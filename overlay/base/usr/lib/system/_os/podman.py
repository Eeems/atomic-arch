import os
import shlex
import subprocess

from . import SYSTEM_PATH
from . import ostree
from . import execute
from . import _execute


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
