import json

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast
from collections.abc import Iterable

from . import image_tags
from . import hex_to_base62
from . import image_digest_cached
from . import REPO

kwds: dict[str, str] = {
    "help": "Get deltas",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "target",
        action="extend",
        nargs="+",
        type=str,
        metavar="VARIANT",
        help="Variant to get the deltas for",
    )
    _ = parser.add_argument(
        "--missing", action="store_true", help="Only return deltas that are missing"
    )
    _ = parser.add_argument(
        "--json",
        action="store_true",
        help="Return JSON instead of a newline delimited list",
    )


def command(args: Namespace):
    missing_only = cast(bool, args.missing)
    output_json = cast(bool, args.json)
    targets = cast(list[str], args.target)
    tags = [
        {"a": a, "b": b, "tag": tag}
        for target in targets
        for a, b, tag in get_deltas(target, missing_only=missing_only)
    ]
    if output_json:
        print(json.dumps(tags))
        return

    for item in tags:
        print(item["tag"])


def get_deltas(
    target: str, missing_only: bool = False
) -> Iterable[tuple[str, str, str]]:
    tags = image_tags(REPO, True)
    target_tags = [
        x
        for x in tags
        if x.startswith(f"{target}_")
        and (target == "rootfs" or len(x[len(target) + 1 :]) > 10)
    ]
    target_tags.sort()
    digest_cache = {
        tag: hex_to_base62(image_digest_cached(f"{REPO}:{tag}", skip_manifest=True))
        for tag in target_tags
    }
    diff_tags = (
        [
            x
            for x in tags
            if x.startswith("_diff-") and len(x) == (43 * 2) + 1 + 6 and x[49] == "-"
        ]
        if missing_only
        else []
    )
    for i in range(len(target_tags)):
        for offset in range(1, 4):
            if i + offset < len(target_tags):
                a, b = target_tags[i], target_tags[i + offset]
                if digest_cache[a] == digest_cache[b]:
                    continue

                t = f"_diff-{digest_cache[a]}-{digest_cache[b]}"
                if t not in diff_tags:
                    yield a, b, t


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
