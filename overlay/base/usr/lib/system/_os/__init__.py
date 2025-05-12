#!/usr/bin/python
import argparse
import importlib
import os
import sys

from glob import iglob
from typing import Callable
from typing import cast


OS_NAME = "atomic-arch"
IMAGE = f"eeems/{OS_NAME}"
SYSTEM_PATH = "/var/lib/system"


def cli(argv: list[str]):
    parser = argparse.ArgumentParser(
        prog="os", description="Manage your operating system", add_help=True
    )
    subparsers = parser.add_subparsers(help="Action to run")
    for file in iglob(os.path.join(os.path.dirname(__file__), "cli", "*.py")):
        if os.path.abspath(file) == os.path.abspath(__file__) or file.endswith("__.py"):
            continue

        name = os.path.splitext(os.path.basename(file))[0]
        module = importlib.import_module(f"{__name__}.cli.{name}", __name__)
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
