# pyright: reportImportCycles=false
import atexit
import os
import shlex
import shutil
import string
import tarfile
import subprocess
import json

from time import time
from hashlib import sha256
from glob import iglob
from typing import IO, Any, cast
from typing import Callable
from collections.abc import Generator, Iterable
from contextlib import contextmanager

from . import OS_NAME
from . import SYSTEM_PATH
from . import REGISTRY
from . import IMAGE
from . import REPO

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
    flags: list[str] | None = None,
) -> int:
    cmd = shlex.join(
        in_system_cmd(
            *args,
            target=target,
            entrypoint=entrypoint,
            volumes=volumes,
            flags=flags,
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
    flags: list[str] | None = None,
) -> bytes:
    return subprocess.check_output(
        in_system_cmd(
            *args,
            target=target,
            entrypoint=entrypoint,
            volumes=volumes,
            flags=flags,
        )
    )


def in_system_cmd(
    *args: str,
    target: str = "system:latest",
    entrypoint: str = "/usr/bin/os",
    volumes: list[str] | None = None,
    flags: list[str] | None = None,
) -> list[str]:
    target = image_qualified_name(target)
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
        "--pull=never",
        "--security-opt=label=disable",
        *[f"--volume={x}" for x in volume_args],
        *[f"--{x}" for x in (flags or [])],
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
    image = image_qualified_name(image)
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


def image_exists(image: str, remote: bool = True, skip_manifest: bool = False) -> bool:
    image_exists = not _execute(shlex.join(podman_cmd("image", "exists", image)))
    if image_exists or not remote:
        return image_exists

    image = image_qualified_name(image)
    registry, image, tag, ref = image_name_parts(image)
    if ref is not None:
        raise NotImplementedError()

    tags = image_tags(f"{registry}/{image}", skip_manifest=skip_manifest)
    if not tag:
        return bool(tags)

    return tag in tags


def image_tags(image: str, skip_manifest: bool = False) -> list[str]:
    image = image_qualified_name(image)
    registry, image, _, _ = image_name_parts(image)
    if (
        not skip_manifest
        and registry == REGISTRY
        and image == IMAGE
        and _latest_manifest()
    ):
        tags = [
            x[19:]
            for x in image_labels(f"{REPO}:_manifest", False).keys()
            if x.startswith("arkes.manifest.tag.")
        ]
        if tags:
            return ["_manifest", *tags]

    data: dict[str, str | list[str]] = json.loads(  # pyright:ignore [reportAny]
        subprocess.check_output(
            [
                "skopeo",
                "list-tags",
                f"docker://{registry}/{image}",
            ]
        )
    )
    assert isinstance(data, dict), f"Unexpected data {data}"
    tags = data.get("Tags", [])
    assert isinstance(tags, list), f"Tags is not a list: {tags}"
    return tags


def image_name_parts(name: str) -> tuple[str | None, str, str | None, str | None]:
    registry = None
    tag = None
    ref = None
    if "/" in name:
        registry, name = name.split("/", 1)
        if "." not in registry and registry != "localhost":
            name = f"{registry}/{name}"
            registry = None

    if "@" in name:
        name, ref = name.split("@", 1)
        assert ref.startswith("sha256:")

    if ":" in name:
        name, tag = name.split(":", 1)

    return registry, name, tag, ref


def image_name_from_parts(
    registry: str | None,
    repo: str,
    tag: str | None,
    digest: str | None,
) -> str:
    suffix = ""
    if tag is not None:
        suffix = f":{tag}"

    if digest is not None:
        suffix = f"{suffix}@{digest}"

    prefix = ""
    if registry is None:
        match repo:
            case "system":
                registry = "localhost"

            case "scratch":
                pass

            case _:
                if repo != IMAGE:
                    registry = "docker.io"

    if registry is not None:
        prefix = f"{registry}/"

    return f"{prefix}{repo}{suffix}"


def image_qualified_name(image: str) -> str:
    registry, repo, tag, digest = image_name_parts(image)
    if ((registry or REGISTRY) == REGISTRY) and repo == IMAGE:
        registry = REGISTRY

    if registry == "docker.io" and repo == f"library/{OS_NAME}":
        registry = REGISTRY
        repo = IMAGE

    if tag and digest:
        tag = None

    return image_name_from_parts(registry, repo, tag, digest)


def _image_digest_remote(image: str) -> str:
    return (
        subprocess.check_output(
            [
                "skopeo",
                "inspect",
                f"docker://{image}",
                "--format={{.Digest}}",
            ]
        )
        .strip()
        .decode("utf-8")
    )


def _latest_manifest() -> bool:
    return (
        subprocess.run(
            podman_cmd("pull", f"{REPO}:_manifest"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def image_digest(image: str, remote: bool = True) -> str:
    image = image_qualified_name(image)
    if not remote:
        return (
            subprocess.check_output(
                ["podman", "inspect", image, "--format={{.Digest}}"]
            )
            .strip()
            .decode("utf-8")
        )

    registry, repo, tag, _ = image_name_parts(image)
    if tag and registry == REGISTRY and repo == IMAGE and _latest_manifest():
        return image_labels(f"{REPO}:_manifest", False).get(
            f"arkes.manifest.tag.{tag}",
            _image_digest_remote(image),
        )

    return _image_digest_remote(image)


def image_size(image: str) -> int:
    image = image_qualified_name(image)
    manifest: dict[str, list[dict[str, int]]] = json.loads(  # pyright: ignore[reportAny]
        subprocess.check_output(
            [
                "skopeo",
                "inspect",
                f"docker://{image}",
                "--raw",
            ]
        )
    )
    layers = manifest.get("layers", [])
    # TODO when multiarch images are added, update this to handle that
    return 0 if not layers else sum(layer.get("size", 0) for layer in layers)


CONTAINER_POST_STEPS = r"""
RUN fc-cache -f

ARG KARGS

RUN /usr/lib/system/build_kernel

RUN /usr/lib/system/prepare_fs

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
    from .system import baseImage

    base_image = baseImage(systemfile)
    if not image_exists(base_image, remote=False):
        pull(base_image)

    cache = "/var/cache/pacman"
    if not os.path.exists(cache):
        os.makedirs(cache, exist_ok=True)

    context = os.path.join(SYSTEM_PATH, "context")
    if os.path.exists(context):
        _ = shutil.rmtree(context)

    containerfile = os.path.join(context, "Containerfile")
    try:
        _ = shutil.copytree("/etc/system", context)

        extra: bytes = "\n".join((buildArgs or []) + (extraSteps or [])).encode("utf-8")
        _buildArgs = [
            f"VERSION_ID={context_hash(extra)}",
            "TAR_SORT=1",
            "TAR_DETERMINISTIC=1",
        ]
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
            "--pull=never",
            "--cap-add=SYS_ADMIN",
            *[f"--build-arg={x}" for x in _buildArgs],
            f"--volume={cache}:{cache}",
            f"--file={containerfile}",
            "--format=oci",
            onstdout=onstdout,
            onstderr=onstderr,
        )

    finally:
        if os.path.exists(context):
            shutil.rmtree(context)


@contextmanager
def export_stream(
    tag: str = "latest",
    setup: str = "",
    workingDir: str | None = None,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
) -> Generator[IO[bytes], None, None]:
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
        yield process.stdout

    finally:
        process.stdout.close()
        _ = process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd, None, None)

        atexit.unregister(exitFunc1)
        podman("rm", name, onstdout=onstdout, onstderr=onstderr)
        os.chdir(cwd)


@contextmanager
def export(
    tag: str = "latest",
    setup: str = "",
    workingDir: str | None = None,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
) -> Generator[tarfile.TarFile, None, None]:
    with export_stream(tag, setup, workingDir, onstdout, onstderr) as stdout:
        yield tarfile.open(fileobj=stdout, mode="r|*")


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


def escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\\n")


def pull(
    image: str,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    podman(
        "pull",
        image_qualified_name(image),
        onstdout=onstdout,
        onstderr=onstderr,
    )


def parse_containerfile(
    containerfile: str | IO[str],
    build_args: dict[str, str] | None = None,
    pretty: bool = False,
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    is_path = isinstance(containerfile, str)
    if is_path:
        containerfile = open(containerfile, "r")

    try:
        argv = ["-p"] if pretty else []
        if build_args is not None:
            argv += [x for k, v in build_args.items() for x in ["-b", f"{k}={v}"]]

        data = json.loads(  # pyright: ignore[reportAny]
            subprocess.check_output(
                ["dockerfile2llbjson", *argv],
                stdin=containerfile,
            ).decode("utf-8")
        )
        assert isinstance(data, list)

    finally:
        if is_path:
            containerfile.close()

    return cast(list[dict[str, Any]], data)  # pyright: ignore[reportExplicitAny]


def base_images(
    containerfile: str, build_args: dict[str, str] | None = None
) -> Iterable[str]:
    for base_image in [
        b
        for x in parse_containerfile(containerfile, build_args, False)
        for f in [
            cast(dict[str, dict[str, str]], x.get("Op", {}))
            .get("source", {})
            .get("identifier", "")
        ]
        for b in [f[15:]]
        if f.startswith("docker-image://")
        if b != "scratch"
    ]:
        registry, name, tag, ref = image_name_parts(base_image)
        if tag and ref:
            ref = None

        if registry == "docker.io" and name == IMAGE:
            registry = REGISTRY

        yield image_qualified_name(image_name_from_parts(registry, name, tag, ref))
