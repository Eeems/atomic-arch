#!/usr/bin/env python
import signal
import subprocess
import sys
import shutil
import os
import atexit
import tempfile
import json
import threading

from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from time import sleep, time
from typing import IO, Any, TextIO, cast
from collections.abc import Iterable
from collections.abc import Callable

_osDir = tempfile.mkdtemp()
os.makedirs(os.path.join(_osDir, "lib/system"))
os.makedirs(os.path.join(_osDir, "bin"))
_ = atexit.register(shutil.rmtree, _osDir)
_ = shutil.copytree(
    "overlay/base/usr/lib/system/_os",
    os.path.join(_osDir, "lib/system/_os"),
)
_ = shutil.copytree(
    "overlay/atomic/usr/lib/system/_os",
    os.path.join(_osDir, "lib/system/_os"),
    dirs_exist_ok=True,
)
_ = shutil.copy2("overlay/base/usr/bin/os", os.path.join(_osDir, "bin/os"))
_ = shutil.copystat("overlay/base/usr/bin/os", os.path.join(_osDir, "bin/os"))
sys.path.append(os.path.join(_osDir, "lib/system"))

import _os  # noqa: E402 #pyright:ignore [reportMissingImports]
import _os.podman  # noqa: E402 #pyright:ignore [reportMissingImports]
import _os.system  # noqa: E402 #pyright:ignore [reportMissingImports]

podman = cast(Callable[..., None], _os.podman.podman)  # pyright:ignore [reportUnknownMemberType]
podman_cmd = cast(Callable[..., list[str]], _os.podman.podman_cmd)  # pyright:ignore [reportUnknownMemberType]
_execute = cast(Callable[..., int], _os.system._execute)  # pyright:ignore [reportUnknownMemberType]
execute = cast(Callable[..., None], _os.system.execute)  # pyright:ignore [reportUnknownMemberType]
execute_pipe = cast(Callable[..., None], _os.system.execute_pipe)  # pyright:ignore [reportUnknownMemberType]
chronic = cast(Callable[..., None], _os.system.chronic)  # pyright:ignore [reportUnknownMemberType]
in_system = cast(Callable[..., int], _os.podman.in_system)  # pyright:ignore [reportUnknownMemberType]
in_system_output = cast(Callable[..., bytes], _os.podman.in_system_output)  # pyright:ignore [reportUnknownMemberType]
is_root = cast(Callable[[], bool], _os.system.is_root)  # pyright:ignore [reportUnknownMemberType]
image_hash = cast(Callable[[str], str], _os.podman.image_hash)  # pyright:ignore [reportUnknownMemberType]
image_info = cast(Callable[[str, bool], dict[str, object]], _os.podman.image_info)  # pyright:ignore [reportUnknownMemberType]
image_labels = cast(Callable[[str, bool], dict[str, str]], _os.podman.image_labels)  # pyright:ignore [reportUnknownMemberType]
image_exists = cast(Callable[[str, bool, bool], bool], _os.podman.image_exists)  # pyright:ignore [reportUnknownMemberType]
image_tags = cast(Callable[[str, bool], list[str]], _os.podman.image_tags)  # pyright:ignore [reportUnknownMemberType]
hex_to_base62 = cast(Callable[[str], str], _os.podman.hex_to_base62)  # pyright:ignore [reportUnknownMemberType]
escape_label = cast(Callable[[str], str], _os.podman.escape_label)  # pyright: ignore[reportUnknownMemberType]
image_digest = cast(Callable[[str, bool], str], _os.podman.image_digest)  # pyright:ignore [reportUnknownMemberType]
image_qualified_name = cast(Callable[[str], str], _os.podman.image_qualified_name)  # pyright:ignore [reportUnknownMemberType]
base_images = cast(
    Callable[[str, dict[str, str] | None], Iterable[str]],
    _os.podman.base_images,  # pyright:ignore [reportUnknownMemberType]
)
image_name_parts = cast(
    Callable[[str], tuple[str | None, str, str | None, str | None]],
    _os.podman.image_name_parts,  # pyright:ignore [reportUnknownMemberType]
)
image_name_from_parts = cast(
    Callable[[str | None, str, str | None, str | None], str],
    _os.podman.image_name_from_parts,  # pyright:ignore [reportUnknownMemberType]
)
parse_containerfile = cast(
    Callable[[str | IO[str], dict[str, str] | None, bool], list[dict[str, Any]]],  # pyright: ignore[reportExplicitAny]
    _os.podman.parse_containerfile,  # pyright: ignore[reportUnknownMemberType]
)
bytes_to_stdout = cast(
    Callable[[bytes], None],
    _os.console.bytes_to_stdout,  # pyright: ignore[reportUnknownMemberType]
)
bytes_to_stderr = cast(
    Callable[[bytes], None],
    _os.console.bytes_to_stderr,  # pyright: ignore[reportUnknownMemberType]
)

IMAGE = cast(str, _os.IMAGE)
REGISTRY = cast(str, _os.REGISTRY)
REPO = cast(str, _os.REPO)
BUILDER = f"{REPO}-builder"


def ci_log(*args: str):
    import os

    if "CI" not in os.environ:
        return

    print(*args)


def base62_to_hex(base62_str: str) -> str:
    assert base62_str, "Invalid base62 string"
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    char_to_value = {char: idx for idx, char in enumerate(alphabet)}
    value = 0
    for char in base62_str:
        if char not in char_to_value:
            raise ValueError(f"Invalid Base62 character: '{char}'")
        value = value * 62 + char_to_value[char]

    hex_str = hex(value)[2:]
    assert hex_str, "Invalid base62 string"
    return hex_str


def progress_bar[T](
    iterable: list[T] | Iterable[T],
    count: int | None = None,
    prefix: str = "Progress: ",
    out: TextIO = sys.stdout,
    interval: int = 1,
):
    import os

    if count is None:
        count = len(iterable)  # pyright: ignore[reportArgumentType]

    if not count:
        return

    no_progress = "CI" in os.environ or not out.isatty()
    if no_progress and interval < 10:
        interval = 10

    current = 0

    def show():
        nonlocal current
        if current > count:
            current = count

        if no_progress:
            print(f"{prefix} {current}/{count}")
            return

        size = os.get_terminal_size().columns
        count_size = len(str(count))
        size -= len(prefix) + 4 + (count_size * 2) + 1
        if size < 2:
            print(f"{current}/{count}")
            return

        x = int(size * current / count)
        current_size = len(str(current))
        print(
            f"{prefix}[{'█' * x}{'.' * (size - x)}] {' ' * (count_size - current_size)}{current}/{count}",
            end="\r",
            file=out,
            flush=True,
        )

    _ = signal.signal(signal.SIGWINCH, lambda _, _b: show())
    show()
    last_update = 0.0
    for i, item in enumerate(iterable):
        yield item
        now = time()
        if now - last_update < interval and i < count - 1:
            continue

        last_update = now
        current = i + 1
        show()

    print(end="\n", file=out, flush=True)


_executor = ThreadPoolExecutor(max_workers=5)
_image_sizes: dict[str, Future[int]] = {}
_image_sizes_lock = threading.Lock()


def _image_size_cached(image: str) -> Future[int] | int:
    future = _image_sizes.get(image)
    if future is None:
        with _image_sizes_lock:
            # In case it was added after we locked
            future = _image_sizes.get(image)
            if future is None:
                future = _executor.submit(
                    cast(
                        Callable[[str], int],
                        _os.podman.image_size,  # pyright: ignore[reportUnknownMemberType]
                    ),
                    image,
                )
                _image_sizes[image] = future

    return future


def image_size_cached(image: str) -> int:
    future = _image_size_cached(image)
    if isinstance(future, Future):
        return future.result()

    return future


DIGEST_CACHE_PATH = os.path.join(os.environ.get("TMPDIR", "/tmp"), "manifest_cache")
_image_digests: dict[str, Future[str] | str] = {}
_image_digests_lock = threading.Lock()
_image_digests_write_lock = threading.Lock()
if os.path.exists(DIGEST_CACHE_PATH):
    with open(DIGEST_CACHE_PATH, "r") as f:
        try:
            data = json.load(f)  # pyright: ignore[reportAny]
            assert isinstance(data, dict)
            for image, digest in cast(dict[str, str], data).items():
                assert isinstance(image, str)
                assert isinstance(digest, str)
                _image_digests[image] = digest

        except Exception as e:
            print(f"Failed to load digest cache: {e}", file=sys.stderr)
            os.unlink(DIGEST_CACHE_PATH)

if not os.path.exists(DIGEST_CACHE_PATH):
    with open(DIGEST_CACHE_PATH, "w") as f:
        _ = f.write("{}")


def _remote_image_digest(image: str, skip_manifest: bool = False) -> str:
    e: Exception | None = None
    for attempt in range(10):
        assert image_exists(image, True, skip_manifest), (
            f"{image} does not exist on remote the server"
        )
        try:
            digest = image_digest(image, True)
            return digest

        except Exception as ex:
            e = ex
            if isinstance(e, subprocess.CalledProcessError) and e.returncode == 2:
                # Exit early, image cannot be found
                break

            sleep(1.0 * (2**attempt))  # pyright: ignore[reportAny]

    assert e is not None
    raise e


def _image_digest_cached(image: str, skip_manifest: bool = False) -> Future[str] | str:
    global _image_digests
    image = image_qualified_name(image)
    future = _image_digests.get(image, None)
    if future is None:
        with _image_digests_lock:
            # In case it was added after we locked
            future = _image_digests.get(image, None)
            if future is None:
                future = _executor.submit(_remote_image_digest, image, skip_manifest)
                _image_digests[image] = future

    return future


def _image_digests_write_cache(image: str, digest: str):
    global _image_digests
    with _image_digests_write_lock:
        image = image_qualified_name(image)
        if isinstance(_image_digests.get(image), str):
            return

        _image_digests[image] = digest
        with open(DIGEST_CACHE_PATH, "w+") as f:
            _ = f.seek(0)
            json.dump(
                {k: v for k, v in _image_digests.items() if isinstance(v, str)},
                f,
            )
            _ = f.truncate()
            _ = f.flush()


def image_digest_cached(image: str, skip_manifest: bool = False) -> str:
    global _image_digests
    future = _image_digest_cached(image, skip_manifest=skip_manifest)
    if not isinstance(future, Future):
        return future

    digest = future.result()
    _image_digests_write_cache(image, digest)
    return digest
