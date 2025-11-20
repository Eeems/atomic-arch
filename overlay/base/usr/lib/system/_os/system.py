import json
import os
import sys
import subprocess
import shlex
import shutil

from datetime import datetime
from typing import TextIO
from typing import BinaryIO
from typing import Callable
from typing import cast
from glob import iglob
from select import select
from tempfile import NamedTemporaryFile

from . import SYSTEM_PATH
from . import OS_NAME
from .console import bytes_to_stdout
from .console import bytes_to_stderr


def baseImage(systemFile: str = "/etc/system/Systemfile") -> str:
    from .podman import base_images

    results = list(base_images(systemFile))
    if not results:
        raise RuntimeError("No FROM statement in the Systemfile")

    if len(results) > 1:
        raise RuntimeError(
            "Multiple FROM statements are not currently supported in a Systemfile"
        )

    return results[0]


def _execute(cmd: str) -> int:
    status = os.system(cmd)
    return os.waitstatus_to_exitcode(status)


def execute(
    cmd: str | list[str],
    *args: str,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    if isinstance(cmd, str):
        _args = [cmd]
    else:
        _args = cmd

    ret = execute_pipe(*_args, *args, onstdout=onstdout, onstderr=onstderr)
    if ret:
        raise subprocess.CalledProcessError(ret, cmd, None, None)


def chronic(cmd: str | list[str], *args: str):
    argv: list[str] = []
    if isinstance(cmd, str):
        argv.append(cmd)

    else:
        argv += cmd

    if args:
        argv += args

    try:
        _ = subprocess.check_output(argv, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(e.output.decode("utf-8"))  # pyright:ignore [reportAny]
        raise


def execute_pipe(
    *args: str,
    stdin: bytes | str | BinaryIO | TextIO | None = None,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
) -> int:
    p = subprocess.Popen(
        args,
        stdin=None if stdin is None else subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    while p.stdout is None or p.stderr is None:
        pass

    if isinstance(stdin, bytes):
        while p.stdin is None:
            pass

        _ = p.stdin.write(stdin)
        p.stdin.close()

    elif isinstance(stdin, str):
        while p.stdin is None:
            pass

        _ = p.stdin.write(stdin.encode("utf-8"))
        p.stdin.close()
    elif stdin is not None:
        os.set_blocking(stdin.fileno(), False)

    if stdin is not None:
        while p.stdin is None:
            pass

    os.set_blocking(p.stdout.fileno(), False)
    os.set_blocking(p.stderr.fileno(), False)
    while p.poll() is None:
        _ = select([p.stderr, p.stdout], [] if p.stdin is None else [p.stdin], [])
        line = p.stdout.readline()
        if line:
            onstdout(line)

        line = p.stderr.readline()
        if line:
            onstderr(line)

        if p.stdin is None or p.stdin.closed:
            continue

        if isinstance(stdin, BinaryIO):
            line = stdin.readline()
            if line:
                _ = p.stdin.write(line)

            if stdin.closed:
                p.stdin.close()

        elif isinstance(stdin, TextIO):
            line = stdin.readline().encode("utf-8")
            if line:
                _ = p.stdin.write(line)

            if stdin.closed:
                p.stdin.close()

        else:
            p.stdin.close()

    stdout, stderr = p.communicate()
    for line in stdout.splitlines(True):
        onstdout(line)

    for line in stderr.splitlines(True):
        onstderr(line)

    return p.returncode


def system_kernelCommandLine() -> str:
    if os.path.exists("/etc/system/commandline"):
        with open("/etc/system/commandline", "r") as f:
            return f.read().strip()

    return ""


def checkupdates(image: str | None = None) -> list[str]:
    from .podman import in_system_output
    from .podman import system_hash
    from .podman import context_hash
    from .podman import image_labels

    if image is None:
        image = baseImage()

    updates: list[str] = []
    new_hash = context_hash(f"KARGS={system_kernelCommandLine()}".encode("utf-8"))
    current_hash = system_hash()
    if new_hash != current_hash:
        updates.append(f"Systemfile {current_hash[:9]} -> {new_hash[:9]}")

    mirrorlist: list[str] | None = None
    remote_labels = image_labels(image, remote=True)
    with open("/usr/lib/os-release", "r") as f:
        local_info = {
            x[0]: x[1]
            for x in [
                x.strip().split("=", 1)
                for x in f.readlines()
                if x.startswith("VERSION_ID=") or x.startswith("VERSION=")
            ]
        }

    local_id = local_info.get("VERSION_ID", "0")
    remote_id = remote_labels.get("os-release.VERSION_ID", "0")
    if local_id != remote_id:
        remote_version = remote_labels.get("os-release.VERSION", "0")
        local_version = local_info.get("VERSION", "0")
        updates.append(
            f"{image} {local_version}.{local_id} -> {remote_version}.{remote_id}"
        )

    try:
        data = json.loads(remote_labels.get("mirrorlist", "[]"))  # pyright: ignore[reportAny]
        assert isinstance(data, list)
        for x in data:  # pyright: ignore[reportUnknownVariableType]
            assert isinstance(x, str)

        mirrorlist = cast(list[str], data)

    except json.JSONDecodeError:
        pass

    if mirrorlist is None or not mirrorlist:
        with open("/etc/pacman.d/mirrorlist") as f:
            mirrorlist = [
                x.split("=")[1].strip()
                for x in f.read().splitlines(False)
                if x.startswith("Server") and "=" in x
            ]

    mirrorlist_file = NamedTemporaryFile("w", delete_on_close=False)
    mirrorlist_file.writelines([f"Server = {x}\n" for x in mirrorlist])
    mirrorlist_file.close()

    try:
        updates += (
            in_system_output(
                entrypoint="/usr/bin/checkupdates",
                volumes=[f"{mirrorlist_file.name}:/etc/pacman.d/mirrorlist"],
            )
            .strip()
            .decode("utf-8")
            .splitlines()
        )

    except subprocess.CalledProcessError as e:
        if e.returncode != 2:
            raise

        updates += cast(bytes, e.stdout).strip().decode("utf-8").splitlines()

    finally:
        os.unlink(mirrorlist_file.name)

    return updates


def in_nspawn_system(*args: str, check: bool = False):
    from .ostree import current_deployment

    if not is_root():
        raise RuntimeError("in_nspawn_system can only be called as root")

    if os.path.exists("/ostree") and os.path.isdir("/ostree"):
        _ostree = "/ostree"
        if not os.path.exists(SYSTEM_PATH):
            os.makedirs(SYSTEM_PATH, exist_ok=True)

        if not os.path.exists(f"{SYSTEM_PATH}/ostree"):
            os.symlink("/ostree", f"{SYSTEM_PATH}/ostree")

    else:
        _ostree = f"{SYSTEM_PATH}/ostree"
        os.makedirs(_ostree, exist_ok=True)
        repo = os.path.join(_ostree, "repo")
        from .ostree import ostree

        setattr(ostree, "repo", repo)
        if not os.path.exists(repo):
            ostree("init")

    cache = "/var/cache/pacman"
    if not os.path.exists(cache):
        os.makedirs(cache, exist_ok=True)

    _, checksum, _, stateroot = current_deployment()
    os.environ["SYSTEMD_NSPAWN_LOCK"] = "0"
    # TODO overlay /usr/lib/pacman somehow
    cmd = [
        "systemd-nspawn",
        "--volatile=state",
        "--link-journal=try-guest",
        "--directory=/sysroot",
        f"--bind={SYSTEM_PATH}:{SYSTEM_PATH}",
        "--bind=/boot:/boot",
        "--bind=/run/podman/podman.sock:/run/podman/podman.sock",
        f"--bind={cache}:{cache}",
        f"--bind=+/sysroot/ostree/deploy/{stateroot}/var:/var",
        f"--pivot-root={_ostree}/deploy/{stateroot}/deploy/{checksum}:/sysroot",
        *args,
    ]
    ret = _execute(shlex.join(cmd))
    if ret and check:
        raise subprocess.CalledProcessError(ret, cmd, None, None)

    return ret


def upgrade(
    branch: str = "system",
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    from .podman import export_stream
    from .podman import build

    from .ostree import prune
    from .ostree import deploy
    from .ostree import ostree_cmd

    if not os.path.exists("/ostree"):
        print("OSTree repo missing")
        sys.exit(1)

    if not os.path.exists(SYSTEM_PATH):
        os.makedirs(SYSTEM_PATH, exist_ok=True)

    build(
        buildArgs=[f"KARGS={system_kernelCommandLine()}"],
        onstdout=onstdout,
        onstderr=onstderr,
    )
    with export_stream(
        setup="""
        rm -f /etc
        rm -rf /var/*
        """,
        workingDir=SYSTEM_PATH,
        onstdout=onstdout,
        onstderr=onstderr,
    ) as stdout:
        cmd = ostree_cmd(
            "commit",
            "--generate-composefs-metadata",
            "--generate-sizes",
            f"--branch={OS_NAME}/{branch}",
            f"--subject={datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}",
            "--tree=tar=-",
            "--tar-pathname-filter=^,./",
            "--tar-autocreate-parents",
        )
        ostree_proc = subprocess.Popen(cmd, stdin=stdout)
        ostree_out, ostree_err = ostree_proc.communicate()
        if ostree_out is not None:  # pyright: ignore[reportUnnecessaryComparison]
            onstdout(ostree_out)

        if ostree_err is not None:  # pyright: ignore[reportUnnecessaryComparison]
            onstderr(ostree_err)

        if ostree_proc.returncode:
            raise subprocess.CalledProcessError(
                ostree_proc.returncode, cmd, ostree_out, ostree_err
            )

    prune(branch, onstdout=onstdout, onstderr=onstderr)
    deploy(branch, "/", onstdout=onstdout, onstderr=onstderr)
    cmd = shlex.join(
        [
            "/usr/bin/grub-mkconfig",
            "-o",
            "/boot/efi/EFI/grub/grub.cfg",
        ]
    )
    ret = _execute(cmd)
    if ret:
        raise subprocess.CalledProcessError(ret, cmd, None, None)


def delete(glob: str):
    for path in iglob(glob):
        if os.path.islink(path) or os.path.isfile(path):
            os.unlink(path)

        else:
            shutil.rmtree(path)


def is_root() -> bool:
    return os.geteuid() == 0


def wait_for_processes(
    *processes: subprocess.Popen[bytes],
    cleanup: Callable[[], None] | None = None,
    fast_fail: bool = True,
):
    errors: list[subprocess.CalledProcessError] = []
    queue = list(processes)
    while queue:
        for proc in list(queue):
            try:
                _ = proc.wait(1)

            except subprocess.TimeoutExpired:
                continue

            if proc.returncode is None:
                continue

            queue.remove(proc)
            if not proc.returncode:
                continue

            errors.append(subprocess.CalledProcessError(proc.returncode, proc.args))
            if not fast_fail:
                continue

            for proc in queue:
                proc.terminate()

            for proc in queue:
                try:
                    if proc.returncode is None:
                        _ = proc.wait(timeout=5)

                except subprocess.TimeoutExpired:
                    proc.kill()

            for proc in queue:
                if proc.wait():
                    errors.append(
                        subprocess.CalledProcessError(proc.returncode, proc.args)
                    )

            queue = []
            break

    if cleanup is not None:
        cleanup()

    if errors:
        raise ExceptionGroup("CalledProcessError", errors)  # noqa: F821
