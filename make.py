#!/usr/bin/env python
import argparse
from itertools import pairwise
import sys
import shlex
import shutil
import os
import atexit
import re
import tempfile
import json
import string

from glob import iglob
from hashlib import sha256
from typing import cast
from datetime import datetime
from datetime import UTC
from collections.abc import Callable, Iterable

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
image_digest = cast(Callable[[str, bool], str], _os.podman.image_digest)  # pyright:ignore [reportUnknownMemberType]
create_delta = cast(Callable[[str, str, str, bool], None], _os.podman.create_delta)  # pyright:ignore [reportUnknownMemberType]
IMAGE = cast(str, _os.IMAGE)
REGISTRY = cast(str, _os.REGISTRY)


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
        image = f"{REGISTRY}/{IMAGE}:{base_variant}"
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
        image = f"{REGISTRY}/{IMAGE}:{base_variant}"
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

    podman(
        "build",
        f"--tag={REGISTRY}/{IMAGE}:{target}",
        *[f"--build-arg={k}={v}" for k, v in build_args.items()],
        "--force-rm",
        "--volume=/var/cache/pacman:/var/cache/pacman",
        f"--file={containerfile}",
        "--format=docker",
        ".",
    )


def push(target: str):
    image = f"{REGISTRY}/{IMAGE}:{target}"
    labels = image_labels(image, False)
    tags: list[str] = []
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

    if tags:
        podman("untag", *tags)


def pull(target: str):
    podman("pull", f"{REGISTRY}/{IMAGE}:{target}")


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


def get_missing_deltas(target: str) -> Iterable[tuple[str, str]]:
    tags = image_tags(f"{REGISTRY}/{IMAGE}")
    target_tags = [
        x
        for x in tags
        if x.startswith(f"{target}_")
        and (target == "rootfs" or len(x[len(target) + 1 :]) > 10)
        and x
        not in [
            x
            for x in tags
            if x.startswith("_diff-") and len(x) == (43 * 2) + 1 + 6 and x[49] == "-"
        ]
    ]
    target_tags.sort()
    return pairwise(target_tags)


def delta(a: str, b: str, pull: bool, push: bool, clean: bool):
    imageA = f"{REGISTRY}/{IMAGE}:{a}"
    imageB = f"{REGISTRY}/{IMAGE}:{b}"
    if pull:
        podman("pull", imageA)
        podman("pull", imageB)

    digestA = hex_to_base62(image_digest(imageA, False))
    digestB = hex_to_base62(image_digest(imageB, False))
    assert digestA != digestB, "There is nothing to diff"
    imageD = f"{REGISTRY}/{IMAGE}:_diff-{digestA}-{digestB}"
    create_delta(imageA, imageB, imageD, pull)
    if push:
        execute(
            "skopeo",
            "copy",
            f"containers-storage:{imageD}",
            f"docker://{imageD}",
        )

    if clean:
        podman("rmi", imageA, imageB, imageD)


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
        _ = in_system("build", target=f"{REGISTRY}/{IMAGE}:{target}", check=True)
        _ = in_system("iso", check=True)


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
        target=f"{REGISTRY}/{IMAGE}:{cast(str, args.target)}",
        entrypoint="/bin/bash",
    )
    if ret:
        sys.exit(ret)


def do_pull(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        pull(target)


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
        target=f"{REGISTRY}/{IMAGE}:{cast(str, args.target)}",
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
    image = f"{REGISTRY}/{IMAGE}:{target}"
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
    current_hash = image_hash(image) if exists else "(none)"
    if current_hash != new_hash:
        print(f"context {current_hash[:9]} -> {new_hash[:9]}")
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


def do_check(_: argparse.Namespace):
    failed = False
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
                    "ruff check .",
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
            {
                x: image_info(f"{REGISTRY}/{IMAGE}:{x}", remote)
                for x in cast(list[str], args.target)
            }
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

    for target in targets:
        for a, b in get_missing_deltas(target):
            ci_log(f"::group::Delta {a} to {b}")
            delta(a, b, pull, push, clean)
            ci_log("::endgroup::")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    subparsers = parser.add_subparsers()

    subparser = subparsers.add_parser("build")
    _ = subparser.add_argument("--push", action="store_true")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_build)

    subparser = subparsers.add_parser("iso")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
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
    subparser.set_defaults(func=do_check)

    subparser = subparsers.add_parser("inspect")
    _ = subparser.add_argument("--remote", action="store_true")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_inspect)

    subparser = subparsers.add_parser("hash")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_hash)

    subparser = subparsers.add_parser("delta")
    _ = subparser.add_argument("target", action="extend", nargs="+", type=str)
    _ = subparser.add_argument("--push", action="store_true")
    _ = subparser.add_argument("--no-pull", action="store_false", dest="pull")
    _ = subparser.add_argument("--no-clean", action="store_false", dest="clean")
    _ = subparser.add_argument("--explicit", action="store_true")
    subparser.set_defaults(func=do_delta)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    cast(Callable[[argparse.Namespace], None], args.func)(args)
