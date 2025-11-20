import sys

from datetime import datetime
from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import is_root

from .build import build
from .push import push

kwds: dict[str, str] = {
    "help": "Export the rootfs for a variant",
}


def register(parser: ArgumentParser):
    now = datetime.now()
    _ = parser.add_argument("--year", default=now.year)
    _ = parser.add_argument("--month", default=now.strftime("%m"))
    _ = parser.add_argument("--day", default=now.strftime("%d"))
    _ = parser.add_argument("--tag", default=None)
    _ = parser.add_argument("--no-build", action="store_true", dest="noBuild")
    _ = parser.add_argument("--push", action="store_true")


def command(args: Namespace):
    noBuild = cast(bool, args.noBuild)
    doPush = cast(bool, args.push)
    if noBuild and doPush:
        print("You cannot push without also building")
        sys.exit(1)

    if not is_root() and not noBuild:
        print("Must be run as root")
        sys.exit(1)

    containerfile = "variants/rootfs.Containerfile"
    with open(containerfile, "r") as f:
        lines = f.readlines()

    config = {
        x[0]: x[1]
        for x in [
            x.rstrip().split(" ", 1)[1].split("=", 1)
            for x in lines
            if x.startswith("ARG ARCHIVE_YEAR=")
            or x.startswith("ARG ARCHIVE_MONTH=")
            or x.startswith("ARG ARCHIVE_DAY=")
            or x.startswith("ARG PACSTRAP_TAG=")
        ]
    }

    year = cast(str | None, args.year) or config["ARCHIVE_YEAR"]
    month = cast(str | None, args.month) or config["ARCHIVE_MONTH"]
    day = cast(str | None, args.day) or config["ARCHIVE_DAY"]
    tag = cast(str | None, args.tag) or config["PACSTRAP_TAG"]

    with open(containerfile, "w") as f:
        for line in lines:
            if line.startswith("ARG ARCHIVE_YEAR="):
                line = f"ARG ARCHIVE_YEAR={year}\n"

            elif line.startswith("ARG ARCHIVE_MONTH="):
                line = f"ARG ARCHIVE_MONTH={month}\n"

            elif line.startswith("ARG ARCHIVE_DAY="):
                line = f"ARG ARCHIVE_DAY={day}\n"

            elif line.startswith("ARG PACSTRAP_TAG="):
                line = f"ARG PACSTRAP_TAG={tag}\n"

            _ = f.write(line)

    if noBuild:
        return

    build("rootfs")
    if doPush:
        push("rootfs")


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
