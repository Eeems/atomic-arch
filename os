#!/usr/bin/python
import atexit
import os
import shutil
import subprocess
import sys
import tarfile
import shlex

from time import time
from datetime import datetime

# TODO - locking

timestamp = int(time())


def execute(cmd: str | list[str], *args: str):
    if not isinstance(cmd, str):
        cmd = shlex.join(cmd)

    if args:
        cmd = f"{cmd} {shlex.join(args)}"

    status = os.system(cmd)
    ret = os.waitstatus_to_exitcode(status)
    if ret:
        raise subprocess.CalledProcessError(ret, cmd, None, None)


def build():
    execute(
        [
            "podman",
            "--remote",
            "build",
            "--tag",
            "system:latest",
            "--tag",
            f"system:{timestamp}",
            "--file",
            "/etc/system/Systemfile",
        ]
    )


def iso():
    uuid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-00")
    with open("/etc/system/Systemfile", "r") as f:
        buildImage = [
            x.split(" ")[1].strip() for x in f.readlines() if x.startswith("FROM")
        ][0]

    execute(
        [
            "podman",
            "--remote",
            "build",
            f"--build-arg=UUID={uuid}",
            f"--build-arg=BASE_IMAGE={buildImage}",
            "--tag",
            f"system:iso-{uuid}",
            "--file",
            "/etc/system/Isofile",
        ]
    )
    exitFunc1 = atexit.register(
        execute, "podman", "--remote", "rmi", f"system:iso-{uuid}"
    )
    system = "/var/lib/system"
    os.makedirs(system, exist_ok=True)
    execute(
        "podman",
        "--remote",
        "create",
        "--name",
        f"iso-{timestamp}",
        f"system:iso-{uuid}",
    )
    exitFunc2 = atexit.register(execute, "podman", "--remote", "rm", f"iso-{timestamp}")
    tar = os.path.join(system, "rootfs.tar")
    if os.path.exists(tar):
        os.unlink(tar)

    execute(["podman", "--remote", "export", f"iso-{timestamp}", "--output", tar])
    rootfs = os.path.join(system, "rootfs")
    os.makedirs(rootfs, exist_ok=True)
    with tarfile.open(tar, mode="r") as t:
        t.extractall(rootfs, numeric_owner=True, filter="fully_trusted")

    os.unlink(tar)
    atexit.unregister(exitFunc2)
    execute(
        "podman",
        "--remote",
        "rm",
        f"iso-{timestamp}",
    )
    atexit.unregister(exitFunc1)
    execute("podman", "--remote", "rmi", f"system:iso-{uuid}")
    iso = os.path.join(system, "iso")
    if os.path.exists(iso):
        shutil.rmtree(iso)

    _ = shutil.move(os.path.join(rootfs, "iso"), iso)
    squashfs = os.path.join(iso, "arch/x86_64/airootfs.sfs")
    if os.path.exists(squashfs):
        os.unlink(squashfs)

    execute("mksquashfs", rootfs, squashfs)

    efi = os.path.join(iso, "boot/grub/efi.img")
    if os.path.exists(efi):
        os.unlink(efi)

    execute("truncate", "-s", "32M", efi)
    execute("mkfs.vfat", efi)

    mount = os.path.join(system, "mnt")
    os.makedirs(mount, exist_ok=True)
    execute("mount", efi, mount)
    os.makedirs(os.path.join(mount, "EFI/BOOT"), exist_ok=True)
    modules = " ".join(
        [
            "all_video",
            "at_keyboard",
            "boot",
            "btrfs",
            "cat",
            "chain",
            "configfile",
            "echo",
            "efifwsetup",
            "efinet",
            "exfat",
            "ext2",
            "f2fs",
            "fat",
            "font",
            "gfxmenu",
            "gfxterm",
            "gzio",
            "halt",
            "hfsplus",
            "iso9660",
            "jpeg",
            "keylayouts",
            "linux",
            "loadenv",
            "loopback",
            "lsefi",
            "lsefimmap",
            "minicmd",
            "normal",
            "ntfs",
            "ntfscomp",
            "part_apple",
            "part_gpt",
            "part_msdos",
            "png",
            "read",
            "reboot",
            "regexp",
            "search",
            "search_fs_file",
            "search_fs_uuid",
            "search_label",
            "serial",
            "sleep",
            "tpm",
            "udf",
            "usb",
            "usbserial_common",
            "usbserial_ftdi",
            "usbserial_pl2303",
            "usbserial_usbdebug",
            "video",
            "xfs",
            "zstd",
        ]
    )
    execute(
        "grub-mkstandalone",
        "-O",
        "x86_64-efi",
        f"--modules={modules}",
        "--locales=en@quot",
        '--themes=""',
        "--sbat=/usr/share/grub/sbat.csv",
        "--disable-shim-lock",
        "-o",
        os.path.join(mount, "EFI/BOOT/BOOTx64.EFI"),
        "boot/grub/grub.cfg=./grub.cfg",
    )
    if os.path.exists(os.path.join(iso, "EFI")):
        shutil.rmtree(os.path.join(iso, "EFI"))

    _ = shutil.copytree(os.path.join(mount, "EFI"), os.path.join(iso, "EFI"))
    os.sync()
    execute("umount", mount)
    os.rmdir(mount)
    core = os.path.join(system, "core.img")
    execute(
        "grub-mkimage",
        "-o",
        core,
        "-p",
        "/boot/grub",
        "-O",
        "i386-pc",
        "all_video",
        "at_keyboard",
        "boot",
        "btrfs",
        "biosdisk",
        "iso9660",
        "multiboot",
        "configfile",
        "echo",
        "halt",
        "reboot",
        "exfat",
        "ext2",
        "linux",
        "ntfs",
        "usb",
        "sleep",
        "xfs",
        "zstd",
    )
    with open(os.path.join(iso, "boot/grub/atomic-arch.img"), "wb") as img:
        with open(os.path.join(rootfs, "usr/lib/grub/i386-pc/cdboot.img"), "rb") as f:
            _ = img.write(f.read())

        with open(core, "rb") as f:
            _ = img.write(f.read())

    os.unlink(core)
    if os.path.exists(os.path.join(system, "atomic-arch.iso")):
        os.unlink(os.path.join(system, "atomic-arch.iso"))

    execute(
        "xorriso",
        "-volume_date",
        "uuid",
        f"{uuid.replace('-', '')}",
        "-as",
        "mkisofs",
        "-b",
        "boot/grub/atomic-arch.img",
        "-no-emul-boot",
        "-boot-load-size",
        "4",
        "-boot-info-table",
        "--grub2-boot-info",
        "--grub2-mbr",
        os.path.join(rootfs, "usr/lib/grub/i386-pc/boot_hybrid.img"),
        "--efi-boot",
        "boot/grub/efi.img",
        "-efi-boot-part",
        "--efi-boot-image",
        "-o",
        os.path.join(system, "atomic-arch.iso"),
        iso,
    )
    shutil.rmtree(rootfs)
    shutil.rmtree(iso)


if len(sys.argv) != 2:
    print("Usage: os <command>")
    sys.exit(1)

if sys.argv[1] == "build":
    build()

elif sys.argv[1] == "iso":
    iso()

else:
    print("Invalid command")
    sys.exit(1)
