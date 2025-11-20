# pyright: reportImportCycles=false
import os
import shlex
import subprocess
import json

from datetime import datetime
from typing import Callable
from typing import cast
from collections.abc import Generator

from . import SYSTEM_PATH
from . import ROOTFS_PATH
from . import OS_NAME

from .system import execute
from .system import _execute  # pyright:ignore [reportPrivateUsage]
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
        rootfs = ROOTFS_PATH

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
    os.unlink(_skipList)


def deploy(
    branch: str = "system",
    sysroot: str = "/",
    onstdout: Callable[[bytes], None] = bytes_to_stdout,  # pyright:ignore [reportUnusedParameter]
    onstderr: Callable[[bytes], None] = bytes_to_stderr,  # pyright:ignore [reportUnusedParameter]
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

    stateroot = OS_NAME
    if not os.path.exists(os.path.join(sysroot, "ostree/deploy", OS_NAME)):
        _, _, _, stateroot = current_deployment()

    cmd = shlex.join(
        [
            "ostree",
            "admin",
            "deploy",
            f"--sysroot={sysroot}",
            *kargs,
            f"--os={OS_NAME}",
            f"--stateroot={stateroot}",
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
    from .podman import podman

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
    podman("system", "prune", "-f", "--build")


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


def deployments() -> Generator[tuple[int, str, str, bool, str], None, None]:
    status = json.loads(  # pyright: ignore[reportAny]
        subprocess.check_output(["ostree", "admin", "status", "--json"])
    )
    assert isinstance(status, dict)
    deployments = cast(
        list[dict[str, str | int | bool]],
        status.get("deployments", []),  # pyright: ignore[reportUnknownMemberType]
    )
    index = 0
    for deployment in deployments:
        type = ""
        if cast(bool, deployment["booted"]):
            type = "current"

        elif cast(bool, deployment["pending"]):
            type = "pending"

        elif cast(bool, deployment["rollback"]):
            type = "rollback"

        yield (
            index,
            f"{deployment['checksum']}.{deployment['serial']}",
            type,
            cast(bool, deployment["pinned"]),
            cast(str, deployment["stateroot"]),
        )
        index += 1


def current_deployment() -> tuple[int, str, bool, str]:
    candidates = [x for x in deployments() if x[2] == "current"]
    assert len(candidates) == 1, (
        f"There should be one current deployment, not {len(candidates)}"
    )
    index, checksum, _, pinned, stateroot = candidates[0]
    return index, checksum, pinned, stateroot
