import os
import subprocess

from datetime import datetime

from . import SYSTEM_PATH
from . import OS_NAME
from .system import execute

RETAIN = 5


def ostree_cmd(*args: str) -> list[str]:
    return ["ostree", f"--repo={getattr(ostree, 'repo')}", *args]


def ostree(*args: str):
    execute(*ostree_cmd(*args))


setattr(ostree, "repo", "/ostree/repo")


def commit(
    branch: str = "system", rootfs: str | None = None, skipList: list[str] | None = None
):
    if rootfs is None:
        rootfs = os.path.join(SYSTEM_PATH, "rootfs")

    if skipList is None:
        skipList = []

    skipList.append("/etc")
    for name in os.listdir(os.path.join(rootfs, "var")):
        skipList.append(f"/var/{name}")

    _skipList = os.path.join(SYSTEM_PATH, "skiplist")
    with open(_skipList, "w") as f:
        _ = f.write("\n".join(skipList))

    ostree(
        "commit",
        "--generate-composefs-metadata",
        "--generate-sizes",
        f"--branch={OS_NAME}/{branch}",
        f"--subject={datetime.now().strftime('%Y-%m-%d-%H-%M-%S')}",
        f"--tree=dir={rootfs}",
        f"--skip-list={_skipList}",
    )


def deploy(branch: str = "system", sysroot: str = "/"):
    kargs = ["--karg=root=LABEL=SYS_ROOT", "--karg=rw"]
    revision = f"{OS_NAME}/{branch}"
    if b"/usr/etc/system/commandline" in subprocess.check_output(
        ostree_cmd("ls", revision, "/usr/etc/system")
    ):
        kernelCommandline = (
            subprocess.check_output(
                ostree_cmd("cat", revision, "/usr/etc/system/commandline")
            )
            .strip()
            .decode("UTF-8")
        )
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
        revision,
    )


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
