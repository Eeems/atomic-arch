import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast

from .. import execute
from .. import is_root
from .. import OS_NAME


def register(parser: ArgumentParser):
    _ = parser.add_argument("--branch", default="system")
    _ = parser.add_argument("--sysroot", default="/")
    _ = parser.add_argument("--kargs", default="", dest="kernelCommandline")


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    deploy(
        cast(str, args.branch),
        cast(str, args.sysroot),
        cast(str, args.kernelCommandline),
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


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
