import sys
import _os.podman  # noqa: E402 #pyright:ignore [reportMissingImports]

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import Callable
from typing import cast

from . import is_root
from . import REPO

pull = cast(Callable[[str], None], _os.podman.pull)  # pyright:ignore [reportUnknownMemberType]

kwds: dict[str, str] = {
    "help": "Pull one or more tags from the remote repository",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "target",
        action="extend",
        nargs="+",
        type=str,
        metavar="TAG",
        help="Tag to pull",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        pull(f"{REPO}:{target}")


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
