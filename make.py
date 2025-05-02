#!/usr/bin/env python
import argparse
import sys
import os

from typing import cast
from datetime import datetime
from importlib.util import spec_from_loader
from importlib.util import module_from_spec
from importlib.machinery import SourceFileLoader
from collections.abc import Callable


def import_from_file(path: str):
    name = os.path.basename(path)
    spec = spec_from_loader(name, SourceFileLoader(name, path))
    assert spec is not None
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_os = import_from_file("overlay/base/usr/bin/os")
podman = _os.podman
ostree = _os.ostree
is_root = _os.is_root


def build(target):
    podman(
        "build",
        f"--tag=atomic-arch:{target}",
        "--force-rm",
        "--volume=/var/cache/pacman:/var/cache/pacman",
        f"--file=variants/{target}.Containerfile",
        ".",
    )


def atomic_arch(*args: str, target: str | None = None):
    assert target is not None
    if os.path.exists("/ostree") and os.path.isdir("/ostree"):
        _ostree = "/ostree"
        if not os.path.exists("/var/lib/system/ostree"):
            os.symlink("/ostree", "/var/lib/system/ostree")

    else:
        _ostree = "/var/lib/system/ostree"
        os.makedirs(_ostree, exist_ok=True)
        repo = os.path.join(_ostree, "repo")
        setattr(ostree, "repo", repo)  # pyright:ignore [reportAny]
        if not os.path.exists(repo):
            ostree("init")

    podman(
        "run",
        "--rm",
        "--privileged",
        "--security-opt=label=disable",
        "--volume=/run/podman/podman.sock:/run/podman/podman.sock",
        "--volume=/var/lib/system:/var/lib/system",
        f"--volume={_ostree}:/ostree",
        "--volume=/var/cache/pacman:/var/cache/pacman",
        "--entrypoint=/usr/bin/os",
        f"atomic-arch:{target}",
        *args,
    )


def do_build(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        build(target)


def do_iso(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        build(target)
        atomic_arch("build", target=target)

    for target in cast(list[str], args.target):
        atomic_arch("iso", target=target)

def do_rootfs(args: argparse.Namespace):
    noBuild = cast(bool, args.noBuild)
    if not is_root() and not noBuild:
        print("Must be run as root")
        sys.exit(1)

    containerfile = "variants/rootfs.Containerfile"
    with open(containerfile, "r") as f:
        lines = f.readlines()

    config = {
        x[0]: x[1]
        for x in
        [
            x.rstrip().split(" ", 1)[1].split("=", 1)
            for x in lines
            if x.startswith("ARG ARCHIVE_YEAR=")
            or x.startswith("ARG ARCHIVE_MONTH=")
            or x.startswith("ARG ARCHIVE_DAY=")
            or x.startswith("ARG PACSTRAP_TAG=")
        ]
    }

    year = cast(str|None, args.year) or config["ARCHIVE_YEAR"]
    month = cast(str|None, args.month) or config["ARCHIVE_MONTH"]
    day = cast(str|None, args.day) or config["ARCHIVE_DAY"]
    tag = cast(str|None, args.tag) or config["PACSTRAP_TAG"]

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

            f.write(line)

    if not noBuild:
        build("rootfs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    subparsers = parser.add_subparsers()

    subparser = subparsers.add_parser("build")
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
    _ = subparser.add_argument(
        "--no-build",
        action="store_true",
        dest="noBuild"
    )
    subparser.set_defaults(func=do_rootfs)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    cast(Callable[[argparse.Namespace], None], args.func)(args)
