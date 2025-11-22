import shutil
import atexit
import os
import sys
import shlex

from datetime import datetime
from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from .. import OS_NAME
from .. import SYSTEM_PATH
from .. import ROOTFS_PATH

from ..system import is_root
from ..system import baseImage
from ..system import execute
from ..podman import podman
from ..podman import podman_cmd
from ..podman import export

kwds = {"help": "Build a bootable ISO image to install your system"}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--no-local-image",
        help="If the image should be copied to the iso container storage",
        dest="localImage",
        action="store_false",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    name = iso(cast(bool, args.localImage))
    print(f"ISO Created: {name}")


def iso(local_image: bool):
    cwd = os.getcwd()
    os.chdir(SYSTEM_PATH)
    if os.path.exists("archiso"):
        shutil.rmtree("archiso")

    if os.path.exists("work"):
        shutil.rmtree("work")

    cache = "/var/cache/pacman"
    if not os.path.exists(cache):
        os.makedirs(cache, exist_ok=True)

    uuid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-00")
    buildImage = baseImage()

    os.chdir("/etc/system")
    podman(
        "build",
        f"--build-arg=UUID={uuid}",
        f"--build-arg=BASE_IMAGE={buildImage}",
        "--force-rm",
        "--pull=never",
        f"--volume={cache}:{cache}",
        f"--tag=system:iso-{uuid}",
        "--file=/etc/system/Isofile",
    )
    os.chdir(SYSTEM_PATH)
    exitFunc1 = atexit.register(podman, "rmi", f"system:iso-{uuid}")
    if os.path.exists(ROOTFS_PATH):
        shutil.rmtree(ROOTFS_PATH)

    with export(
        f"iso-{uuid}",
        workingDir=SYSTEM_PATH,
    ) as t:
        if not os.path.exists(ROOTFS_PATH):
            os.makedirs(ROOTFS_PATH, exist_ok=True)

        t.extractall(ROOTFS_PATH, numeric_owner=True, filter="fully_trusted")

    atexit.unregister(exitFunc1)
    podman("rmi", f"system:iso-{uuid}")
    if local_image:
        execute(
            "bash",
            "-c",
            " | ".join(
                [
                    shlex.join(podman_cmd("save", buildImage)),
                    shlex.join(
                        [
                            "podman",
                            f"--root={ROOTFS_PATH}/var/lib/containers/storage",
                            "--runroot=/tmp/podman-runroot",
                            "--storage-driver=vfs",
                            "--events-backend=file",
                            "load",
                        ]
                    ),
                ]
            ),
        )

    _ = shutil.copytree(os.path.join(ROOTFS_PATH, "etc/system/archiso"), "archiso")
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

    execute("mksquashfs", ROOTFS_PATH, "archiso/arkes/x86_64/airootfs.sfs")
    _ = shutil.copy2(os.path.join(ROOTFS_PATH, "etc/system/efiboot.img"), "efiboot.img")
    shutil.rmtree(ROOTFS_PATH)

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
