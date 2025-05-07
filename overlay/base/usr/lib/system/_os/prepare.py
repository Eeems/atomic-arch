import os
import sys
import shutil

from argparse import ArgumentParser
from argparse import Namespace
from glob import iglob
from typing import cast

from . import delete
from . import execute
from . import is_root


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
    with open("etc/system/commandline", "w") as f:
        _ = f.write(kernelCommandline)

    _ = shutil.move("etc", "usr")

    def var_link(name: str):
        shutil.rmtree(name)
        os.symlink(f"var/{name}", name)

    var_link("home")
    var_link("mnt")
    shutil.rmtree("root")
    delete("run/*")
    os.symlink("var/roothome", "root")
    var_link("srv")
    os.mkdir("sysroot")
    os.symlink("sysroot/ostree", "ostree")
    shutil.rmtree("usr/local")
    os.symlink("../var/userlocal", "usr/local")
    _ = shutil.move("var/lib/pacman", "usr/lib")
    execute(
        "sed",
        "-i",
        "-e",
        r"s|^#\(DBPath\s*=\s*\).*|\1/usr/lib/pacman|g",
        "-e",
        r"s|^#\(IgnoreGroup\s*=\s*\).*|\1modified|g",
        "usr/etc/pacman.conf",
    )
    delete("var/*")
    os.unlink("boot/vmlinuz-linux-zen")
    modulePath = [*iglob("usr/lib/modules/*")][0]
    os.rename("boot/initramfs-linux-zen.img", f"{modulePath}/initramfs.img")
    os.chdir(cwd)


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
