import subprocess
import os
import shutil
import tarfile
import atexit
import sys

from time import time
from typing import cast
from typing import Any
from argparse import ArgumentParser
from argparse import Namespace

from ..podman import podman
from ..podman import podman_cmd
from .. import SYSTEM_PATH
from .. import is_root

kwds = {"help": "Export your current system image to a folder"}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--tag", default="latest", help="System image version to export"
    )
    _ = parser.add_argument(
        "--rootfs", default=SYSTEM_PATH, help="Directory to export to"
    )
    _ = parser.add_argument(
        "--workingDir",
        default=SYSTEM_PATH,
        help="Working directory to use while exporting",
    )
    _ = parser.add_argument(
        "--setup",
        default="",
        help="Script to run against the system image before exproting it",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    export(
        cast(str, args.tag),
        cast(str, args.setup),
        cast(str, args.rootfs),
        cast(str, args.workingDir),
    )


def export(
    tag: str = "latest",
    setup: str = "",
    rootfs: str | None = None,
    workingDir: str | None = None,
):
    if workingDir is None:
        workingDir = SYSTEM_PATH

    if rootfs is None:
        rootfs = os.path.join(workingDir, "rootfs")

    if os.path.exists(rootfs):
        shutil.rmtree(rootfs)

    os.makedirs(rootfs, exist_ok=True)
    os.makedirs(workingDir, exist_ok=True)
    cwd = os.getcwd()
    os.chdir(workingDir)
    timestamp = int(time())
    name = f"export-{tag}-{timestamp}"
    exitFunc1 = atexit.register(podman, "rm", name)
    podman(
        "run",
        f"--name={name}",
        "--privileged",
        "--security-opt=label=disable",
        "--volume=/run/podman/podman.sock:/run/podman/podman.sock",
        f"system:{tag}",
        "-c",
        setup,
    )
    cmd = podman_cmd("export", name)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    assert process.stdout is not None
    with tarfile.open(fileobj=process.stdout, mode="r|*") as t:
        t.extractall(rootfs, numeric_owner=True, filter="fully_trusted")

    process.stdout.close()
    _ = process.wait()
    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd, None, None)

    atexit.unregister(exitFunc1)
    podman("rm", name)
    os.chdir(cwd)


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
