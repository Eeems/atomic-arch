import json

from io import TextIOWrapper
from argparse import ArgumentParser
from argparse import Namespace
from argparse import FileType
from typing import Any
from typing import cast

from . import parse_containerfile

kwds: dict[str, str] = {
    "help": "Parse a Containerfile and return the LLB",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Output human readable JSON",
    )
    _ = parser.add_argument(
        "--build_arg",
        metavar="NAME=VALUE",
        action="extend",
        nargs="*",
        type=str,
        help="Build arguments to use when parsing the Containerfile",
    )
    _ = parser.add_argument(
        "file",
        metavar="FILE",
        type=FileType("r"),
        help="Containerfile to parse",
    )


def command(args: Namespace):
    print(
        json.dumps(
            parse_containerfile(
                cast(TextIOWrapper, args.file),
                {
                    k: v
                    for x in cast(list[str], args.build_arg or [])
                    for k, v in [x.split("=", 1)]
                },
                cast(bool, args.pretty),
            ),
            indent=2 if cast(bool, args.pretty) else None,
        )
    )


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
