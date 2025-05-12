import atexit
import os
import shlex
import shutil
import tarfile
import subprocess

from time import time

from . import SYSTEM_PATH
from .system import execute
from .system import _execute  # pyright:ignore [reportPrivateUsage]
from .ostree import ostree


def podman_cmd(*args: str):
    if _execute("systemd-detect-virt --quiet --container") == 0:
        return ["podman", "--remote", *args]

    return ["podman", *args]


def podman(*args: str):
    execute(*podman_cmd(*args))


def in_system(
    *args: str,
    target: str = "system:latest",
    entrypoint: str = "/usr/bin/os",
    check: bool = False,
    volumes: list[str] | None = None,
) -> int:
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
        setattr(ostree, "repo", repo)
        if not os.path.exists(repo):
            ostree("init")

    cache = "/var/cache/pacman"
    if not os.path.exists(cache):
        os.makedirs(cache, exist_ok=True)

    pacman = "/usr/lib/pacman"
    if not os.path.exists(pacman):
        pacman = "/var/lib/pacman"

    volume_args: list[str] = [
        "/run/podman/podman.sock:/run/podman/podman.sock",
        f"{pacman}:/usr/lib/pacman:O",
        "/etc/pacman.d/gnupg:/etc/pacman.d/gnupg:O",
        f"{SYSTEM_PATH}:{SYSTEM_PATH}",
        f"{_ostree}:/sysroot/ostree",
        f"{cache}:{cache}",
    ]
    if volumes is not None:
        volume_args += volumes

    cmd = podman_cmd(
        "run",
        "--rm",
        "--privileged",
        "--security-opt=label=disable",
        *[f"--volume={x}" for x in volume_args],
        f"--entrypoint={entrypoint}",
        target,
        *args,
    )
    ret = _execute(shlex.join(cmd))
    if ret and check:
        raise subprocess.CalledProcessError(ret, cmd, None, None)

    return ret


def build(systemfile: str = "/etc/system/Systemfile"):
    cache = "/var/cache/pacman"
    if not os.path.exists(cache):
        os.makedirs(cache, exist_ok=True)

    uuid = (
        subprocess.check_output(["bash", "-c", "uuidgen --time-v7 | cut -c-8"])
        .decode("utf-8")
        .strip()
    )
    podman(
        "build",
        "--force-rm",
        "--tag=system:latest",
        f"--build-arg=VERSION_ID={uuid}",
        f"--volume={cache}:{cache}",
        f"--file={systemfile}",
    )


def export(
    tag: str = "latest",
    setup: str = "",
    rootfs: str | None = None,
    workingDir: str | None = None,
):
    if workingDir is None:
        workingDir = SYSTEM_PATH

    if rootfs is None:
        rootfs = os.path.join(workingDir, "rootfs")

    if os.path.exists(rootfs):
        shutil.rmtree(rootfs)

    os.makedirs(rootfs, exist_ok=True)
    os.makedirs(workingDir, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(workingDir)
    timestamp = int(time())
    name = f"export-{tag}-{timestamp}"
    exitFunc1 = atexit.register(podman, "rm", name)
    podman(
        "run",
        f"--name={name}",
        "--privileged",
        "--security-opt=label=disable",
        "--volume=/run/podman/podman.sock:/run/podman/podman.sock",
        f"system:{tag}",
        "-c",
        setup,
    )
    cmd = podman_cmd("export", name)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    assert process.stdout is not None
    with tarfile.open(fileobj=process.stdout, mode="r|*") as t:
        t.extractall(rootfs, numeric_owner=True, filter="fully_trusted")

    process.stdout.close()
    _ = process.wait()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd, None, None)

    atexit.unregister(exitFunc1)
    podman("rm", name)
    os.chdir(cwd)
