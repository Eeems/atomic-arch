import traceback
import subprocess
import os
import sys
import shutil

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from .. import execute
from .. import SYSTEM_PATH
from .. import is_root

from ..podman import podman
from ..podman import in_system

from .export import export
from .checkupdates import checkupdates
from .deploy import deploy
from .prune import prune
from .build import build
from .build import build_image
from .commit import commit

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
        baseImage = build_image()
        updates = checkupdates(baseImage)
        if updates:
            try:
                podman("pull", baseImage)

            except subprocess.CalledProcessError:
                traceback.print_exc()

    upgrade(cast(str, args.branch))


def upgrade(branch: str = "system"):
    if not os.path.exists("/ostree"):
        print("OSTree repo missing")
        sys.exit(1)

    if not os.path.exists(SYSTEM_PATH):
        os.makedirs(SYSTEM_PATH, exist_ok=True)

    if os.path.exists("/etc/system/commandline"):
        with open("/etc/system/commandline", "r") as f:
            kernelCommandline = f.read()

    else:
        kernelCommandline = ""

    rootfs = os.path.join(SYSTEM_PATH, "rootfs")
    if os.path.exists(rootfs):
        shutil.rmtree(rootfs)

    build()
    export(rootfs=rootfs, workingDir=SYSTEM_PATH)
    _ = in_system("prepare", rootfs, "--kargs", kernelCommandline, check=True)
    commit(branch, rootfs)
    prune(branch)
    deploy(branch, "/", kernelCommandline)
    _ = shutil.rmtree(rootfs)
    execute("/usr/bin/grub-mkconfig", "-o", "/boot/efi/EFI/grub/grub.cfg")


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
