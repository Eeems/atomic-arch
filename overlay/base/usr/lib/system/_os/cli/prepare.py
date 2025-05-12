import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast

from .. import is_root
from ..ostree import prepare


def register(parser: ArgumentParser):
    _ = parser.add_argument("--kargs", default="")
    _ = parser.add_argument("rootfs")


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    prepare(cast(str, args.rootfs), cast(str, args.kargs))


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
