import sys
import traceback

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any


from .. import is_root
from ..system import checkupdates

kwds = {"help": "Checks for updates to the system"}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--base-image", default=None, help="Base image to check", dest="baseImage"
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    updates = False
    try:
        updates = checkupdates(cast(str, args.baseImage))

    except BaseException:
        traceback.print_exc()
        sys.exit(1)

    if updates:
        sys.exit(2)


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
