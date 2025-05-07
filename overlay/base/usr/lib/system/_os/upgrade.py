import traceback
import subprocess
import os
import sys
import shutil

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any
from datetime import datetime

from . import podman
from . import SYSTEM_PATH
from . import OS_NAME
from . import execute
from . import ostree
from . import is_root

from .prune import prune
from .export import export
from .checkupdates import checkupdates
from .build import build
from .build import build_image

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
    from .prepare import prepare

    if not os.path.exists("/ostree"):
        print("OSTree repo missing")
        sys.exit(1)

    if not os.path.exists(SYSTEM_PATH):
        os.makedirs(SYSTEM_PATH, exist_ok=True)

    build()
    rootfs = os.path.join(SYSTEM_PATH, "rootfs")
    if os.path.exists(rootfs):
        shutil.rmtree(rootfs)

    export(rootfs=rootfs, workingDir=SYSTEM_PATH)
    if os.path.exists("/etc/system/commandline"):
        with open("/etc/system/commandline", "r") as f:
            kernelCommandline = f.read()

    else:
        kernelCommandline = ""

    prepare(rootfs, kernelCommandline)
    commit(branch, rootfs)
    _ = shutil.rmtree(rootfs)
    prune(branch)
    deploy(branch, "/", kernelCommandline)
    execute("grub-mkconfig -o /boot/efi/EFI/grub/grub.cfg")


def deploy(branch: str = "system", sysroot: str = "/", kernelCommandline: str = ""):
    kargs = ["--karg=root=LABEL=SYS_ROOT", "--karg=rw"]
    for karg in kernelCommandline.split():
        kargs.append(f"--karg={karg.strip()}")

    execute(
        "ostree",
        "admin",
        "deploy",
        f"--sysroot={sysroot}",
        *kargs,
        f"--os={OS_NAME}",
        "--retain",
        f"{OS_NAME}/{branch}",
    )


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
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
