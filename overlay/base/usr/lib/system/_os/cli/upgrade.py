import traceback
import subprocess
import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..system import is_root

from ..podman import podman
from ..system import checkupdates
from ..system import baseImage
from ..system import upgrade


kwds = {"help": "Perform a system upgrade"}


def register(parser: ArgumentParser):
    _ = parser.add_argument("--branch", default="system", help="System branch to prune")
    _ = parser.add_argument(
        "--no-pull",
        help="Do not pull base image updates",
        action="store_true",
        dest="noPull",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    if not cast(bool, args.noPull):
        image = baseImage()
        updates = checkupdates(image)
        if updates:
            try:
                podman("pull", image)

            except subprocess.CalledProcessError:
                traceback.print_exc()

    upgrade(cast(str, args.branch))


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
