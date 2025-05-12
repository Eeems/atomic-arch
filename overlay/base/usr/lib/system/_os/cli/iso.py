import shutil
import atexit
import os
import sys

from datetime import datetime
from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from ..podman import podman
from .. import execute
from .. import OS_NAME
from .. import SYSTEM_PATH
from .. import is_root

from .export import export

kwds = {"help": "Build a bootable ISO image to install your system"}


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    name = iso()
    print(f"ISO Created: {name}")


def iso():
    cwd = os.getcwd()
    os.chdir(SYSTEM_PATH)
    if os.path.exists("archiso"):
        shutil.rmtree("archiso")

    if os.path.exists("work"):
        shutil.rmtree("work")

    uuid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-00")
    with open("/etc/system/Systemfile", "r") as f:
        buildImage = [
            x.split(" ")[1].strip() for x in f.readlines() if x.startswith("FROM")
        ][0]

    os.chdir("/etc/system")
    podman(
        "build",
        f"--build-arg=UUID={uuid}",
        f"--build-arg=BASE_IMAGE={buildImage}",
        "--force-rm",
        f"--tag=system:iso-{uuid}",
        "--file=/etc/system/Isofile",
    )
    os.chdir(SYSTEM_PATH)
    exitFunc1 = atexit.register(podman, "rmi", f"system:iso-{uuid}")
    rootfs = os.path.join(SYSTEM_PATH, "rootfs")
    if os.path.exists(rootfs):
        shutil.rmtree(rootfs)

    export(
        f"iso-{uuid}",
        f"podman --remote save {buildImage} | podman load",
        rootfs=rootfs,
        workingDir=SYSTEM_PATH,
    )
    atexit.unregister(exitFunc1)
    podman("rmi", f"system:iso-{uuid}")

    _ = shutil.copytree("rootfs/etc/system/archiso", "archiso")
    for path in [
        "loader/entries/01-archiso-x86_64-linux.conf",
        "grub/grub.cfg",
        "syslinux/syslinux-linux.cfg",
    ]:
        with open(os.path.join("archiso", path), "r+") as f:
            content = f.read()
            _ = f.seek(0)
            _ = f.truncate()
            _ = f.write(content.replace("%UUID%", uuid))

    execute("mksquashfs", "rootfs", "archiso/atomic/x86_64/airootfs.sfs")
    _ = shutil.copy2("rootfs/etc/system/efiboot.img", "efiboot.img")
    shutil.rmtree("rootfs")

    parts = buildImage.split(":")
    variant = parts[-1] if len(parts) == 2 else "latest"
    name = f"{OS_NAME}-{variant}-{uuid}.iso"
    # fmt: off
    execute(
        "xorriso",
        "-volume_date", "uuid", uuid.replace("-", ""),
        "-as", "mkisofs",
        "-iso-level", "3",
        "-partition_offset", "16",
        "--mbr-force-bootable",
        "-append_partition", "2", "0xEF", "efiboot.img",
        "-appended_part_as_gpt",
        "-c", "/boot.catalog",
        "-b", "boot/grub/eltorito.img",
        "-no-emul-boot",
        "-boot-load-size", "4",
        "-boot-info-table",
        "--grub2-boot-info",
        "-eltorito-alt-boot",
        "-e", "--interval:appended_partition_2:all::",
        "-no-emul-boot",
        "-o", name,
        "archiso",
    )
    # fmt: on
    os.unlink("efiboot.img")
    shutil.rmtree("archiso")
    os.chdir(cwd)
    return name


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
