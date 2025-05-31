import sys
import traceback

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..dbus import checkupdates
from ..system import _execute  # pyright:ignore [reportPrivateUsage]

kwds = {"help": "Checks for updates to the system"}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--force",
        action="store_true",
        help="Force check updates, even if there are already known updates",
    )


def command(args: Namespace):
    ret = _execute("nm-online --quiet")
    if ret:
        print("Not currently online", file=sys.stderr)
        sys.exit(1)

    updates: list[str] = []
    try:
        updates = checkupdates(cast(bool, args.force))

    except BaseException:
        traceback.print_exc()
        sys.exit(1)

    if updates:
        print("\n".join(updates))
        sys.exit(2)


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
