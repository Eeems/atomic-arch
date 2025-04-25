#!/usr/bin/python
import os
from re import sub
import shutil
import subprocess
import sys
from tabnanny import check
import tarfile

from time import time
from pathlib import Path
from datetime import datetime

# TODO - locking

timestamp = int(time())


def build():
    _ = subprocess.check_call(
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


GRUB_CFG_TEMPLATE = r"""
insmod part_gpt
insmod part_msdos
insmod fat
insmod iso9660
insmod ntfs
insmod ntfscomp
insmod exfat
insmod udf

search --file --set=root /boot/{0}.uuid

if loadfont "\${prefix}/fonts/unicode.pf2" ; then
    insmod all_video
    set gfxmode="auto"
    terminal_input console
    terminal_output console
fi

default=archlinux
timeout=15
timeout_style=menu

menuentry "Boot atomic-arch" --class arch --class gnu-linux --class gnu --class os --id 'archlinux' {
    set gfxpayload=keep
    linux /arch/boot/x86_64/vmlinuz-linux-zen archisobasedir=arch archisosearchuuid={0} copytoram=n
    initrd /arch/boot/x86_64/initramfs.img
}
menuentry "Boot atomic-arch (nomodeset)" --class arch --class gnu-linux --class gnu --class os --id 'archlinux' {
    set gfxpayload=keep
    linux /arch/boot/x86_64/vmlinuz-linux-zen nomodeset archisobasedir=arch archisosearchuuid={0} copytoram=n
    initrd /arch/boot/x86_64/initramfs.img
}
menuentry 'System shutdown' --class shutdown --class poweroff {
    echo 'System shutting down...'
    halt
}
menuentry 'System restart' --class reboot --class restart {
    echo 'System rebooting...'
    reboot
}
play 600 988 1 1319 4
"""


def iso():
    _ = subprocess.check_call(
        [
            "podman",
            "--remote",
            "build",
            "--tag",
            "system:iso",
            "--tag",
            f"system:{timestamp}",
            "--file",
            "/etc/system/Isofile",
        ]
    )
    system = "/var/lib/system"
    os.makedirs(system, exist_ok=True)
    _ = subprocess.check_call(
        [
            "podman",
            "--remote",
            "create",
            "--name",
            f"iso-{timestamp}",
            "system:iso",
        ]
    )
    tar = os.path.join(system, "rootfs.tar")
    if os.path.exists(tar):
        os.unlink(tar)

    _ = subprocess.check_call(
        ["podman", "--remote", "export", f"iso-{timestamp}", "--output", tar]
    )
    rootfs = os.path.join(system, "rootfs")
    os.makedirs(rootfs, exist_ok=True)
    with tarfile.open(tar, mode="r") as t:
        t.extractall(rootfs, numeric_owner=True, filter="fully_trusted")

    os.unlink(tar)
    _ = subprocess.check_call(
        [
            "podman",
            "--remote",
            "rm",
            f"iso-{timestamp}",
        ]
    )
    iso = os.path.join(system, "iso")
    if os.path.exists(iso):
        shutil.rmtree(iso)

    os.makedirs(os.path.join(iso, "arch/x86_64"), exist_ok=True)
    os.makedirs(os.path.join(iso, "arch/boot/x86_64"), exist_ok=True)
    os.makedirs(os.path.join(iso, "arch/boot/grub"), exist_ok=True)
    os.makedirs(os.path.join(iso, "boot/grub"), exist_ok=True)
    initramfs = os.path.join(iso, "arch/boot/x86_64/initramfs.img")
    if os.path.exists(initramfs):
        os.unlink(initramfs)

    _ = shutil.move(os.path.join(rootfs, "boot/initramfs-iso.img"), initramfs)
    uuid = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-00")
    Path(os.path.join(iso, f"boot/{uuid}.uuid")).touch()
    _ = shutil.copy2(
        os.path.join(rootfs, "boot/vmlinuz-linux-zen"),
        os.path.join(iso, "arch/boot/x86_64"),
    )
    squashfs = os.path.join(iso, "arch/x86_64/airootfs.sfs")
    if os.path.exists(squashfs):
        os.unlink(squashfs)

    _ = subprocess.check_call(["mksquashfs", rootfs, squashfs])
    with open(os.path.join(iso, "boot/grub/grub.cfg"), "w") as f:
        _ = f.write(GRUB_CFG_TEMPLATE.replace("{0}", uuid))

    efi = os.path.join(iso, "boot/grub/efi.img")
    if os.path.exists(efi):
        os.unlink(efi)

    _ = subprocess.check_call(["truncate", "-s", "32M", efi])
    _ = subprocess.check_call(["mkfs.vfat", efi])

    mount = os.path.join(system, "mnt")
    os.makedirs(mount, exist_ok=True)
    _ = subprocess.check_call(["mount", efi, mount])
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
    _ = subprocess.check_call(
        [
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
        ]
    )
    if os.path.exists(os.path.join(iso, "EFI")):
        shutil.rmtree(os.path.join(iso, "EFI"))

    _ = shutil.copytree(os.path.join(mount, "EFI"), os.path.join(iso, "EFI"))
    os.sync()
    _ = subprocess.check_call(["umount", mount])
    os.rmdir(mount)
    _ = subprocess.check_call(
        [
            "grub-mkimage",
            "-o",
            os.path.join(system, "core.img"),
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
        ]
    )
    with open(os.path.join(iso, "boot/grub/atomic-arch.img"), "wb") as img:
        with open(os.path.join(rootfs, "usr/lib/grub/i386-pc/cdboot.img"), "rb") as f:
            _ = img.write(f.read())

        with open(os.path.join(system, "core.img"), "rb") as f:
            _ = img.write(f.read())

    if os.path.exists(os.path.join(system, "atomic-arch.iso")):
        os.unlink(os.path.join(system, "atomic-arch.iso"))

    _ = subprocess.check_call(
        [
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
        ]
    )


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
