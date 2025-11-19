import json

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import image_info
from . import REPO

kwds: dict[str, str] = {
    "help": "Return the JSON manifest of an image",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "-r",
        "--remote",
        action="store_true",
        help="Inspect the image in the repository instead of local",
    )
    _ = parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Output human readable JSON",
    )
    _ = parser.add_argument(
        "target",
        action="extend",
        nargs="+",
        type=str,
        help="Tag to inspect",
        metavar="TAG",
    )


def command(args: Namespace):
    remote = cast(bool, args.remote)
    print(
        json.dumps(
            {
                x: image_info(f"{REPO}:{x}", remote)
                for x in cast(list[str], args.target)
            },
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
