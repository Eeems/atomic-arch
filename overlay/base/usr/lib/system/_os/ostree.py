import os
import shlex
import subprocess

from datetime import datetime
from typing import Callable

from . import SYSTEM_PATH
from . import OS_NAME
from .system import execute
from .system import _execute
from .console import bytes_to_stdout
from .console import bytes_to_stderr

RETAIN = 5


def ostree_cmd(*args: str) -> list[str]:
    return ["ostree", f"--repo={getattr(ostree, 'repo')}", *args]


def ostree(
    *args: str,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    execute(*ostree_cmd(*args), onstdout=onstdout, onstderr=onstderr)


setattr(ostree, "repo", "/ostree/repo")


def commit(
    branch: str = "system",
    rootfs: str | None = None,
    skipList: list[str] | None = None,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
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
        onstdout=onstdout,
        onstderr=onstderr,
    )


def deploy(
    branch: str = "system",
    sysroot: str = "/",
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
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

    cmd = shlex.join(
        [
            "ostree",
            "admin",
            "deploy",
            f"--sysroot={sysroot}",
            *kargs,
            f"--os={OS_NAME}",
            "--retain",
            revision,
        ]
    )
    ret = _execute(cmd)
    if ret:
        raise subprocess.CalledProcessError(ret, cmd, None, None)


def prune(
    branch: str = "system",
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    ostree(
        "prune",
        "--commit-only",
        f"--retain-branch-depth={branch}={RETAIN}",
        f"--only-branch={OS_NAME}/{branch}",
        "--keep-younger-than=1 second",
        onstdout=onstdout,
        onstderr=onstderr,
    )
    execute("ostree", "admin", "cleanup", onstdout=onstdout, onstderr=onstderr)


def undeploy(
    index: int,
    onstdout: Callable[[bytes], None] = bytes_to_stdout,
    onstderr: Callable[[bytes], None] = bytes_to_stderr,
):
    execute(
        "ostree",
        "admin",
        "undeploy",
        "--sysroot=/",
        str(index),
        onstdout=onstdout,
        onstderr=onstderr,
    )
