from datetime import datetime
import re
import sys
import requests
import subprocess

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import is_root
from . import image_qualified_name
from . import image_exists
from . import in_system_output
from . import image_hash
from . import in_system
from . import REPO

from .pull import pull
from .hash import hash

kwds: dict[str, str] = {
    "help": "Check to see if a variant has updates and needs to be rebuilt",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--target",
        default="rootfs",
        metavar="VARIANT",
        help="Which variant to check",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    target = cast(str, args.target)
    image = image_qualified_name(f"{REPO}:{target}")
    exists = image_exists(image, True, False)
    if exists and not image_exists(image, False, False):
        try:
            pull(image)

        except subprocess.CalledProcessError:
            pass

    if exists:
        mirror = [
            x.split(" = ", 1)[1]
            for x in in_system_output(
                "cat",
                "/etc/pacman.d/mirrorlist",
                entrypoint="",
                target=image,
            )
            .decode("utf-8")
            .splitlines()
        ][0]

    else:
        mirror = "https://archive.archlinux.org/repos/2025/11/06/$repo/os/$arch"

    m = re.match(r"^(.+)\/(\d{4}\/\d{2}\/\d{2})\/\$repo\/os\/\$arch$", mirror)
    assert m
    current = m.group(2)
    now = datetime.now()
    new = f"{now.year}/{now.strftime('%m')}/{now.strftime('%d')}"
    has_updates = False
    if current != new:
        url = f"{m.group(1)}/{new}/"
        res = requests.head(url)
        if res.status_code == 200:
            print(f"mirrorlist {current} -> {new}")
            has_updates = True

        elif res.status_code != 404:
            print(res.reason)
            sys.exit(1)

    new_hash = hash(target)
    current_hash = image_hash(image) if exists else ""
    if current_hash != new_hash:
        print(f"context {current_hash[:9] or '(none)'} -> {new_hash[:9]}")
        has_updates = True

    if not image_exists(image, False, False):
        if has_updates:
            sys.exit(2)

        return

    res = in_system(
        "-ec",
        " ".join(
            [
                "if [ -f /usr/bin/chronic ]; then",
                "  /usr/bin/chronic /usr/lib/system/initialize_pacman;",
                "else",
                "  /usr/lib/system/initialize_pacman > /dev/null;",
                "fi;",
                "if [ -f /usr/bin/checkupdates ];then",
                "  /usr/bin/checkupdates;",
                "fi",
            ]
        ),
        entrypoint="/bin/bash",
        target=image,
    )
    if res == 1:
        sys.exit(1)

    elif res == 2:
        has_updates = True

    if has_updates:
        sys.exit(2)


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
