import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..system import is_root
from ..ostree import prune

kwds = {"help": "Prune unused data from the ostree"}


def register(parser: ArgumentParser):
    _ = parser.add_argument("--branch", default="system", help="System branch to prune")


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    prune(cast(str, args.branch))


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
