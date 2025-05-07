import subprocess
import os
import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from . import podman
from . import is_root

kwds = {"help": "Build your system image"}


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    build()


def build_image() -> str:
    with open("/etc/system/Systemfile", "r") as f:
        return [x.split(" ")[1].strip() for x in f.readlines() if x.startswith("FROM")][
            0
        ]


def build(systemfile: str = "/etc/system/Systemfile"):
    cache = "/var/cache/pacman"
    if not os.path.exists(cache):
        os.makedirs(cache, exist_ok=True)

    uuid = (
        subprocess.check_output(["bash", "-c", "uuidgen --time-v7 | cut -c-8"])
        .decode("utf-8")
        .strip()
    )
    podman(
        "build",
        "--force-rm",
        "--tag=system:latest",
        f"--build-arg=VERSION_ID={uuid}",
        f"--volume={cache}:{cache}",
        f"--file={systemfile}",
    )


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
