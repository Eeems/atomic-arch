import sys
import importlib

from subprocess import CalledProcessError
from argparse import ArgumentParser
from argparse import Namespace
from collections.abc import Iterable
from typing import Any
from typing import cast
from typing import Callable

from . import ci_log
from . import pull
from . import hex_to_base62
from . import image_digest
from . import podman
from . import create_delta
from . import _image_digests_write_cache  # pyright: ignore[reportPrivateUsage]
from . import REPO
from . import __name__ as modulename

get_deltas = cast(
    Callable[[str, bool], Iterable[tuple[str, str, str]]],
    importlib.import_module(f"{modulename}.get-deltas", modulename).get_deltas,
)

kwds: dict[str, str] = {
    "help": "Generate deltas",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "target",
        action="extend",
        nargs="+",
        type=str,
        metavar="VARIANT_OR_TAG",
        help="The variants to generate deltas for, or two tags when --explicit is set",
    )
    _ = parser.add_argument(
        "--push",
        action="store_true",
        help="Push the deltas after they have been generated",
    )
    _ = parser.add_argument(
        "--no-pull",
        action="store_false",
        dest="pull",
        help="Do not pull images from the remote repository",
    )
    _ = parser.add_argument(
        "--no-clean",
        action="store_false",
        dest="clean",
        help="Do not remove the tags used to generate the deltas, or the deltas themselves upon completion",
    )
    _ = parser.add_argument(
        "--explicit",
        action="store_true",
        help="Generate an explicit delta between two tags, instead of all missing deltas for a variant",
    )
    _ = parser.add_argument(
        "--force",
        action="store_true",
        help="Generate all deltas, not just the missing ones",
    )


def command(args: Namespace):
    push = cast(bool, args.push)
    pull = cast(bool, args.pull)
    clean = cast(bool, args.clean)
    targets = cast(list[str], args.target)
    if cast(bool, args.explicit):
        if len(targets) != 2:
            print("When --explicit is set, you must specify two explicit tags")
            sys.exit(1)

        imageA, imageB = targets
        delta(imageA, imageB, pull, push, clean)
        return

    missing_only = not cast(bool, args.force)
    for target in targets:
        for a, b, t in get_deltas(target, missing_only):
            delta(a, b, pull, push, clean, imageD=f"{REPO}:{t}")


def delta(
    a: str, b: str, allow_pull: bool, push: bool, clean: bool, imageD: str | None = None
):
    imageA = f"{REPO}:{a}"
    imageB = f"{REPO}:{b}"
    if allow_pull:
        ci_log(f"::group::pull {imageA}")
        pull(imageA)
        ci_log("::endgroup::")
        ci_log(f"::group::pull {imageB}")
        pull(imageB)
        ci_log("::endgroup::")

    if imageD is None:
        digestA = hex_to_base62(image_digest(imageA, False))
        digestB = hex_to_base62(image_digest(imageB, False))
        assert digestA != digestB, "There is nothing to diff"
        imageD = f"{REPO}:_diff-{digestA}-{digestB}"

    ci_log(f"::group::delta {a} and {b}")
    _ = create_delta(imageA, imageB, imageD, allow_pull)
    ci_log("::endgroup::")
    if push:
        ci_log("::group::push")
        tries = 3
        while tries:
            try:
                podman("push", imageD)
                break

            except CalledProcessError:
                tries -= 1

        ci_log("::endgroup::")
        _image_digests_write_cache(imageD, image_digest(imageD, False))

    if not clean:
        return

    ci_log("::group::clean")
    podman("rmi", imageA, imageB)
    if push:
        podman("rmi", imageD)

    ci_log("::endgroup::")


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
