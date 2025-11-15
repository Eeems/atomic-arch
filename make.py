#!/usr/bin/env python
import argparse
from io import TextIOWrapper
import itertools
import signal
import sys
import shlex
import shutil
import os
import atexit
import re
import tempfile
import json
import threading

from collections import defaultdict
from collections import deque
from concurrent.futures import as_completed
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from glob import iglob
from hashlib import sha256
from time import sleep, time
from typing import IO, Any, TextIO, cast
from datetime import datetime
from datetime import UTC
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
chronic = cast(Callable[..., None], _os.system.chronic)  # pyright:ignore [reportUnknownMemberType]
in_system = cast(Callable[..., int], _os.podman.in_system)  # pyright:ignore [reportUnknownMemberType]
in_system_output = cast(Callable[..., bytes], _os.podman.in_system_output)  # pyright:ignore [reportUnknownMemberType]
is_root = cast(Callable[[], bool], _os.system.is_root)  # pyright:ignore [reportUnknownMemberType]
image_hash = cast(Callable[[str], str], _os.podman.image_hash)  # pyright:ignore [reportUnknownMemberType]
image_info = cast(Callable[[str, bool], dict[str, object]], _os.podman.image_info)  # pyright:ignore [reportUnknownMemberType]
image_labels = cast(Callable[[str, bool], dict[str, str]], _os.podman.image_labels)  # pyright:ignore [reportUnknownMemberType]
image_exists = cast(Callable[[str, bool], bool], _os.podman.image_exists)  # pyright:ignore [reportUnknownMemberType]
image_tags = cast(Callable[[str], list[str]], _os.podman.image_tags)  # pyright:ignore [reportUnknownMemberType]
create_delta = cast(Callable[[str, str, str, bool], bool], _os.podman.create_delta)  # pyright:ignore [reportUnknownMemberType]
hex_to_base62 = cast(Callable[[str], str], _os.podman.hex_to_base62)  # pyright:ignore [reportUnknownMemberType]
pull = cast(Callable[[str], None], _os.podman.pull)  # pyright:ignore [reportUnknownMemberType]
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

IMAGE = cast(str, _os.IMAGE)
REGISTRY = cast(str, _os.REGISTRY)
REPO = cast(str, _os.REPO)


def ci_log(*args: str):
    if "CI" not in os.environ:
        return

    print(*args)


def hash(target: str) -> str:
    m = sha256()
    containerfile = f"variants/{target}.Containerfile"
    if "-" in target and not os.path.exists(containerfile):
        base_variant, template = target.rsplit("-", 1)
        containerfile = f"templates/{template}.Containerfile"
        image = f"{REPO}:{base_variant}"
        labels = image_labels(image, not image_exists(image, False))
        m.update(labels["hash"].encode("utf-8"))

    with open(containerfile, "rb") as f:
        m.update(f.read())

    for file in sorted(iglob(f"overlay/{target}/**", recursive=True)):
        if os.path.isdir(file):
            m.update(file.encode("utf-8"))

        else:
            with open(file, "rb") as f:
                m.update(f.read())

    return m.hexdigest()


def build(target: str):
    now = datetime.now(UTC)
    uuid = f"{now.strftime('%H%M%S')}{int(now.microsecond / 10000)}"
    build_args: dict[str, str] = {"VERSION_ID": uuid, "HASH": hash(target)}
    containerfile = f"variants/{target}.Containerfile"
    if "-" in target and not os.path.exists(containerfile):
        base_variant, template = target.rsplit("-", 1)
        containerfile = f"templates/{template}.Containerfile"
        image = f"{REPO}:{base_variant}"
        labels = image_labels(image, not image_exists(image, False))
        build_args["BASE_VARIANT_ID"] = f"{base_variant}"
        build_args["VARIANT"] = f"{labels['os-release.VARIANT']} ({template})"
        build_args["VARIANT_ID"] = f"{labels['os-release.VARIANT_ID']}-{template}"
        build_args["MIRRORLIST"] = f"{labels['mirrorlist']}"
        build_args["VERSION"] = f"{labels['os-release.VERSION']}"
        build_args["VERSION_ID"] = f"{labels['os-release.VERSION_ID']}"
        build_args["NAME"] = f"{labels['os-release.NAME']}"
        build_args["PRETTY_NAME"] = f"{labels['os-release.PRETTY_NAME']}"
        build_args["ID"] = f"{labels['os-release.ID']}"
        build_args["HOME_URL"] = f"{labels['os-release.HOME_URL']}"
        build_args["BUG_REPORT_URL"] = f"{labels['os-release.BUG_REPORT_URL']}"
        if not image_exists(f"{REPO}:{base_variant}", False):
            pull(f"{REPO}:{base_variant}")

    for base_image in base_images(containerfile, build_args):
        print(f"Base image {base_image}")
        if not image_exists(base_image, False):
            pull(base_image)

    podman(
        "build",
        f"--tag={REPO}:{target}",
        *[f"--build-arg={k}={v}" for k, v in build_args.items()],
        "--force-rm",
        "--pull=never",
        "--volume=/var/cache/pacman:/var/cache/pacman",
        f"--file={containerfile}",
        "--format=docker",
        ".",
    )


def push(target: str):
    image = f"{REPO}:{target}"
    labels = image_labels(image, False)
    tags: list[str] = []
    # TODO handle when trying to push a versioned image
    if labels.get("os-release.VERSION", None):
        version = labels["os-release.VERSION"]
        version_id = labels.get("os-release.VERSION_ID", None)
        if version_id and version != version_id:
            tag = f"{image}_{version}.{version_id}"
            tags.append(tag)
            podman("tag", image, tag)

        tag = f"{image}_{version}"
        tags.append(tag)
        podman("tag", image, tag)

    for tag in tags + [image]:
        podman("push", tag)
        print(f"Pushed {tag}")
        _image_digests_write_cache(tag, image_digest(tag, False))

    if tags:
        podman("rmi", *tags)


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


def get_deltas(
    target: str, missing_only: bool = False
) -> Iterable[tuple[str, str, str]]:
    tags = image_tags(REPO)
    target_tags = [
        x
        for x in tags
        if x.startswith(f"{target}_")
        and (target == "rootfs" or len(x[len(target) + 1 :]) > 10)
    ]
    target_tags.sort()
    digest_cache = {
        tag: hex_to_base62(image_digest_cached(f"{REPO}:{tag}")) for tag in target_tags
    }
    diff_tags = (
        [
            x
            for x in tags
            if x.startswith("_diff-") and len(x) == (43 * 2) + 1 + 6 and x[49] == "-"
        ]
        if missing_only
        else []
    )
    for i in range(len(target_tags)):
        for offset in range(1, 4):
            if i + offset < len(target_tags):
                a, b = target_tags[i], target_tags[i + offset]
                if digest_cache[a] == digest_cache[b]:
                    continue

                t = f"_diff-{digest_cache[a]}-{digest_cache[b]}"
                if t not in diff_tags:
                    yield a, b, t


def delta(
    a: str, b: str, allow_pull: bool, push: bool, clean: bool, imageD: str | None = None
):
    imageA = f"{REPO}:{a}"
    imageB = f"{REPO}:{b}"
    if allow_pull:
        ci_log(f"::group::pull {imageA}")
        pull(imageA)
        ci_log("::endgroup::")
        ci_log(f"::group::pull {imageB}")
        pull(imageB)
        ci_log("::endgroup::")

    if imageD is None:
        digestA = hex_to_base62(image_digest(imageA, False))
        digestB = hex_to_base62(image_digest(imageB, False))
        assert digestA != digestB, "There is nothing to diff"
        imageD = f"{REPO}:_diff-{digestA}-{digestB}"

    ci_log(f"::group::delta {a} and {b}")
    _ = create_delta(imageA, imageB, imageD, allow_pull)
    ci_log("::endgroup::")
    if push:
        ci_log("::group::push")
        tries = 3
        while tries:
            podman("push", imageD)
            tries -= 1

        ci_log("::endgroup::")
        _image_digests_write_cache(imageD, image_digest(imageD, False))

    if not clean:
        return

    ci_log("::group::clean")
    podman("rmi", imageA, imageB)
    if push:
        podman("rmi", imageD)

    ci_log("::endgroup::")


def do_build(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        build(target)
        if cast(bool, args.push):
            push(target)


def do_iso(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        image = f"{REPO}:{target}"
        _ = in_system("build", target=image, check=True)
        _ = in_system(
            "iso",
            *([] if cast(bool, args.localImage) else ["--no-local-image"]),
            check=True,
        )


def do_rootfs(args: argparse.Namespace):
    noBuild = cast(bool, args.noBuild)
    doPush = cast(bool, args.push)
    if noBuild and doPush:
        print("You cannot push without also building")
        sys.exit(1)

    if not is_root() and not noBuild:
        print("Must be run as root")
        sys.exit(1)

    containerfile = "variants/rootfs.Containerfile"
    with open(containerfile, "r") as f:
        lines = f.readlines()

    config = {
        x[0]: x[1]
        for x in [
            x.rstrip().split(" ", 1)[1].split("=", 1)
            for x in lines
            if x.startswith("ARG ARCHIVE_YEAR=")
            or x.startswith("ARG ARCHIVE_MONTH=")
            or x.startswith("ARG ARCHIVE_DAY=")
            or x.startswith("ARG PACSTRAP_TAG=")
        ]
    }

    year = cast(str | None, args.year) or config["ARCHIVE_YEAR"]
    month = cast(str | None, args.month) or config["ARCHIVE_MONTH"]
    day = cast(str | None, args.day) or config["ARCHIVE_DAY"]
    tag = cast(str | None, args.tag) or config["PACSTRAP_TAG"]

    with open(containerfile, "w") as f:
        for line in lines:
            if line.startswith("ARG ARCHIVE_YEAR="):
                line = f"ARG ARCHIVE_YEAR={year}\n"

            elif line.startswith("ARG ARCHIVE_MONTH="):
                line = f"ARG ARCHIVE_MONTH={month}\n"

            elif line.startswith("ARG ARCHIVE_DAY="):
                line = f"ARG ARCHIVE_DAY={day}\n"

            elif line.startswith("ARG PACSTRAP_TAG="):
                line = f"ARG PACSTRAP_TAG={tag}\n"

            _ = f.write(line)

    if noBuild:
        return

    build("rootfs")
    if doPush:
        push("rootfs")


def do_push(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        push(target)


def do_run(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    ret = in_system(
        "-c",
        shlex.join(cast(list[str], args.arg)),
        target=f"{REPO}:{cast(str, args.target)}",
        entrypoint="/bin/bash",
    )
    if ret:
        sys.exit(ret)


def do_pull(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        pull(f"{REPO}:{target}")


def do_os(args: argparse.Namespace):
    ret = _execute(
        shlex.join([os.path.join(_osDir, "bin/os"), *cast(list[str], args.arg)])
    )
    if ret:
        sys.exit(ret)


def do_scan(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    os.makedirs(".trivy", exist_ok=True)
    volumes: list[str] = ["./.trivy:/trivy"]
    in_ci = "CI" in os.environ
    if in_ci:
        volumes.append("./markdown.tpl:/template")

    ret = in_system(
        "-c",
        f"""
        set -e
        /usr/lib/system/initialize_pacman
        /usr/lib/system/install_packages trivy
        if [[ "{"x" if in_ci else ""}" == "" ]]; then
            trivy rootfs \
                --cache-dir /trivy \
                --skip-dirs=/ostree \
                --skip-dirs=/sysroot \
                --skip-dirs=/var/lib/system \
                --skip-dirs=/usr/share/doc \
                --skip-dirs=/usr/share/man \
                --skip-dirs=/trivy \
                --skip-files=/usr/bin/trivy \
                --skip-files=/usr/lib/qt6/mkspecs/features/data/testserver/Dockerfile \
                --scanners vuln,misconfig,secret \
                /
        else
            trivy rootfs \
                --cache-dir /trivy \
                --format json \
                --output /trivy/report.json \
                --skip-dirs=/ostree \
                --skip-dirs=/sysroot \
                --skip-dirs=/var/lib/system \
                --skip-dirs=/usr/share/doc \
                --skip-dirs=/usr/share/man \
                --skip-dirs=/trivy \
                --skip-files=/usr/bin/trivy \
                --skip-files=/usr/lib/qt6/mkspecs/features/data/testserver/Dockerfile \
                --scanners vuln,misconfig,secret \
                /
            trivy convert \
                --format sarif \
                /trivy/report.json \
            > /trivy/report.sarif
            trivy convert \
                --format template \
                --template "@/template" \
                /trivy/report.json \
            > /trivy/report.md
            trivy convert \
                --format table \
                /trivy/report.json
        fi
        """,
        target=f"{REPO}:{cast(str, args.target)}",
        entrypoint="/bin/bash",
        volumes=volumes,
    )
    if ret:
        sys.exit(ret)


def do_checkupdates(args: argparse.Namespace):
    import requests

    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    target = cast(str, args.target)
    image = image_qualified_name(f"{REPO}:{target}")
    exists = image_exists(image, True)
    if exists:
        mirror = [
            x.split(" = ", 1)[1]
            for x in in_system_output(
                "cat",
                "/etc/pacman.d/mirrorlist",
                entrypoint="",
                target=image,
            )
            .decode("utf-8")
            .splitlines()
        ][0]

    else:
        mirror = "https://archive.archlinux.org/repos/2025/11/06/$repo/os/$arch"

    m = re.match(r"^(.+)\/(\d{4}\/\d{2}\/\d{2})\/\$repo\/os\/\$arch$", mirror)
    assert m
    current = m.group(2)
    now = datetime.now()
    new = f"{now.year}/{now.strftime('%m')}/{now.strftime('%d')}"
    has_updates = False
    if current != new:
        url = f"{m.group(1)}/{new}/"
        res = requests.head(url)
        if res.status_code == 200:
            print(f"mirrorlist {current} -> {new}")
            has_updates = True

        elif res.status_code != 404:
            print(res.reason)
            sys.exit(1)

    new_hash = hash(target)
    current_hash = image_hash(image) if exists else ""
    if current_hash != new_hash:
        print(f"context {current_hash[:9] or '(none)'} -> {new_hash[:9]}")
        has_updates = True

    if not exists:
        sys.exit(2)

    res = in_system(
        "-ec",
        " ".join(
            [
                "if [ -f /usr/bin/chronic ]; then",
                "  /usr/bin/chronic /usr/lib/system/initialize_pacman;",
                "else",
                "  /usr/lib/system/initialize_pacman > /dev/null;",
                "fi;",
                "if [ -f /usr/bin/checkupdates ];then",
                "  /usr/bin/checkupdates;",
                "fi",
            ]
        ),
        entrypoint="/bin/bash",
        target=image,
    )
    if res == 1:
        sys.exit(1)

    elif res == 2:
        has_updates = True

    if has_updates:
        sys.exit(2)


def do_check(args: argparse.Namespace):
    failed = False
    fix = cast(bool, args.fix)

    def _assert_name(name: str, expected: str) -> bool:
        image = image_qualified_name(name)
        if image == expected:
            return True

        print(f" Failed: image_qualified_name({json.dumps(name)})")
        print(f"  Expected: {json.dumps(expected)}")
        print(f"  Actual: {json.dumps(image)}")
        return False

    print("[check] Running tests")
    failed = failed or not _assert_name(
        "hello-world:latest@sha256:123",
        "docker.io/hello-world@sha256:123",
    )
    failed = failed or not _assert_name(
        "hello-world@sha256:123",
        "docker.io/hello-world@sha256:123",
    )
    failed = failed or not _assert_name(
        "hello-world:latest",
        "docker.io/hello-world:latest",
    )
    failed = failed or not _assert_name(
        "hello-world:latest",
        "docker.io/hello-world:latest",
    )
    failed = failed or not _assert_name("hello-world", "docker.io/hello-world")
    failed = failed or not _assert_name("system:latest", "localhost/system:latest")
    failed = failed or not _assert_name(
        f"{REPO}:latest@sha256:123",
        f"{REPO}@sha256:123",
    )
    failed = failed or not _assert_name(f"{REPO}:latest", f"{REPO}:latest")
    failed = failed or not _assert_name(f"{REPO}@sha256:123", f"{REPO}@sha256:123")
    failed = failed or not _assert_name(REPO, REPO)
    failed = failed or not _assert_name(
        f"{IMAGE}:latest@sha256:123",
        f"{REPO}@sha256:123",
    )
    failed = failed or not _assert_name(f"{IMAGE}:latest", f"{REPO}:latest")
    failed = failed or not _assert_name(IMAGE, REPO)
    if shutil.which("niri") is not None:
        print("[check] Checking niri config", file=sys.stderr)
        cmd = shlex.join(
            [
                "niri",
                "validate",
                "--config=overlay/atomic/usr/share/niri/config.kdl",
            ]
        )
        res = _execute(cmd)
        if res:
            print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
            failed = True

    if shutil.which("gofmt") is not None:
        print("[check] Checking go formatting", file=sys.stderr)
        cmd = shlex.join(
            ["gofmt", "-e"]
            + (["-w", "-l"] if fix else ["-d"])
            + ["tools/dockerfile2llbjson"]
        )
        res = _execute(cmd)
        if res:
            print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
            failed = True

    if shutil.which("go") is not None:
        cwd = os.getcwd()
        print("[check] Analyzing go code", file=sys.stderr)
        cmd = shlex.join(["go", "vet"])
        os.chdir("tools/dockerfile2llbjson")
        res = _execute(cmd)
        os.chdir(cwd)
        if res:
            print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
            failed = True

    if not os.path.exists(".venv/bin/activate"):
        chronic("python", "-m", "venv", ".venv")

    chronic(
        "bash",
        "-ec",
        ";".join(
            [
                "source .venv/bin/activate",
                "pip install "
                + " ".join(
                    [
                        "ruff",
                        "basedpyright",
                        "requests",
                        "dbus-python",
                        "PyGObject",
                        "xattr",
                    ]
                ),
            ]
        ),
    )
    cmd = shlex.join(
        [
            "bash",
            "-ec",
            ";".join(
                [
                    "source .venv/bin/activate",
                    f"ruff check {'--fix' if fix else ''} .",
                ]
            ),
        ]
    )
    print("[check] Checking python formatting", file=sys.stderr)
    res = _execute(cmd)
    if res:
        print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
        failed = True

    cmd = shlex.join(
        [
            "bash",
            "-ec",
            ";".join(
                [
                    "source .venv/bin/activate",
                    shlex.join(
                        [
                            "basedpyright",
                            "--pythonversion=3.12",
                            "--pythonplatform=Linux",
                            "--venvpath=.venv",
                            "make.py",
                            f"{_osDir}",
                        ]
                    ),
                ]
            ),
        ]
    )
    print("[check] Checking python types", file=sys.stderr)
    res = _execute(cmd)
    if res:
        print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
        failed = True

    if failed:
        print("[check] One or more checks failed", file=sys.stderr)
        sys.exit(1)

    print("[check] All checks passed", file=sys.stderr)


def do_inspect(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    remote = cast(bool, args.remote)
    print(
        json.dumps(
            {x: image_info(f"{REPO}:{x}", remote) for x in cast(list[str], args.target)}
        )
    )


def do_hash(args: argparse.Namespace):
    for target in cast(list[str], args.target):
        print(f"{target}: {hash(target)[:9]}")


def do_delta(args: argparse.Namespace):
    push = cast(bool, args.push)
    pull = cast(bool, args.pull)
    clean = cast(bool, args.clean)
    targets = cast(list[str], args.target)
    if cast(bool, args.explicit):
        if len(targets) != 2:
            print("When --explicit is set, you must specify two explicit tags")
            sys.exit(1)

        imageA, imageB = targets
        delta(imageA, imageB, pull, push, clean)
        return

    missing_only = not cast(bool, args.force)
    for target in targets:
        for a, b, t in get_deltas(target, missing_only=missing_only):
            delta(a, b, pull, push, clean, imageD=t)


def do_get_deltas(args: argparse.Namespace):
    missing_only = cast(bool, args.missing)
    output_json = cast(bool, args.json)
    targets = cast(list[str], args.target)
    tags = [
        {"a": a, "b": b, "tag": tag}
        for target in targets
        for a, b, tag in get_deltas(target, missing_only=missing_only)
    ]
    if output_json:
        print(json.dumps(tags))
        return

    for item in tags:
        print(item["tag"])


def progress_bar[T](
    iterable: list[T] | Iterable[T],
    count: int | None = None,
    prefix: str = "Progress: ",
    out: TextIO = sys.stdout,
    interval: int = 1,
):
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


def _classify_tag(tag: str) -> tuple[str, str | None, str | None]:
    if tag == "_manifest":
        return "other", None, None

    if tag.startswith("_diff-"):
        if len(tag) == 49 or tag[48] != "-":
            return "other", None, None

        src_b62 = tag[6:49]
        dst_b62 = tag[49:]
        if len(src_b62) != 43 or len(dst_b62) != 43:
            return "other", None, None

        return "diff", src_b62, dst_b62

    if "_" not in tag:
        if all(c.isalnum() or c == "-" for c in tag):
            return "variant", tag, None

        return "other", None, None

    sep_idx = tag.rfind("_")
    if sep_idx <= 0:
        return "other", None, None

    variant = tag[:sep_idx]
    rest = tag[sep_idx + 1 :]
    if not (variant and all(c.isalnum() or c == "-" for c in variant)):
        return "other", None, None

    if "." in rest:
        last_dot = rest.rfind(".")
        if last_dot > 0:
            build_num = rest[last_dot + 1 :]
            if build_num.isdigit():
                version_part = rest[:last_dot]
                full_version = f"{version_part}.{build_num}"
                return "build", variant, full_version

    if rest and all(c.isalnum() or c in ".-" for c in rest):
        return "versioned", variant, rest

    return "other", None, None


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


def _remote_image_digest(image: str) -> str:
    e: Exception | None = None
    for attempt in range(10):
        try:
            digest = image_digest(image, True)
            return digest

        except Exception as ex:
            e = ex
            sleep(1.0 * (2**attempt))  # pyright: ignore[reportAny]

    assert e is not None
    raise e


def _image_digest_cached(image: str) -> Future[str] | str:
    global _image_digests
    image = image_qualified_name(image)
    future = _image_digests.get(image, None)
    if future is None:
        with _image_digests_lock:
            # In case it was added after we locked
            future = _image_digests.get(image, None)
            if future is None:
                future = _executor.submit(_remote_image_digest, image)
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


def image_digest_cached(image: str) -> str:
    global _image_digests
    future = _image_digest_cached(image)
    if not isinstance(future, Future):
        return future

    digest = future.result()
    _image_digests_write_cache(image, digest)
    return digest


def shortest_path(
    a: str, b: str, graph: dict[str, dict[str, tuple[str, int]]]
) -> tuple[int | None, list[str] | None]:
    if a == b:
        return 0, []

    queue = deque([(a, 0, cast(list[str], []))])
    visited: dict[str, tuple[int, list[str]]] = {a: (0, [])}
    while queue:
        node, cost, path = queue.popleft()
        for neigh, (tag, sz) in graph.get(node, {}).items():
            if sz == -1:
                continue

            new_cost = cost + sz
            if neigh not in visited or new_cost < visited[neigh][0]:
                visited[neigh] = (new_cost, path + [tag])
                queue.append((neigh, new_cost, path + [tag]))

    return visited.get(b, (None, None))


def do_manifest(args: argparse.Namespace):
    print("Getting all tags...")
    all_tags = image_tags(REPO)
    assert all_tags, "No tags found"
    digest_info: dict[str, tuple[list[str], str]] = {}
    graph: defaultdict[str, dict[str, tuple[str, int]]] = defaultdict(dict)
    to_classify: list[tuple[str, str]] = []
    for tag in progress_bar(
        all_tags,
        prefix="Classifying tags:" + " " * 9,
    ):
        kind, a, b = _classify_tag(tag)
        if kind == "other":
            continue

        if kind != "diff":
            to_classify.append((kind, tag))
            continue

        if a and b:
            graph[a][b] = (tag, -1)

    assert to_classify, "No tags found"

    # TODO filter out tags that aren't part of the config

    def _digest_worker(data: tuple[str, str]) -> tuple[str, str, Future[str] | str]:
        image = f"{REPO}:{data[1]}"
        future = _image_digest_cached(image)
        if isinstance(future, Future):
            future.add_done_callback(
                lambda x: _image_digests_write_cache(image, x.result())
            )

        return *data, future

    with ThreadPoolExecutor(max_workers=50) as exc:
        for future in progress_bar(
            as_completed([exc.submit(_digest_worker, x) for x in to_classify]),
            count=len(to_classify),
            prefix="Processing tags:" + " " * 10,
        ):
            kind, tag, digest = future.result()
            if isinstance(digest, Future):
                digest = digest.result()

            b62 = hex_to_base62(digest)
            if b62 not in digest_info:
                digest_info[b62] = ([], digest)

            digest_info[b62] = (digest_info[b62][0] + [tag], digest)

    def flatten(
        d: dict[str, dict[str, tuple[str, int]]],
    ) -> Iterable[tuple[dict[str, tuple[str, int]], str, tuple[str, int]]]:
        for _, inner_dict in d.items():
            for key, value in inner_dict.items():
                yield inner_dict, key, value

    for d, key, (tag, _size) in progress_bar(
        flatten(graph),
        count=len(list(flatten(graph))),
        prefix="Calculating sizes:" + " " * 8,
    ):
        d[key] = (tag, image_size_cached(f"{REPO}:{tag}"))

    labels: dict[str, str] = {}
    for b62, (tags, digest) in progress_bar(
        digest_info.items(), prefix="Generating tag labels:" + " " * 4
    ):
        for tag in tags:
            labels[f"tag.{tag}"] = digest

    b62_list = list(digest_info.keys())
    delta_map: defaultdict[str, dict[str, list[str]]] = defaultdict(dict)

    def _delta_worker(data: tuple[str, str]) -> tuple[str, str, int, list[str]] | None:
        a_b62, b_b62 = data
        cost, path = shortest_path(a_b62, b_b62, graph)
        if cost is None or not path:
            return None

        return b_b62, a_b62, cost, path

    with ThreadPoolExecutor(max_workers=50) as exc:
        combinations = list(itertools.combinations(b62_list, 2))
        for future in progress_bar(
            as_completed([exc.submit(_delta_worker, x) for x in combinations]),
            count=len(combinations),
            prefix="Calculating deltas:" + " " * 7,
        ):
            item = future.result()
            if item is None:
                continue

            b_b62, a_b62, cost, path = item
            sizes = [
                x
                for t in digest_info[b_b62][0]
                for x in [_image_size_cached(f"{REPO}:{t}")]
            ]
            b_direct: int = min(
                [x for x in sizes if not isinstance(x, Future)]
                + cast(
                    list[int],
                    list(as_completed([x for x in sizes if isinstance(x, Future)])),
                ),
            )
            if cost < b_direct * 0.9:
                continue

            delta_map[b_b62][a_b62] = path

    for b_b62, item in progress_bar(
        delta_map.items(),
        prefix="Generating map labels:" + " " * 4,
    ):
        labels[f"map.{b_b62}"] = json.dumps(item, separators=(",", ":"), indent=2)

    labels["timestamp"] = datetime.now(tz=UTC).replace(microsecond=0).isoformat() + "Z"
    with tempfile.TemporaryDirectory() as tmpdir:
        containerfile = os.path.join(tmpdir, "Containerfile")
        with open(containerfile, "w") as f:
            _ = f.write("FROM scratch\nLABEL \\")
            for k, v in progress_bar(
                labels.items(), prefix="Generating Containerfile: "
            ):
                _ = f.write(f'\n  atomic.manifest.{k}="{escape_label(v)}" \\')

            _ = f.write('\n  atomic.manifest.version="1"\n')

        image = f"{REPO}:_manifest"
        print(f"Building {image}...")
        try:
            chronic(
                podman_cmd(
                    "build",
                    f"--tag={image}",
                    f"--file={containerfile}",
                    tmpdir,
                )
            )

        except:
            with (
                open(containerfile, "r") as f,
                open("/tmp/manifest.Containerfile", "w") as out,
            ):
                _ = out.write(f.read())

            raise
        if cast(bool, args.push):
            podman("push", image)


type ConfigItem = dict[str, str | None | list[str] | bool]
type Config = dict[str, dict[str, ConfigItem]]


def _get_config_data(
    lines: list[str], prefix: str, multiple: bool = False
) -> list[str] | str | None:
    data = [x[len(prefix) :] for x in lines if x.startswith(prefix)]
    assert len(data) < 2
    if not data:
        return None if not multiple else []

    data = data[0]
    if not multiple:
        return data

    return [x.strip() for x in data.split(",")]


def parse_config(containerfile: str) -> tuple[str, ConfigItem]:
    filename = os.path.basename(containerfile)
    assert filename.endswith(".Containerfile")
    with open(containerfile, "r") as f:
        lines = f.read().splitlines()

    config: ConfigItem = {}
    depends = cast(str | None, _get_config_data(lines, "# x-depends="))
    if depends is not None:
        config["depends"] = depends

    templates = cast(
        str | None, _get_config_data(lines, "# x-templates=", multiple=True)
    )
    if templates is not None:
        config["templates"] = templates

    # TODO sort out how to set clean property in a way so it's only for
    #      one template if it's set for a template
    return filename[:-14], config


def parse_all_config() -> Config:
    return {
        "variants": {
            k: v
            for x in iglob("variants/*.Containerfile")
            for k, v in [parse_config(x)]
            if k != "rootfs"
        }
    }


type Graph = dict[str, dict[str, str | list[str] | None | bool]]
type Indegree = dict[str, int]


def do_workflow(_: argparse.Namespace):
    config: Config = parse_all_config()

    def build_job_graph(config: Config) -> tuple[Graph, Indegree]:
        graph: Graph = {
            "rootfs": {
                "depends": "check",
                "cleanup": False,
            }
        }
        indegree: Indegree = {"rootfs": 0}
        for variant, data in cast(
            dict[str, dict[str, str | None | list[str]]], config["variants"]
        ).items():
            if variant in ("check", "rootfs"):
                raise ValueError(f"Invalid use of protected variant name: {variant}")

            graph[variant] = {
                "depends": data.get("depends", None) or "rootfs",
                "cleanup": False,
            }
            indegree[variant] = 0
            for template in cast(list[str], data["templates"]):
                full_id = f"{variant}-{template}"
                graph[full_id] = {
                    "depends": (
                        f"{variant}-{template.rsplit('-', 1)[0]}"
                        if "-" in template
                        else variant
                    ),
                    "cleanup": cast(bool, data.get("clean", False)),
                }
                indegree[full_id] = 0

        for job_id, data in graph.items():
            depends = data["depends"]
            if job_id == "rootfs":
                continue

            indegree[job_id] += 1
            if depends not in graph:
                raise RuntimeError(f"{job_id} cannot find dependency {depends}")

        return graph, indegree

    def topological_sort(graph: Graph, indegree: Indegree) -> list[str]:
        queue = deque(sorted([job for job, deg in indegree.items() if deg == 0]))
        order: list[str] = []
        while queue:
            job = queue.popleft()
            order.append(job)
            for dep_job, data in graph.items():
                if data["depends"] != job:
                    continue

                indegree[dep_job] -= 1
                if indegree[dep_job] == 0:
                    queue.append(dep_job)

        if len(order) != len(graph):
            raise RuntimeError("Cycle detected in job dependencies")

        return order

    graph, indegree = build_job_graph(config)

    def indent(lines: list[str], level: int = 1) -> list[str]:
        return [
            (("  " * level) + line).rstrip() if line.strip() else "" for line in lines
        ]

    def comment(title: str) -> list[str]:
        return [
            "  ######################################",
            f"  #             {title:<19}#",
            "  ######################################",
        ]

    def render_build(job_id: str) -> list[str]:
        d = graph[job_id]
        depends = d["depends"]
        lines = [
            f"{job_id}:",
            f"  name: Build atomic-arch:{job_id} image",
            f"  needs: {depends}",
            "  uses: ./.github/workflows/build-variant.yaml",
            "  secrets: inherit",
            "  permissions: *permissions",
            "  with:",
            f"    variant: {job_id}",
        ]
        if job_id == "rootfs":
            lines.append("    push: true")

        else:
            lines += [
                f"    updates: ${{{{ fromJson(needs['{depends}'].outputs.updates) }}}}",
                "    push: ${{ github.event_name != 'pull_request' }}",
                f"    artifact: {depends}",
                f"    digest: ${{{{ needs['{depends}'].outputs.digest }}}}",
            ]

        if d["cleanup"]:
            lines.append("    cleanup: true")

        return indent(lines)

    def render_delta(job_id: str) -> list[str]:
        return indent(
            [
                f"delta_{job_id}:",
                f"  name: Generate deltas for {job_id}",
                "  if: github.event_name != 'pull_request'",
                f"  needs: {job_id}",
                "  uses: ./.github/workflows/delta.yaml",
                "  secrets: inherit",
                "  permissions: *permissions",
                "  with:",
                f"    variant: {job_id}",
                "    push: ${{ github.event_name != 'pull_request' }}",
                "    recreate: false",
            ]
        )

    def render_scan(job_id: str) -> list[str]:
        return indent(
            [
                f"scan_{job_id}:",
                f"  name: Scan image for {job_id}",
                f"  if: github.event_name != 'pull_request' || fromJson(needs['{job_id}'].outputs.updates)",
                f"  needs: {job_id}",
                "  uses: ./.github/workflows/scan.yaml",
                "  secrets: inherit",
                "  permissions: *permissions",
                "  with:",
                f"    variant: {job_id}",
                "    push: ${{ github.event_name != 'pull_request' }}",
                f"    artifact: ${{{{ fromJson(needs['{job_id}'].outputs.updates) && '{job_id}' || '' }}}}",
                f"    digest: ${{{{ needs['{job_id}'].outputs.digest }}}}",
            ]
        )

    def render_iso(job_id: str) -> list[str]:
        def __(offline: bool):
            return [
                f"{'offline' if offline else 'online'}_iso_{job_id}:",
                f"  name: Generate iso for {job_id}",
                f"  needs: {job_id}",
                "  uses: ./.github/workflows/iso.yaml",
                "  secrets: inherit",
                "  permissions: *permissions",
                "  with:",
                f"    variant: {job_id}",
                f"    pull: ${{{{ github.event_name != 'pull_request' && fromJson(needs['{job_id}'].outputs.updates) }}}}",
                f"    offline: {json.dumps(offline)}",
            ]

        return indent(__(False) + [""] + __(True))

    build_order = topological_sort(graph, indegree)

    sections = [
        [
            "#########################################",
            "# THIS FILE IS DYNAMICALLY GENERATED    #",
            "# Run the following to update the file: #",
            "#   $ ./make.py workflow                #",
            "#########################################",
            "name: Build images",
            "on:",
            "  pull_request: &on-filter",
            "    branches:",
            "      - master",
            "    paths:",
            "      - .github/workflows/build.yaml",
            "      - .github/workflows/build-variant.yaml",
            "      - .github/workflows/delta.yaml",
            "      - .github/workflows/iso.yaml",
            "      - .github/workflows/manifest.yaml",
            "      - .github/workflows/sync.yaml",
            '      - ".github/actions/**"',
            "      - make.py",
            "      - seccomp.json",
            "      - .containerignore",
            '      - "overlay/**"',
            '      - "templates/**"',
            '      - "variants/**"',
            "  push: *on-filter",
            "  workflow_dispatch:",
            "  schedule:",
            '    - cron: "0 23 * * *"',
            "",
            "concurrency:",
            "  group: build-${{ github.ref_name }}",
            "  cancel-in-progress: true",
            "",
            "jobs:",
        ],
        comment("UNIQUE"),
        indent(
            [
                "notifications:",
                "  name: Clear notifications",
                "  runs-on: ubuntu-latest",
                "  steps:",
                "    - name: Checkout the repository",
                "      uses: actions/checkout@v4",
                "    - name: Clean cancellation notifications",
                "      uses: ./.github/actions/clean-cancelled-notifications",
                "      with:",
                "        pat: ${{ secrets.NOTIFICATION_PAT }}",
                "",
                "wait:",
                "  name: Wait for builder to finish",
                "  runs-on: ubuntu-latest",
                "  permissions:",
                "    contents: read",
                "    actions: read",
                "  steps:",
                "    - name: Wait",
                "      uses: NathanFirmo/wait-for-other-action@8241e29ea2e9661a8af6d319b1d074825a299730",
                "      with:",
                "        token: ${{ github.token }}",
                "        workflow: 'tool-builder.yaml'",
                "",
                "check:",
                "  name: Ensure config is valid",
                "  runs-on: ubuntu-latest",
                "  needs: wait",
                "  permissions:",
                "    contents: read",
                "    packages: read",
                "  container:",
                "    image: ghcr.io/eeems/atomic-arch-builder:latest",
                "    options: >-",
                "      --privileged",
                "      --security-opt seccomp=unconfined",
                "      --security-opt apparmor=unconfined",
                "      --cap-add=SYS_ADMIN",
                "      --cap-add=NET_ADMIN",
                "      --device /dev/fuse",
                "      --tmpfs /tmp",
                "      --tmpfs /run",
                "      --userns=host",
                "      -v /var/lib/containers:/var/lib/containers",
                "      -v /:/run/host",
                "  steps:",
                "    - name: Checkout the repository",
                "      uses: actions/checkout@v4",
                "    - name: Cache venv",
                "      uses: actions/cache@v4",
                "      with:",
                "        path: .venv",
                "        key: venv-${{ hashFiles('.github/workflows/Dockerfile.builder') }}-${{ hashFiles('make.py') }}",
                "    - name: Cache go",
                "      uses: actions/cache@v4",
                "      with:",
                "        path: |",
                "          ~/go/pkg/mod",
                "          ~/.cache/go-build",
                "        key: go-${{ hashFiles('**/go.mod') }}-${{ hashFiles('**/go.sum') }}",
                "    - name: Ensure config is valid",
                "      run: |",
                "        set -e",
                "        ./make.py check",
                "        ./make.py workflow",
                '        if [[ -n "$(git status -s)" ]]; then',
                '          echo "Please run ./make.py workflow, commit the changes, and try again."',
                "          exit 1",
                "        fi",
                "      env:",
                "        TMPDIR: ${{ runner.temp }}",
                "",
                "manifest:",
                "  name: Generate manifest",
                '  if: "!cancelled()"',
                "  needs:",
                *[f"    - delta_{j}" for j in sorted(build_order)],
                "  uses: ./.github/workflows/manifest.yaml",
                "  secrets: inherit",
                "  permissions: &permissions",
                "    contents: write",
                "    actions: write",
                "    packages: write",
                "    security-events: write",
                "  with:",
                "    cache: false",
                "",
                "sync:",
                "  if: always()",
                "  name: Sync repositories",
                "  needs: manifest",
                "  uses: ./.github/workflows/sync.yaml",
                "  secrets: inherit",
                "  permissions: *permissions",
            ]
        ),
        comment("BUILD"),
        *[render_build(j) for j in build_order],
        comment("SCAN"),
        *[render_scan(j) for j in build_order],
        comment("DELTA"),
        *[render_delta(j) for j in build_order],
        comment("ISO"),
        *[render_iso(j) for j in build_order if j != "rootfs"],
    ]

    output: list[str] = []
    for i, sec in enumerate(sections):
        output.extend(sec)
        if i < len(sections) - 1:
            output.append("")

    with open(".github/workflows/build.yaml", "w") as f:
        _r = f.write("\n".join(output).rstrip() + "\n")


def do_config(_: argparse.Namespace):
    print(json.dumps(parse_all_config()))


def do_parse_containerfile(args: argparse.Namespace):
    print(
        json.dumps(
            parse_containerfile(
                cast(TextIOWrapper, args.file),
                {
                    k: v
                    for x in cast(list[str], args.build_arg or [])
                    for k, v in [x.split("=", 1)]
                },
                cast(bool, args.pretty),
            ),
            indent=2 if cast(bool, args.pretty) else None,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    subparsers = parser.add_subparsers()

    subparser = subparsers.add_parser("build")
    _ = subparser.add_argument("--push", action="store_true")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_build)

    subparser = subparsers.add_parser("iso")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    _ = subparser.add_argument(
        "--no-local-image",
        help="If the image should be copied to the iso container storage",
        dest="localImage",
        action="store_false",
    )
    subparser.set_defaults(func=do_iso)

    subparser = subparsers.add_parser("rootfs")
    now = datetime.now()
    _ = subparser.add_argument("--year", default=now.year)
    _ = subparser.add_argument("--month", default=now.strftime("%m"))
    _ = subparser.add_argument("--day", default=now.strftime("%d"))
    _ = subparser.add_argument("--tag", default=None)
    _ = subparser.add_argument("--no-build", action="store_true", dest="noBuild")
    _ = subparser.add_argument("--push", action="store_true")
    subparser.set_defaults(func=do_rootfs)

    subparser = subparsers.add_parser("push")
    _ = subparser.add_argument("target", action="extend", nargs="+", type=str)
    subparser.set_defaults(func=do_push)

    subparser = subparsers.add_parser("pull")
    _ = subparser.add_argument("target", action="extend", nargs="+", type=str)
    subparser.set_defaults(func=do_pull)

    subparser = subparsers.add_parser("run")
    _ = subparser.add_argument("--target", default="base")
    _ = subparser.add_argument("arg", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_run)

    subparser = subparsers.add_parser("os")
    _ = subparser.add_argument("--target", default="base")
    _ = subparser.add_argument("arg", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_os)

    subparser = subparsers.add_parser("scan")
    _ = subparser.add_argument("target")
    subparser.set_defaults(func=do_scan)

    subparser = subparsers.add_parser("checkupdates")
    _ = subparser.add_argument("--target", default="rootfs")
    subparser.set_defaults(func=do_checkupdates)

    subparser = subparsers.add_parser("check")
    _ = subparser.add_argument("--fix", action="store_true")
    subparser.set_defaults(func=do_check)

    subparser = subparsers.add_parser("inspect")
    _ = subparser.add_argument("--remote", action="store_true")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_inspect)

    subparser = subparsers.add_parser("hash")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_hash)

    subparser = subparsers.add_parser("get-deltas")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    _ = subparser.add_argument("--missing", action="store_true")
    _ = subparser.add_argument("--json", action="store_true")
    subparser.set_defaults(func=do_get_deltas)

    subparser = subparsers.add_parser("delta")
    _ = subparser.add_argument("target", action="extend", nargs="+", type=str)
    _ = subparser.add_argument("--push", action="store_true")
    _ = subparser.add_argument("--no-pull", action="store_false", dest="pull")
    _ = subparser.add_argument("--no-clean", action="store_false", dest="clean")
    _ = subparser.add_argument("--explicit", action="store_true")
    _ = subparser.add_argument("--force", action="store_true")
    subparser.set_defaults(func=do_delta)

    subparser = subparsers.add_parser("manifest")
    _ = subparser.add_argument("--push", action="store_true")
    subparser.set_defaults(func=do_manifest)

    subparser = subparsers.add_parser("workflow")
    subparser.set_defaults(func=do_workflow)

    subparser = subparsers.add_parser("config")
    subparser.set_defaults(func=do_config)

    subparser = subparsers.add_parser("parse-containerfile")
    _ = subparser.add_argument("--pretty", action="store_true")
    _ = subparser.add_argument("--build_arg", action="extend", nargs="*", type=str)
    _ = subparser.add_argument("file", type=argparse.FileType("r"))
    subparser.set_defaults(func=do_parse_containerfile)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    cast(Callable[[argparse.Namespace], None], args.func)(args)
