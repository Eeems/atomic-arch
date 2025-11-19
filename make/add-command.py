from argparse import ArgumentParser
from argparse import Namespace
import os
import shutil
import sys
from typing import Any
from typing import cast

kwds: dict[str, str] = {
    "help": "Adds a new command using __template__.py",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument("name", help="Name of the command to add")


def command(args: Namespace):
    name = cast(str, args.name)
    __dirname__ = os.path.dirname(__file__)
    toPath = os.path.join(__dirname__, f"{name}.py")
    if os.path.exists(toPath):
        print(f"Command {name} already exists", file=sys.stderr)
        sys.exit(1)

    _ = shutil.copyfile(os.path.join(__dirname__, "__template__.py"), toPath)


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
