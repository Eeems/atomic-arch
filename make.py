#!/usr/bin/env python
import argparse
import sys
import shlex
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
podman = cast(Callable[..., None], _os.podman)
ostree = cast(Callable[..., None], _os.ostree)
is_root = cast(Callable[[], bool], _os.is_root)
IMAGE = cast(str, _os.IMAGE)
SYSTEM_PATH = cast(str, _os.SYSTEM_PATH)


def build(target: str):
    podman(
        "build",
        f"--tag=docker.io/{IMAGE}:{target}",
        "--force-rm",
        "--volume=/var/cache/pacman:/var/cache/pacman",
        f"--file=variants/{target}.Containerfile",
        ".",
    )


def in_system(*args: str, target: str | None = None, entrypoint: str = "/usr/bin/os"):
    assert target is not None
    if os.path.exists("/ostree") and os.path.isdir("/ostree"):
        _ostree = "/ostree"
        if not os.path.exists(f"{SYSTEM_PATH}/ostree"):
            os.symlink("/ostree", f"{SYSTEM_PATH}/ostree")

    else:
        _ostree = f"{SYSTEM_PATH}/ostree"
        os.makedirs(_ostree, exist_ok=True)
        repo = os.path.join(_ostree, "repo")
        setattr(ostree, "repo", repo)
        if not os.path.exists(repo):
            ostree("init")

    podman(
        "run",
        "--rm",
        "--privileged",
        "--security-opt=label=disable",
        "--volume=/run/podman/podman.sock:/run/podman/podman.sock",
        f"--volume={SYSTEM_PATH}:{SYSTEM_PATH}",
        f"--volume={_ostree}:/ostree",
        "--volume=/var/cache/pacman:/var/cache/pacman",
        f"--entrypoint={entrypoint}",
        f"{IMAGE}:{target}",
        *args,
    )


def push(target: str):
    podman("push", f"{IMAGE}:{target}")


def pull(target: str):
    podman("pull", f"{IMAGE}:{target}")


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
        in_system("build", target=target)

    for target in cast(list[str], args.target):
        in_system("iso", target=target)


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

    if not noBuild:
        build("rootfs")


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

    in_system(
        "-c",
        shlex.join(cast(list[str], args.arg)),
        target=cast(str, args.target),
        entrypoint="/bin/bash",
    )


def do_pull(args: argparse.Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        pull(target)


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
    _ = subparser.add_argument("--no-build", action="store_true", dest="noBuild")
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

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    cast(Callable[[argparse.Namespace], None], args.func)(args)
