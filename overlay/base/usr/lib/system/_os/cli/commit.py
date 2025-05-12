import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast

from ..system import is_root

from ..ostree import commit


def register(parser: ArgumentParser):
    _ = parser.add_argument("--branch", default="system")
    _ = parser.add_argument("rootfs")


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    commit(cast(str, args.branch), cast(str, args.rootfs))


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
