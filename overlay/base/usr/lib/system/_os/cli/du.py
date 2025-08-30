import subprocess
import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..system import is_root
from ..ostree import deployments
from .. import OS_NAME

kwds = {"help": "Output size of current deployments"}


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    sizes = list(
        reversed(
            subprocess.check_output(
                [
                    "du",
                    "-hs",
                    *[
                        f"/ostree/deploy/{OS_NAME}/deploy/{c}"
                        for _, c, _ in reversed(list(deployments()))
                    ],
                ]
            )
            .strip()
            .decode("utf-8")
            .split("\n")
        )
    )
    for index, checksum, type in deployments():
        diffsize = sizes[index].split()[0]
        size = (
            subprocess.check_output(
                ["du", "-hs", f"/ostree/deploy/{OS_NAME}/deploy/{checksum}"]
            )
            .strip()
            .decode("utf-8")
            .split()[0]
        )
        print(f"{index}: {size} (+{diffsize})", end="")
        if type:
            print(f" ({type})", end="")

        print()

    size = size = (
        subprocess.check_output(["du", "-hs", f"/ostree/deploy/{OS_NAME}/deploy"])
        .strip()
        .decode("utf-8")
        .split()[0]
    )
    print(f"total: {size}")


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
