import os
import sys
import shutil
import shlex
import atexit

from getpass import getpass
from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any
from glob import iglob

from .. import OS_NAME
from ..system import is_root
from ..system import execute
from ..system import baseImage
from ..ostree import ostree
from ..ostree import deploy
from ..ostree import commit
from ..podman import build
from ..podman import export


NVIDIA_PACKAGES = ["nvidia-open-dkms", "nvidia-container-toolkit", "nvidia-utils"]

kwds = {"help": "Revert the last system upgrade"}


def register(parser: ArgumentParser):
    _ = parser.add_argument("--branch", default="system", help="System branch to prune")
    _ = parser.add_argument(
        "--sysroot", default="/mnt", help="Location to use for mounting target install"
    )
    _ = parser.add_argument(
        "--kernel-commandline",
        default="",
        help="Kernel command line arguments",
        dest="kernelCommandline",
    )
    _ = parser.add_argument(
        "--system-partition",
        default=None,
        help="Partition to install the system to",
        dest="dev_sys",
    )
    _ = parser.add_argument(
        "--boot-partition",
        default=None,
        help="Partition to install the bootloader to",
        dest="dev_boot",
    )
    _ = parser.add_argument(
        "--format-partitions",
        action="store_true",
        dest="formatPartitions",
        help="Format the partitions before installing",
    )
    _ = parser.add_argument("--password", default=None, help="New root password")
    _ = parser.add_argument(
        "--package", action="append", help="Extra package to install", default=[]
    )
    _ = parser.add_argument(
        "--nvidia", action="store_true", help="Install nvidia packages"
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    packages = cast(list[str], args.package)
    if not packages:
        packages += ["man-pages", "man-db", "git"]

    if cast(bool, args.nvidia):
        packages += NVIDIA_PACKAGES

    install(
        cast(str, args.branch),
        cast(str, args.sysroot),
        cast(str | None, args.dev_sys),
        cast(str | None, args.dev_boot),
        cast(str, args.kernelCommandline),
        cast(bool, args.formatPartitions),
        cast(str, args.password),
        packages,
    )


def install(
    branch: str = "system",
    sysroot: str = "/mnt",
    dev_sys: str | None = None,
    dev_boot: str | None = None,
    kernelCommandline: str = "",
    formatPartitions: bool = False,
    password: str | None = None,
    extraPackages: list[str] | None = None,
):
    if os.path.exists("/ostree"):
        print("Cannot install on existing system")
        sys.exit(1)

    if password is None:
        password = os.environ.get("ROOT_PASSWORD", None)
        if password is None and sys.stdout.isatty():
            # TODO - confirm password
            password = getpass("New root password: ")

        if password is None:
            print("A new root password must be provided")
            sys.exit(1)

    if dev_sys is None:
        print("System partition must be specified")
        sys.exit(1)

    if dev_boot is None:
        print("Boot partition must be specified")
        sys.exit(1)

    setattr(ostree, "repo", f"/mnt{getattr(ostree, 'repo')}")
    if os.path.ismount(sysroot):
        execute("umount", "--recursive", sysroot)

    if formatPartitions:
        execute("mkfs.vfat", "-n", "SYS_BOOT", "-F", "32", dev_boot)
        execute("mkfs.ext4", "-L", "SYS_ROOT", "-F", dev_sys)

    execute("mount", "--mkdir", dev_sys, sysroot)
    execute("mount", "--mkdir", dev_boot, os.path.join(sysroot, "boot/efi"))
    systemDir = os.path.join(sysroot, ".system")
    os.mkdir(systemDir)
    execute("ostree", "admin", "init-fs", f"--sysroot={sysroot}", "--modern", sysroot)
    execute("ostree", "admin", "stateroot-init", f"--sysroot={sysroot}", OS_NAME)
    ostree("init", "--mode=bare")
    ostree("config", "set", "sysroot.bootprefix", "1")
    systemfile = "/tmp/Systemfile"
    if os.path.exists(systemfile):
        os.unlink(systemfile)

    _ = shutil.copy2("/etc/system/Systemfile", systemfile)
    build(
        systemfile,
        buildArgs=[f"KARGS={kernelCommandline}"],
        extraSteps=[
            r"RUN /usr/lib/system/install_packages \ ",
            " \\\n".join([f"  {x}" for x in extraPackages or []]),
        ],
    )
    os.unlink(systemfile)
    export(workingDir=systemDir)
    rootfs = os.path.join(systemDir, "rootfs")
    buildImage = baseImage()
    tmp = os.path.join(sysroot, ".tmp")
    os.mkdir(tmp)
    execute("mount", "-o", "bind", tmp, "/var/tmp")
    exitFunc1 = atexit.register(execute, "umount", "/var/tmp")
    execute(
        "systemd-nspawn",
        f"--directory={rootfs}",
        "--bind=/run/podman/podman.sock:/run/podman/podman.sock",
        f"--bind={os.path.join(rootfs, 'usr/etc')}:/etc",
        "/bin/bash",
        "-c",
        f"podman --remote save --multi-image-archive system:latest {buildImage} | podman load",
    )
    containers = os.path.join(sysroot, "ostree/deploy", OS_NAME, "var/lib/containers")
    os.makedirs(containers, exist_ok=True)
    _ = shutil.move(os.path.join(rootfs, "var/lib/containers"), containers)
    _ = shutil.rmtree(os.path.join(rootfs, "var/tmp"))
    atexit.unregister(exitFunc1)
    execute("umount", "/var/tmp")
    os.rmdir(tmp)

    commit(branch, rootfs)
    shutil.rmtree(systemDir)
    deploy(branch, sysroot)
    execute(
        "grub-install",
        "--target=x86_64-efi",
        f"--efi-directory={sysroot}/boot/efi",
        f"--boot-directory={sysroot}/boot/efi/EFI",
        f"--bootloader-id={OS_NAME}",
        "--removable",
        dev_boot,
    )
    sysPath = [
        x.path
        for x in os.scandir(os.path.join(sysroot, f"ostree/deploy/{OS_NAME}/deploy"))
        if x.is_dir()
    ][0]
    for path in iglob(f"{sysPath}/boot/*"):
        if os.path.islink(path) or os.path.isfile(path):
            os.unlink(path)

        else:
            shutil.rmtree(path)

    os.makedirs(
        os.path.join(sysroot, f"ostree/deploy/{OS_NAME}/var/home"), exist_ok=True
    )
    execute(
        "bash", "-c", f"genfstab -U {sysroot} >> {os.path.join(sysPath, 'etc/fstab')}"
    )
    execute(
        "mount",
        "--mkdir",
        "--rbind",
        os.path.join(sysroot, "boot"),
        os.path.join(sysPath, "boot"),
    )
    execute(
        "mount",
        "--mkdir",
        "--rbind",
        os.path.join(sysroot, "ostree"),
        os.path.join(sysPath, "sysroot/ostree"),
    )
    for i in ["dev", "proc", "sys"]:
        execute("mount", "-o", "bind", f"/{i}", os.path.join(sysPath, i))

    execute(
        "chroot",
        sysPath,
        "/bin/bash",
        "-c",
        "grub-mkconfig -o /boot/efi/EFI/grub/grub.cfg",
    )
    execute(
        "chroot",
        sysPath,
        "/bin/bash",
        "-c",
        shlex.join(["echo", f"root:{password}"]) + " | chpasswd",
    )
    execute("umount", "--recursive", sysroot)


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
