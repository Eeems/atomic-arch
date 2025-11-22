import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import is_root
from . import in_system
from . import REPO

kwds: dict[str, str] = {
    "help": "Build an ISO for a variant",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument("target", action="extend", nargs="*", type=str)
    _ = parser.add_argument(
        "--no-local-image",
        help="If the image should be copied to the iso container storage",
        dest="localImage",
        action="store_false",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        image = f"{REPO}:{target}"
        _ = in_system("build", target=image, check=True)
        _ = in_system(
            "iso",
            *([] if cast(bool, args.localImage) else ["--no-local-image"]),
            check=True,
            volumes=[
                "/etc/machine-id:/etc/machine-id:ro",
                "/run/dbus/system_bus_socket:/run/dbus/system_bus_socket:ro",
            ],
            flags=["cgroupns=host"],
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
