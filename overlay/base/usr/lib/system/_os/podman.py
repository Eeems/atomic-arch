# pyright: reportImportCycles=false
import atexit
import os
import shlex
import shutil
import subprocess
import json

from io import BytesIO
from time import time
from hashlib import sha256
from glob import iglob
from typing import cast
from typing import Callable
from collections.abc import Generator
from contextlib import contextmanager

from . import SYSTEM_PATH

from .system import execute
from .system import _execute  # pyright:ignore [reportPrivateUsage]
from .ostree import ostree

from .console import bytes_to_stdout
from .console import bytes_to_stderr


def podman_cmd(*args: str):
    if _execute("systemd-detect-virt --quiet --container") == 0:
        return ["podman", "--remote", *args]

    return ["podman", *args]


def podman(
    *args: str,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    execute(
        *podman_cmd(*args),
        onstdout=onstdout,
        onstderr=onstderr,
    )


def in_system(
    *args: str,
    target: str = "system:latest",
    entrypoint: str = "/usr/bin/os",
    check: bool = False,
    volumes: list[str] | None = None,
) -> int:
    cmd = shlex.join(
        in_system_cmd(
            *args,
            target=target,
            entrypoint=entrypoint,
            volumes=volumes,
        )
    )
    ret = _execute(cmd)
    if ret and check:
        raise subprocess.CalledProcessError(ret, cmd, None, None)

    return ret


def in_system_output(
    *args: str,
    target: str = "system:latest",
    entrypoint: str = "/usr/bin/os",
    volumes: list[str] | None = None,
) -> bytes:
    return subprocess.check_output(
        in_system_cmd(
            *args,
            target=target,
            entrypoint=entrypoint,
            volumes=volumes,
        )
    )


def in_system_cmd(
    *args: str,
    target: str = "system:latest",
    entrypoint: str = "/usr/bin/os",
    volumes: list[str] | None = None,
) -> list[str]:
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

    return podman_cmd(
        "run",
        "--rm",
        "--privileged",
        "--security-opt=label=disable",
        *[f"--volume={x}" for x in volume_args],
        f"--entrypoint={entrypoint}",
        target,
        *args,
    )


def context_hash(extra: bytes | None = None) -> str:
    m = sha256()
    for file in iglob("/etc/system/**"):
        if os.path.isdir(file):
            m.update(file.encode("utf-8"))

        else:
            with open(file, "rb") as f:
                m.update(f.read())

    if extra is not None:
        m.update(extra)

    return m.hexdigest()


def system_hash() -> str:
    with open("/usr/lib/os-release", "r") as f:
        local_info = {
            x[0]: x[1]
            for x in [
                x.strip().split("=", 1)
                for x in f.readlines()
                if x.startswith("BUILD_ID=")
            ]
        }

    return local_info.get("BUILD_ID", "0000-00-00.0").split(".", 1)[1]


def image_hash(image: str) -> str:
    info = cast(
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
    labels = cast(dict[str, dict[str, str]], info).get("Labels", {})
    return labels.get("hash", "0")


CONTAINER_POST_STEPS = r"""
RUN fc-cache -f

ARG KARGS

RUN /usr/lib/system/build_kernel

RUN sed -i \
  -e 's|^#\(DBPath\s*=\s*\).*|\1/usr/lib/pacman|g' \
  -e 's|^#\(IgnoreGroup\s*=\s*\).*|\1modified|g' \
  /etc/pacman.conf \
  && mv /etc /usr && ln -s /usr/etc /etc \
  && mv /var/lib/pacman /usr/lib \
  && mkdir /sysroot \
  && ln -s /sysroot/ostree ostree

ARG VERSION_ID

RUN /usr/lib/system/set_build_id
"""


def build(
    systemfile: str = "/etc/system/Systemfile",
    buildArgs: list[str] | None = None,
    extraSteps: list[str] | None = None,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    cache = "/var/cache/pacman"
    if not os.path.exists(cache):
        os.makedirs(cache, exist_ok=True)

    context = os.path.join(SYSTEM_PATH, "context")
    if os.path.exists(context):
        _ = shutil.rmtree(context)

    containerfile = os.path.join(context, "Containerfile")
    _ = shutil.copytree("/etc/system", context)

    extra: bytes = "\n".join((buildArgs or []) + (extraSteps or [])).encode("utf-8")
    _buildArgs = [f"VERSION_ID={context_hash(extra)}"]
    if buildArgs is not None:
        _buildArgs += buildArgs

    with open(containerfile, "w") as f, open(systemfile, "r") as i:
        _ = f.write(i.read())
        _ = f.write("\n".join((extraSteps or []) + [CONTAINER_POST_STEPS.strip()]))

    podman(
        "build",
        "--force-rm",
        "--no-hosts",
        "--no-hostname",
        "--dns=none",
        "--tag=system:latest",
        *[f"--build-arg={x}" for x in _buildArgs],
        f"--volume={cache}:{cache}",
        f"--file={containerfile}",
        onstdout=onstdout,
        onstderr=onstderr,
    )


@contextmanager
def export(
    tag: str = "latest",
    setup: str = "",
    workingDir: str | None = None,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
    onsetup: Callable[[str], None] | None = None,
) -> Generator[BytesIO, None, None]:
    if workingDir is None:
        workingDir = SYSTEM_PATH

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
        onstdout=onstdout,
        onstderr=onstderr,
    )
    if onsetup is not None:
        onsetup(name)

    cmd = podman_cmd("export", name)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    assert process.stdout is not None
    try:
        yield cast(BytesIO, process.stdout)

    finally:
        process.stdout.close()
        _ = process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, None, None)

        atexit.unregister(exitFunc1)
        podman("rm", name, onstdout=onstdout, onstderr=onstderr)
        os.chdir(cwd)
