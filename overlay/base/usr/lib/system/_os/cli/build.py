import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..podman import build
from ..system import is_root

kwds = {"help": "Build your system image"}


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    build()


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
