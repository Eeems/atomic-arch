import sys
import shlex

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import is_root
from . import in_system
from . import REPO

kwds: dict[str, str] = {
    "help": "Run a command in a specific variant",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--target",
        default="base",
        metavar="VARIANT",
        help="Variant to run command in",
    )
    _ = parser.add_argument(
        "command",
        action="extend",
        nargs="+",
        type=str,
        metavar="ARG",
        help="Commands to run in the container",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    ret = in_system(
        "-c",
        shlex.join(cast(list[str], args.command)),
        target=f"{REPO}:{cast(str, args.target)}",
        entrypoint="/bin/bash",
    )
    if ret:
        sys.exit(ret)


if __name__ == "__main__":
    kwds["description"] = kwds["help"]
    del kwds["help"]
    parser = ArgumentParser(
        **cast(  # pyright: ignore[reportAny]
            dict[str, Any],  # pyright: ignore[reportExplicitAny]
            kwds,
        ),
    )
    register(parser)
    args = parser.parse_args()
    command(args)
