import json
import os
import sys
import subprocess
import shlex
import shutil

from typing import TextIO
from typing import BinaryIO
from typing import Callable
from typing import cast
from glob import iglob

from . import SYSTEM_PATH
from . import OS_NAME


def baseImage() -> str:
    with open("/etc/system/Systemfile", "r") as f:
        return [x.split(" ")[1].strip() for x in f.readlines() if x.startswith("FROM")][
            0
        ]


def _execute(cmd: str):
    status = os.system(cmd)
    return os.waitstatus_to_exitcode(status)


def execute(cmd: str | list[str], *args: str):
    if not isinstance(cmd, str):
        cmd = shlex.join(cmd)

    if args:
        cmd = f"{cmd} {shlex.join(args)}"

    ret = _execute(cmd)
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
        print(e.output)  # pyright:ignore [reportAny]
        raise


def execute_pipe(
    *args: str,
    stdin: bytes | str | BinaryIO | TextIO | None = None,
    onstdout: Callable[[bytes], None] = print,
    onstderr: Callable[[bytes], None] = print,
) -> int:
    p = subprocess.Popen(
        args,
        stdin=None if stdin is None else subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    while p.stdout is None or p.stderr is None:
        pass

    if stdin is None:
        pass

    elif isinstance(stdin, bytes):
        while p.stdin is None:
            pass

        _ = p.stdin.write(stdin)
        p.stdin.close()

    elif isinstance(stdin, str):
        while p.stdin is None:
            pass

        _ = p.stdin.write(stdin.encode("utf-8"))
        p.stdin.close()

    else:
        while p.stdin is None:
            pass

    os.set_blocking(p.stdout.fileno(), False)
    os.set_blocking(p.stderr.fileno(), False)
    while p.poll() is None:
        line = p.stdout.readline()
        if line:
            onstdout(line)

        line = p.stderr.readline()
        if line:
            onstderr(line)

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

    stdout, stderr = p.communicate()
    for line in stdout.splitlines(True):
        onstdout(line)

    for line in stderr.splitlines(True):
        onstderr(line)

    return p.returncode


def checkupdates(image: str | None = None) -> list[str]:
    from .podman import podman_cmd
    from .podman import in_system_output

    if image is None:
        image = baseImage()

    digests = [
        x
        for x in subprocess.check_output(
            podman_cmd("inspect", "--format={{ .Digest }}", image)
        )
        .decode("utf-8")
        .strip()
        .split("\n")
        if x
    ]
    updates: list[str] = []
    if digests:
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
        remote_info = cast(
            dict[str, object],
            json.loads(
                subprocess.check_output(
                    [
                        "skopeo",
                        "inspect",
                        f"docker://{image}",
                    ]
                )
            ),
        )
        remote_labels = cast(dict[str, dict[str, str]], remote_info).get("Labels", {})
        remote_id = remote_labels.get("os-release.VERSION_ID", "0")
        if local_id != remote_id:
            remote_version = remote_labels.get("os-release.VERSION", "0")
            local_version = local_info.get("VERSION", "0")
            updates.append(
                f"{image} {local_version}.{local_id} -> {remote_version}.{remote_id}"
            )

    updates += (
        in_system_output(entrypoint="/usr/bin/checkupdates")
        .strip()
        .decode("utf-8")
        .splitlines()
    )
    return updates


def in_nspawn_system(*args: str, check: bool = False):
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

    checksum = (
        subprocess.check_output(["bash", "-c", "ostree admin status | grep *"])
        .decode("utf-8")
        .split(" ")[3]
    )
    os.environ["SYSTEMD_NSPAWN_LOCK"] = "0"
    # TODO overlay /usr/lib/pacman somehow
    cmd = [
        "systemd-nspawn",
        "--volatile=state",
        "--link-journal=try-guest",
        "--directory=/sysroot",
        f"--bind={SYSTEM_PATH}:{SYSTEM_PATH}",
        "--bind=/boot:/boot",
        f"--bind={cache}:{cache}",
        f"--pivot-root={_ostree}/deploy/{OS_NAME}/deploy/{checksum}:/sysroot",
        *args,
    ]
    ret = _execute(shlex.join(cmd))
    if ret and check:
        raise subprocess.CalledProcessError(ret, cmd, None, None)

    return ret


def upgrade(branch: str = "system"):
    from .podman import export
    from .podman import build
    from .ostree import commit
    from .ostree import prune
    from .ostree import deploy

    if not os.path.exists("/ostree"):
        print("OSTree repo missing")
        sys.exit(1)

    if not os.path.exists(SYSTEM_PATH):
        os.makedirs(SYSTEM_PATH, exist_ok=True)

    if os.path.exists("/etc/system/commandline"):
        with open("/etc/system/commandline", "r") as f:
            kernelCommandline = f.read().strip()

    else:
        kernelCommandline = ""

    rootfs = os.path.join(SYSTEM_PATH, "rootfs")
    if os.path.exists(rootfs):
        shutil.rmtree(rootfs)

    build(buildArgs=[f"KARGS={kernelCommandline}"])
    export(rootfs=rootfs, workingDir=SYSTEM_PATH)
    commit(branch, rootfs)
    prune(branch)
    deploy(branch, "/")
    _ = shutil.rmtree(rootfs)
    execute("/usr/bin/grub-mkconfig", "-o", "/boot/efi/EFI/grub/grub.cfg")


def delete(glob: str):
    for path in iglob(glob):
        if os.path.islink(path) or os.path.isfile(path):
            os.unlink(path)

        else:
            shutil.rmtree(path)


def is_root() -> bool:
    return os.geteuid() == 0
