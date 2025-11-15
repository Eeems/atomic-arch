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
from typing import IO, Any, cast
from typing import Callable
from collections.abc import Generator, Iterable
from contextlib import contextmanager

from . import SYSTEM_PATH
from . import REGISTRY
from . import IMAGE
from . import REPO

from .system import execute
from .system import _execute  # pyright:ignore [reportPrivateUsage]
from .ostree import ostree

from .console import bytes_to_iec, bytes_to_stdout
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


def image_exists(image: str, remote: bool = True) -> bool:
    image_exists = not _execute(shlex.join(podman_cmd("image", "exists", image)))
    if image_exists or not remote:
        return image_exists

    image = image_qualified_name(image)
    registry, image, tag, ref = image_name_parts(image)
    if ref is not None:
        raise NotImplementedError()

    tags = image_tags(f"{registry}/{image}")
    if not tag:
        return bool(tags)

    return tag in tags


def image_tags(image: str) -> list[str]:
    image = image_qualified_name(image)
    registry, image, _, _ = image_name_parts(image)
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
    if (registry or REGISTRY) == REGISTRY and repo == IMAGE:
        registry = REGISTRY

    if tag and digest:
        tag = None

    return image_name_from_parts(registry, repo, tag, digest)


def _image_digest_remote(image: str) -> str:
    image = image_qualified_name(image)
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
            f"atomic.manifest.tag.{tag}",
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
        "--pull=never",
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


def _save_image(image: str) -> tuple[subprocess.Popen[bytes], TemporaryDirectory[str]]:
    print(f"Saving {image}")
    tmpdir = TemporaryDirectory()
    fifo = os.path.join(tmpdir.name, "fifo")
    os.mkfifo(fifo)
    tar_dir = os.path.join(tmpdir.name, "tar")
    os.mkdir(tar_dir)
    _wait_for_processes(
        subprocess.Popen(
            [
                "skopeo",
                "copy",
                "--preserve-digests",
                f"docker://{image}",
                f"oci-archive:{fifo}",
            ]
        ),
        subprocess.Popen(
            ["tar", "--extract", f"--file={fifo}", f"--directory={tar_dir}"]
        ),
    )
    tar_proc = subprocess.Popen(
        [
            "tar",
            "--format=posix",
            "--pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime,delete=.*",
            "--mtime=@0",
            "--sort=name",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "--create",
            f"--directory={tar_dir}",
            ".",
        ],
        stdout=subprocess.PIPE,
    )
    assert tar_proc.stdout is not None
    return tar_proc, tmpdir


def _wait_for_processes(
    *processes: subprocess.Popen[bytes],
    cleanup: Callable[[], None] | None = None,
):
    errors: list[subprocess.CalledProcessError] = []
    for proc in processes:
        if proc.wait() != 0:
            errors.append(subprocess.CalledProcessError(proc.returncode, proc.args))

    if cleanup is not None:
        cleanup()

    if errors:
        raise ExceptionGroup("CalledProcessError", errors)  # noqa: F821


def _save_image_to_file(image: str, path: str):
    tar_proc, tmpdir = _save_image(image)
    assert tar_proc.stdout is not None
    with open(path, "wb") as f:
        for line in tar_proc.stdout:
            _ = f.write(line)
            f.flush()

    _wait_for_processes(tar_proc, cleanup=tmpdir.cleanup)


def escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\\n")


def create_delta(imageA: str, imageB: str, imageD: str, pull: bool = True) -> bool:
    digestA = image_digest(imageA)
    digestB = image_digest(imageB)
    with TemporaryDirectory() as tmpdir:
        old_oci_path = os.path.join(tmpdir, "old.oci")
        _save_image_to_file(imageA, old_oci_path)
        tar_proc, tardir = _save_image(imageB)
        assert tar_proc.stdout is not None
        xdelta_proc = subprocess.Popen(
            ["xdelta3", "-0", "-S", "none", "-s", old_oci_path, "-", "-"],
            stdin=tar_proc.stdout,
            stdout=subprocess.PIPE,
        )
        tar_proc.stdout.close()
        assert xdelta_proc.stdout is not None
        diff_path = os.path.join(tmpdir, "diff.xd3.zstd")
        zstd_proc = subprocess.Popen(
            ["zstd", "-19", "-T0", "-o", diff_path],
            stdin=xdelta_proc.stdout,
            stdout=subprocess.PIPE,
        )
        xdelta_proc.stdout.close()
        _ = zstd_proc.communicate()
        _wait_for_processes(
            zstd_proc,
            xdelta_proc,
            tar_proc,
            cleanup=tardir.cleanup,
        )
        labels: dict[str, str] = {
            "description": f"Delta between {imageA} and {imageB}",
            "ref.name": imageD,
        }
        src_labels = image_labels(imageB)
        for label in [
            "create",
            "authors",
            "url",
            "documentation",
            "source",
            "vendor",
            "licenses",
            "base.digest",
            "base.name",
            "version",
            "revision",
        ]:
            full_label = f"org.opencontainers.image.{label}"
            if full_label in src_labels:
                labels[label] = src_labels[full_label]

        containerfile = os.path.join(tmpdir, "Containerfile")
        sizeA = os.path.getsize(old_oci_path)
        sizeB = image_size(imageB)
        sizeD = os.path.getsize(diff_path)
        maxSize = int(sizeB * 0.6)

        print(f"Size of {imageA}: {bytes_to_iec(sizeA)}")
        print(f"Size of {imageB}: {bytes_to_iec(sizeB)}")
        print(f"Size of delta: {bytes_to_iec(sizeD)}")
        print(f"Threshhold size: {bytes_to_iec(maxSize)}")
        success = sizeD < maxSize
        with open(containerfile, "w") as f:
            _ = f.write(f"""\
FROM scratch
LABEL {"\n  ".join([f'org.opencontainers.image.{k}="{escape_label(v)}" \\' for k, v in labels.items()])}
  atomic.patch.prev="{digestA}" \\
  atomic.patch.ref="{digestB}" \\
  atomic.patch.format="xdelta3+zstd"
""")
            if success:
                print("Delta is too large, creating empty delta instead")

            else:
                _ = f.write("COPY diff.xd3.zstd /diff.xd3.zstd\n")

        podman(
            "build",
            f"--tag={imageD}",
            f"--file={containerfile}",
            "--force-rm",
            f"--pull={'newer' if pull else 'never'}",
            tmpdir,
        )
        return success


def apply_delta(
    image: str,
    delta_image: str,
    new_image: str,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    image = image_qualified_name(image)
    delta_image = image_qualified_name(delta_image)
    if not image_exists(delta_image, False):
        podman("pull", delta_image, onstdout=onstdout, onstderr=onstderr)

    labels = image_labels(delta_image, False)
    if labels.get("atomic.patch.format", "") != "xdelta3+zstd":
        raise ValueError("Incompatible patch format")

    digest = image_digest(image, remote=False)
    if labels.get("atomic.patch.prev", "") != digest:
        raise ValueError("Patch does not apply to this image")

    new_digest = image_digest(new_image, remote=True)
    if labels.get("atomic.patch.ref", "") != new_digest:
        raise ValueError("Patch does not result in the correct iamge")

    if not image_exists(image, False) or image_digest(image, False) != digest:
        podman("pull", image, onstdout=onstdout, onstderr=onstderr)

    with TemporaryDirectory() as tmpdir:
        onstderr(b"Saving old.oci\n")
        old_oci_path = os.path.join(tmpdir, "old.oci")
        _save_image_to_file(image, old_oci_path)
        onstderr(b"Patching old.oci\n")
        podman_run_proc = subprocess.Popen(
            podman_cmd(
                "run",
                "--rm",
                *[
                    f"--volume={x}:{x}:ro"
                    for x in ["/usr", "/lib", "/lib64", "/bin", "/var"]
                ],
                delta_image,
                *["zstdcat", "--decompress", "--keep", "/diff.xd3.zstd"],
            ),
            stdout=subprocess.PIPE,
        )
        assert podman_run_proc.stdout is not None
        new_oci_path = os.path.join(tmpdir, "new.oci")
        xdelta3_proc = subprocess.Popen(
            ["xdelta3", "-d", "-s", old_oci_path, "-", new_oci_path],
            stdin=podman_run_proc.stdout,
        )
        podman_run_proc.stdout.close()
        _ = xdelta3_proc.communicate()
        _wait_for_processes(xdelta3_proc, podman_run_proc)
        os.unlink(old_oci_path)
        _ = subprocess.check_call(
            [
                "skopeo",
                "copy",
                "--preserve-digests",
                f"oci-archive:{new_oci_path}",
                f"containers-storage:{new_image}",
            ]
        )
        if image_digest(image, remote=False) != new_digest:
            raise RuntimeError("Resulting image has the wrong digest")


def pull(
    image: str,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    image = image_qualified_name(image)
    remote_digest = image_digest(image, remote=True)
    image_exists_locally = image_exists(image, remote=False)
    candidates: list[tuple[str, str]] = []
    if image_exists_locally:
        local_digest = image_digest(image, remote=False)
        if local_digest == remote_digest:
            onstderr(f"Image {image} is already up to date\n".encode("utf-8"))
            return

        candidates.append((image, local_digest))

    registry, name, target_tag, ref = image_name_parts(image)
    if ref is not None:
        onstderr(b"Unable to handle digest images...\n")
        podman("pull", image, onstdout=onstdout, onstderr=onstderr)

    target_tag = target_tag or "latest"
    base_image = f"{registry}/{name}"
    tags = image_tags(base_image)
    tags.sort()
    tag_base = target_tag.split("_")[0] if "_" in target_tag else target_tag
    version_tags = [
        tag for tag in tags if tag.startswith(f"{tag_base}_") and "_" in tag
    ]
    for version_tag in version_tags:
        local_image = f"{base_image}:{version_tag}"
        if image_exists(local_image, remote=False):
            local_digest = image_digest(local_image, remote=False)
            candidates.append((local_image, local_digest))
            onstderr(f"Found local version: {local_image}\n".encode("utf-8"))

    for local_image, local_digest in candidates:
        delta_tag = (
            f"_diff-{hex_to_base62(local_digest)}-{hex_to_base62(remote_digest)}"
        )
        delta_image = f"{base_image}:{delta_tag}"
        onstderr(f"Looking for potential delta {delta_tag}\n".encode("utf-8"))
        if not image_exists(delta_image, remote=True):
            onstderr(b"Not found\n")
            continue

        delta_labels = image_labels(delta_image, remote=True)
        if delta_labels.get("atomic.patch.prev") != local_digest:
            onstderr(b"Wrong digest\n")
            continue

        if delta_labels.get("atomic.patch.format", "none") == "none":
            onstderr(b"Empty patch, likely paching will be too large\n")
            continue

        delta_size = image_size(delta_image)
        target_size = image_size(image)
        if delta_size >= target_size * 0.6:
            onstderr(b"Delta is too large\n")
            continue

        target_size_fmt = bytes_to_iec(target_size)
        savings_pct = ((target_size - delta_size) / target_size) * 100
        onstderr(
            f"Saving {savings_pct:.1f} of {target_size_fmt} using delta optimization...\n".encode(
                "utf-8"
            )
        )
        try:
            apply_delta(
                local_image,
                delta_image,
                image,
                onstdout=onstdout,
                onstderr=onstderr,
            )

            return

        except Exception as e:
            onstderr(f"Delta optimization failed: {e}\n".encode("utf-8"))
            continue

        finally:
            if image_exists(delta_image, remote=False):
                podman("rmi", delta_image, onstdout=onstdout, onstderr=onstderr)

    onstderr(b"Falling back to full pull...\n")
    podman("pull", f"{base_image}:{target_tag}", onstdout=onstdout, onstderr=onstderr)


def parse_containerfile(
    containerfile: str | IO[str],
    build_args: dict[str, str] | None = None,
    pretty: bool = False,
) -> list[dict[str, Any]]:  # pyright: ignore[reportExplicitAny]
    is_path = isinstance(containerfile, str)
    if is_path:
        containerfile = open(containerfile, "r")

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

        yield image_name_from_parts(registry, name, tag, ref)
