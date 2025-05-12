import os
import shutil

from datetime import datetime

from . import SYSTEM_PATH
from . import OS_NAME
from . import delete
from .system import execute

RETAIN = 5


def ostree(*args: str):
    execute("ostree", f"--repo={getattr(ostree, 'repo')}", *args)


setattr(ostree, "repo", "/ostree/repo")


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


def prune(branch: str = "system"):
    ostree(
        "prune",
        "--commit-only",
        f"--retain-branch-depth={branch}={RETAIN}",
        f"--only-branch={OS_NAME}/{branch}",
        "--keep-younger-than=1 second",
    )
    execute("ostree", "admin", "cleanup")


def undeploy(index: int):
    execute("ostree", "admin", "undeploy", "--sysroot=/", str(index))
