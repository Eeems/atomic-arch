#!/usr/bin/env python
import argparse
import sys
import os

from typing import cast
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
        f"--volume={_ostree}:/ostree--volume=/var/cache/pacman:/var/cache/pacman",
        "--entrypoint=/usr/bin/os",
        f"atomic-arch:{target}",
        *args,
    )


def do_build(args: argparse.Namespace):
    targets = cast(list[str], args.target)
    if "base" in targets and targets[0] != "base":
        targets.remove("base")

    if "base" not in targets:
        targets = ["base"] + targets

    for target in targets:
        build(target)


def do_iso(args: argparse.Namespace):
    targets = cast(list[str], args.target)
    if not targets:
        targets.append("base")

    for target in targets:
        build(target)
        atomic_arch("build", target=target)
        atomic_arch("iso", target=target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    subparsers = parser.add_subparsers()
    subparser = subparsers.add_parser("build")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_build)
    subparser = subparsers.add_parser("iso")
    _ = subparser.add_argument("target", action="extend", nargs="*", type=str)
    subparser.set_defaults(func=do_iso)
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    cast(Callable[[argparse.Namespace], None], args.func)(args)
