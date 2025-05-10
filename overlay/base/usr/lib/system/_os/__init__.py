#!/usr/bin/python
import argparse
import importlib
import os
import shlex
import shutil
import subprocess
import sys

from glob import iglob
from typing import Callable
from typing import cast


OS_NAME = "atomic-arch"
IMAGE = f"eeems/{OS_NAME}"
SYSTEM_PATH = "/var/lib/system"


def is_root() -> bool:
    return os.geteuid() == 0


def _execute(cmd: str):
    status = os.system(cmd)
    return os.waitstatus_to_exitcode(status)


def execute(cmd: str | list[str], *args: str):
    if not isinstance(cmd, str):
        cmd = shlex.join(cmd)

    if args:
        cmd = f"{cmd} {shlex.join(args)}"

    ret = _execute(cmd)
    if ret:
        raise subprocess.CalledProcessError(ret, cmd, None, None)


def chronic(cmd: str | list[str], *args: str):
    argv: list[str] = []
    if isinstance(cmd, str):
        argv.append(cmd)

    else:
        argv += cmd

    if args:
        argv += args

    try:
        _ = subprocess.check_output(argv, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(e.output)  # pyright:ignore [reportAny]
        raise


def podman_cmd(*args: str):
    if _execute("systemd-detect-virt --quiet --container") == 0:
        return ["podman", "--remote", *args]

    return ["podman", *args]


def podman(*args: str):
    execute(*podman_cmd(*args))


def ostree(*args: str):
    execute("ostree", f"--repo={getattr(ostree, 'repo')}", *args)


setattr(ostree, "repo", "/ostree/repo")


def delete(glob: str):
    for path in iglob(glob):
        if os.path.islink(path) or os.path.isfile(path):
            os.unlink(path)

        else:
            shutil.rmtree(path)


def cli(argv: list[str]):
    parser = argparse.ArgumentParser(
        prog="os", description="Manage your operating system", add_help=True
    )
    subparsers = parser.add_subparsers(help="Action to run")
    for file in iglob(os.path.join(os.path.dirname(__file__), "*.py")):
        if os.path.abspath(file) == os.path.abspath(__file__) or file.endswith("__.py"):
            continue

        name = os.path.splitext(os.path.basename(file))[0]
        module = importlib.import_module(f"{__name__}.{name}", __name__)
        subparser = subparsers.add_parser(
            name,
            **getattr(module, "kwds", {}),  # pyright:ignore [reportAny]
        )
        module.register(subparser)  # pyright:ignore [reportAny]
        subparser.set_defaults(func=module.command)  # pyright:ignore [reportAny]

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    cast(Callable[[argparse.Namespace], None], args.func)(args)
