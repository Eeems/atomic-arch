import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast

from .. import is_root
from ..ostree import deploy


def register(parser: ArgumentParser):
    _ = parser.add_argument("--branch", default="system")
    _ = parser.add_argument("--sysroot", default="/")
    _ = parser.add_argument("--kargs", default="", dest="kernelCommandline")


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    deploy(
        cast(str, args.branch),
        cast(str, args.sysroot),
        cast(str, args.kernelCommandline),
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
