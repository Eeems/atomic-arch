# pyright: reportImportCycles=false
import atexit
import os
import shlex
import shutil
import string
import tarfile
import subprocess
import json

from tempfile import TemporaryDirectory
from time import time
from hashlib import sha256
from glob import iglob
from typing import cast
from typing import Callable
from collections.abc import Generator
from contextlib import contextmanager

from . import SYSTEM_PATH
from . import REGISTRY

from .system import execute
from .system import _execute  # pyright:ignore [reportPrivateUsage]
from .ostree import ostree

from .console import bytes_to_stdout
from .console import bytes_to_stderr


def podman_cmd(*args: str) -> list[str]:
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
    for file in sorted(iglob("/etc/system/**", recursive=True)):
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


def image_info(image: str, remote: bool = True) -> dict[str, object]:
    if remote:
        args = ["skopeo", "inspect", f"docker://{image}"]

    else:
        args = podman_cmd("inspect", "--format={{ json . }}", image)

    data = subprocess.check_output(args)
    return cast(dict[str, object], json.loads(data))


def image_labels(image: str, remote: bool = True) -> dict[str, str]:
    return cast(dict[str, dict[str, str]], image_info(image, remote)).get("Labels", {})


def image_hash(image: str, remote: bool = True) -> str:
    return image_labels(image, remote=remote).get("hash", "0")


def image_exists(image: str, remote: bool = True) -> bool:
    image_exists = not _execute(shlex.join(podman_cmd("image", "exists", image)))
    if image_exists or not remote:
        return image_exists

    image, tag = image.rsplit(":", 1)
    return tag in image_tags(image)


def image_tags(image: str) -> list[str]:
    if ":" in image:
        image, _ = image.rsplit(":", 1)

    data: dict[str, str | list[str]] = json.loads(  # pyright:ignore [reportAny]
        subprocess.check_output(
            [
                "skopeo",
                "list-tags",
                f"docker://{REGISTRY}/{image}",
            ]
        )
    )
    assert isinstance(data, dict), f"Unexpected data {data}"
    tags = data.get("Tags", [])
    assert isinstance(tags, list), f"Tags is not a list: {tags}"
    return tags


def image_digest(image: str, remote: bool = True) -> str:
    if remote:
        return (
            subprocess.check_output(
                [
                    "skopeo",
                    "inspect",
                    f"docker://{REGISTRY}/{image}",
                    "--format={{.Digest}}",
                ]
            )
            .strip()
            .decode("utf-8")
        )

    return (
        subprocess.check_output(["podman", "inspect", image, "--format={{.Digest}}"])
        .strip()
        .decode("utf-8")
    )


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
) -> Generator[tarfile.TarFile, None, None]:
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
    cmd = podman_cmd("export", name)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    assert process.stdout is not None
    try:
        yield tarfile.open(fileobj=process.stdout, mode="r|*")

    finally:
        process.stdout.close()
        _ = process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, None, None)

        atexit.unregister(exitFunc1)
        podman("rm", name, onstdout=onstdout, onstderr=onstderr)
        os.chdir(cwd)


def hex_to_base62(hex_digest: str) -> str:
    if hex_digest.startswith("sha256:"):
        hex_digest = hex_digest[7:]

    return (
        "".join(
            (string.digits + string.ascii_lowercase + string.ascii_uppercase)[
                int(hex_digest, 16) // (62**i) % 62
            ]
            for i in range(50)
        )[::-1].lstrip("0")
        or "0"
    )


def create_delta(imageA: str, imageB: str, imageD: str, pull: bool = True):
    digestA = image_digest(imageA)
    digestB = image_digest(imageB)
    with TemporaryDirectory() as tmpdir:
        old_oci_path = os.path.join(tmpdir, "old.oci")
        podman("save", imageA, "-o", old_oci_path)

        podman_proc = subprocess.Popen(
            podman_cmd("save", imageB, "--quiet"),
            stdout=subprocess.PIPE,
        )
        assert podman_proc.stdout is not None
        xdelta_proc = subprocess.Popen(
            ["xdelta3", "-0", "-S", "none", "-s", old_oci_path, "-", "-"],
            stdin=podman_proc.stdout,
            stdout=subprocess.PIPE,
        )
        podman_proc.stdout.close()
        assert xdelta_proc.stdout is not None
        zstd_proc = subprocess.Popen(
            ["zstd", "-19", "-T0", "-o", os.path.join(tmpdir, "diff.xd3.zstd")],
            stdin=xdelta_proc.stdout,
            stdout=subprocess.PIPE,
        )
        xdelta_proc.stdout.close()
        _ = zstd_proc.communicate()
        for proc in [zstd_proc, xdelta_proc, podman_proc]:
            if proc.wait() != 0:
                raise subprocess.CalledProcessError(proc.returncode, proc.args)

        containerfile = os.path.join(tmpdir, "Containerfile")
        with open(containerfile, "w") as f:
            _ = f.write(f"""\
FROM scratch
COPY diff.xd3.zstd /diff.xd3.zstd
LABEL atomic.patch.prev="{digestA}" \\
  atomic.patch.ref="{digestB}" \\
  atomic.patch.format="xdelta3+zstd" \\
  org.opencontainers.image.description="Delta between {imageA} and {imageB}"
""")
        podman(
            "build",
            f"--tag={imageD}",
            f"--file={containerfile}",
            "--force-rm",
            f"--pull={'newer' if pull else 'never'}",
            tmpdir,
        )
