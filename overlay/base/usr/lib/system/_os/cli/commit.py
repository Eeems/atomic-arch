import os
import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from datetime import datetime

from .. import ostree
from .. import is_root
from .. import SYSTEM_PATH
from .. import OS_NAME


def register(parser: ArgumentParser):
    _ = parser.add_argument("--branch", default="system")
    _ = parser.add_argument("rootfs")


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    commit(cast(str, args.branch), cast(str, args.rootfs))


def commit(branch: str = "system", rootfs: str | None = None):
    if rootfs is None:
        rootfs = os.path.join(SYSTEM_PATH, "rootfs")

    ostree(
        "commit",
        "--generate-composefs-metadata",
        "--generate-sizes",
        f"--branch={OS_NAME}/{branch}",
        f"--subject={datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}",
        f"--tree=dir={rootfs}",
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
