import os

from hashlib import sha256
from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast
from glob import iglob

from . import image_labels
from . import image_exists
from . import REPO

kwds: dict[str, str] = {
    "help": "Get the variant hash",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "target",
        action="extend",
        nargs="+",
        type=str,
        metavar="VARIANT",
        help="Variant to hash",
    )


def command(args: Namespace):
    for target in cast(list[str], args.target):
        print(f"{target}: {hash(target)[:9]}")


def hash(target: str) -> str:
    m = sha256()
    containerfile = f"variants/{target}.Containerfile"
    if "-" in target and not os.path.exists(containerfile):
        base_variant, template = target.rsplit("-", 1)
        containerfile = f"templates/{template}.Containerfile"
        image = f"{REPO}:{base_variant}"
        labels = image_labels(image, not image_exists(image, False, False))
        m.update(labels["hash"].encode("utf-8"))

    with open(containerfile, "rb") as f:
        m.update(f.read())

    for file in sorted(iglob(f"overlay/{target}/**", recursive=True)):
        if os.path.isdir(file):
            m.update(file.encode("utf-8"))

        else:
            with open(file, "rb") as f:
                m.update(f.read())

    for file in sorted(
        [
            "build.py",
            "hash.py",
            "pull.py",
            "push.py",
            "__init__.py",
        ]
    ):
        with open(f"make/{file}", "rb") as f:
            m.update(f.read())

    return m.hexdigest()


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
