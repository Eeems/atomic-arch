import sys
import json
import traceback
import subprocess

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from ..podman import podman_cmd
from ..podman import in_system
from .. import is_root

from .build import build_image

kwds = {"help": "Checks for updates to the system"}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--base-image", default=None, help="Base image to check", dest="baseImage"
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    updates = False
    try:
        updates = checkupdates(cast(str, args.baseImage))

    except BaseException:
        traceback.print_exc()
        sys.exit(1)

    if updates:
        sys.exit(2)


def checkupdates(baseImage: str | None = None) -> bool:
    if baseImage is None:
        baseImage = build_image()

    digests = [
        x
        for x in subprocess.check_output(
            podman_cmd("inspect", "--format={{ .Digest }}", baseImage)
        )
        .decode("utf-8")
        .strip()
        .split("\n")
        if x
    ]
    image_update = False
    if digests:
        with open("/usr/lib/os-release", "r") as f:
            local_info = {
                x[0]: x[1]
                for x in [
                    x.strip().split("=", 1)
                    for x in f.readlines()
                    if x.startswith("VERSION_ID=") or x.startswith("VERSION=")
                ]
            }

        local_id = local_info.get("VERSION_ID", "0")
        remote_info = cast(
            dict[str, object],
            json.loads(
                subprocess.check_output(
                    [
                        "skopeo",
                        "inspect",
                        f"docker://{baseImage}",
                    ]
                )
            ),
        )
        remote_labels = cast(dict[str, dict[str, str]], remote_info).get("Labels", {})
        remote_id = remote_labels.get("os-release.VERSION_ID", "0")
        if local_id != remote_id:
            remote_version = remote_labels.get("os-release.VERSION", "0")
            local_version = local_info.get("VERSION", "0")
            print(
                f"{baseImage} {local_version}.{local_id} -> {remote_version}.{remote_id}"
            )
            image_update = True

    return in_system(entrypoint="/usr/bin/checkupdates") == 0 or image_update


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
