import sys
import os

from typing import cast
from typing import Any
from argparse import ArgumentParser
from argparse import Namespace

from ..podman import export
from .. import SYSTEM_PATH
from .. import ROOTFS_PATH
from ..system import is_root

kwds = {"help": "Export your current system image to a folder"}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--tag", default="latest", help="System image version to export"
    )
    _ = parser.add_argument(
        "--rootfs",
        default=ROOTFS_PATH,
        help="Directory to export to",
    )
    _ = parser.add_argument(
        "--workingDir",
        default=SYSTEM_PATH,
        help="Working directory to use while exporting",
    )
    _ = parser.add_argument(
        "--setup",
        default="",
        help="Script to run against the system image before exproting it",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    rootfs = os.path.abspath(cast(str, args.rootfs))
    workingDir = os.path.abspath(cast(str, args.workingDir))
    assert rootfs != workingDir
    assert not workingDir.startswith(rootfs)
    with export(
        cast(str, args.tag),
        cast(str, args.setup),
        workingDir,
    ) as t:
        if not os.path.exists(rootfs):
            os.makedirs(rootfs, exist_ok=True)

        t.extractall(rootfs, numeric_owner=True, filter="fully_trusted")


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
