import sys
import os
import shlex

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import _execute  # pyright: ignore[reportPrivateUsage]
from . import _osDir  # pyright: ignore[reportPrivateUsage]

kwds: dict[str, str] = {
    "help": "Run an os command from the development files",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "arg",
        action="extend",
        nargs="*",
        type=str,
        metavar="ARG",
        help="Argument to pass to os",
    )


def command(args: Namespace):
    ret = _execute(
        shlex.join([os.path.join(_osDir, "bin/os"), *cast(list[str], args.arg or [])])
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
