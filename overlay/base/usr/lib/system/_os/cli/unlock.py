import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..system import is_root
from ..system import execute

kwds = {"help": "Make the current deploy mutable"}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--hotfix",
        action="store_true",
        help="Retain changes accross reboots",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    argv: list[str] = []
    if cast(bool, args.hotfix):
        argv.append("--hotfix")

    execute("ostree", "admin", "unlock", *argv)


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
