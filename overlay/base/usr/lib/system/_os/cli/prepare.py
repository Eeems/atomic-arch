import os
import sys
import shutil

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast

from .. import delete
from .. import execute
from .. import is_root


def register(parser: ArgumentParser):
    _ = parser.add_argument("--kargs", default="")
    _ = parser.add_argument("rootfs")


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    prepare(cast(str, args.rootfs), cast(str, args.kargs))


def prepare(rootfs: str, kernelCommandline: str = ""):
    cwd = os.getcwd()
    os.chdir(rootfs)
    _ = shutil.move("etc", "usr")
    with open("usr/etc/system/commandline", "w") as f:
        _ = f.write(kernelCommandline)

    execute(
        "sed",
        "-i",
        "-e",
        r"s|^#\(DBPath\s*=\s*\).*|\1/usr/lib/pacman|g",
        "-e",
        r"s|^#\(IgnoreGroup\s*=\s*\).*|\1modified|g",
        "usr/etc/pacman.conf",
    )
    _ = shutil.move("var/lib/pacman", "usr/lib")
    delete("var/*")
    os.mkdir("sysroot")
    os.symlink("sysroot/ostree", "ostree")
    os.chdir(cwd)


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
