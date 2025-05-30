from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..system import baseImage
from ..dbus import pull
from ..dbus import checkupdates
from ..dbus import upgrade_status
from ..dbus import upgrade


kwds = {"help": "Perform a system upgrade"}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--no-pull",
        help="Do not pull base image updates",
        action="store_true",
        dest="noPull",
    )


def command(args: Namespace):
    if not cast(bool, args.noPull) and upgrade_status() != "pending":
        updates = checkupdates()
        image = baseImage()
        if [x for x in updates if x.startswith(f"{image} ")]:
            pull()

    upgrade()


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
