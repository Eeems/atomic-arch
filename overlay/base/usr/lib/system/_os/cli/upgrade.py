import traceback
import subprocess
import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..podman import podman
from ..system import baseImage
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
    if upgrade_status() != "pending" and not cast(bool, args.noPull):
        updates = checkupdates()
        image = baseImage()
        if [x for x in updates if x.startswith(f"{image} ")]:
            try:
                podman("pull", image)

            except subprocess.CalledProcessError:
                traceback.print_exc()

    upgrade()


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
