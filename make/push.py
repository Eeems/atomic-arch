import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import is_root
from . import image_labels
from . import podman
from . import image_digest
from . import _image_digests_write_cache  # pyright: ignore[reportPrivateUsage]
from . import REPO

kwds: dict[str, str] = {
    "help": "Push one or more tags to the remote repository",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "target",
        action="extend",
        nargs="+",
        type=str,
        metavar="TAG",
        help="Tag to push",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    for target in cast(list[str], args.target):
        push(target)


def push(target: str):
    image = f"{REPO}:{target}"
    labels = image_labels(image, False)
    tags: list[str] = []
    # TODO handle when trying to push a versioned image
    if labels.get("os-release.VERSION", None):
        version = labels["os-release.VERSION"]
        version_id = labels.get("os-release.VERSION_ID", None)
        if version_id and version != version_id:
            tag = f"{image}_{version}.{version_id}"
            tags.append(tag)
            podman("tag", image, tag)

        tag = f"{image}_{version}"
        tags.append(tag)
        podman("tag", image, tag)

    for tag in [*tags, image]:
        podman("push", "--compression-format=zstd:chunked", tag)
        print(f"Pushed {tag}")
        _image_digests_write_cache(tag, image_digest(tag, False))

    if tags:
        podman("rmi", *tags)


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
