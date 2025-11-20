import os
import sys
import argparse
import importlib

from glob import iglob
from typing import cast
from typing import Callable


def cli(argv: list[str]):
    parser = argparse.ArgumentParser(
        prog="make", description="Manage your operating system", add_help=True
    )
    subparsers = parser.add_subparsers(help="Action to run")
    __dirname__ = os.path.dirname(__file__)
    modulename = os.path.basename(__dirname__)
    for file in iglob(os.path.join(__dirname__, "*.py")):
        if os.path.basename(file).startswith("__") or file.endswith("__.py"):
            continue

        name = os.path.splitext(os.path.basename(file))[0]
        module = importlib.import_module(f"{modulename}.{name}", modulename)
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


if __name__ == "__main__":
    cli(sys.argv[1:])
