import itertools
import json
import os
import tempfile
import _os  # pyright: ignore[reportMissingImports]

from datetime import datetime
from datetime import UTC
from argparse import ArgumentParser
from argparse import Namespace
from collections import defaultdict
from collections import deque
from collections.abc import Iterable
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from typing import Any
from typing import cast

from . import image_tags
from . import hex_to_base62
from . import progress_bar
from . import image_size_cached
from . import podman
from . import chronic
from . import podman_cmd
from . import escape_label
from . import _image_size_cached  # pyright: ignore[reportPrivateUsage]
from . import _image_digest_cached  # pyright: ignore[reportPrivateUsage]
from . import _image_digests_write_cache  # pyright: ignore[reportPrivateUsage]
from . import REPO

from .config import parse_all_config


MAX_SIZE_RATIO = cast(float, _os.podman.MAX_SIZE_RATIO)  # pyright: ignore[reportUnknownMemberType]


kwds: dict[str, str] = {
    "help": "Generate the manifest image",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--push",
        action="store_true",
        help="Push the manifest after it builds",
    )


def command(args: Namespace):
    config = parse_all_config()
    print("Getting all tags...")
    all_tags = image_tags(REPO, True)
    assert all_tags, "No tags found"
    digest_info: dict[str, tuple[list[str], str]] = {}
    graph: defaultdict[str, dict[str, tuple[str, int]]] = defaultdict(dict)
    digest_worker_queue: list[tuple[str, str]] = []
    valid_variants = ["rootfs", *config["variants"].keys()]
    for tag in progress_bar(
        all_tags,
        prefix="Classifying tags:" + " " * 9,
    ):
        kind, a, b = _classify_tag(tag)
        if kind in ("other", "manifest"):
            continue

        if kind == "diff":
            if a and b:
                graph[a][b] = (tag, -1)

            continue

        if kind not in ("build", "version", "variant"):
            digest_worker_queue.append((kind, tag))
            continue

        assert a
        parts = a.split("-", 1)
        variant = parts[0]
        if variant not in valid_variants:
            continue

        if "-" in a and parts[1] not in [
            y
            for x in config["variants"].values()
            for y in cast(list[str], x.get("templates", []))
        ]:
            continue

        digest_worker_queue.append((kind, tag))

    assert digest_worker_queue, "No tags found"

    def _digest_worker(data: tuple[str, str]) -> tuple[str, str, Future[str] | str]:
        image = f"{REPO}:{data[1]}"
        future = _image_digest_cached(image, skip_manifest=True)
        if isinstance(future, Future):
            future.add_done_callback(
                lambda x: _image_digests_write_cache(image, x.result())
            )

        return *data, future

    with ThreadPoolExecutor(max_workers=50) as exc:
        for future in progress_bar(
            as_completed([exc.submit(_digest_worker, x) for x in digest_worker_queue]),
            count=len(digest_worker_queue),
            prefix="Getting tag digests:" + " " * 6,
        ):
            kind, tag, digest = future.result()
            if isinstance(digest, Future):
                digest = digest.result()

            b62 = hex_to_base62(digest)
            if b62 not in digest_info:
                digest_info[b62] = ([], digest)

            digest_info[b62] = (digest_info[b62][0] + [tag], digest)

    # TODO remove all delta tags that are not used

    def flatten(
        d: dict[str, dict[str, tuple[str, int]]],
    ) -> Iterable[tuple[dict[str, tuple[str, int]], str, tuple[str, int]]]:
        for _, inner_dict in d.items():
            for key, value in inner_dict.items():
                yield inner_dict, key, value

    for d, key, (tag, _size) in progress_bar(
        flatten(graph),
        count=len(list(flatten(graph))),
        prefix="Calculating sizes:" + " " * 8,
    ):
        d[key] = (tag, image_size_cached(f"{REPO}:{tag}"))

    labels: dict[str, str] = {}
    for b62, (tags, digest) in progress_bar(
        digest_info.items(), prefix="Generating tag labels:" + " " * 4
    ):
        for tag in tags:
            labels[f"tag.{tag}"] = digest

    b62_list = list(digest_info.keys())
    delta_map: defaultdict[str, dict[str, list[str]]] = defaultdict(dict)

    def _delta_worker(data: tuple[str, str]) -> tuple[str, str, int, list[str]] | None:
        a_b62, b_b62 = data
        cost, path = shortest_path(a_b62, b_b62, graph)
        if cost is None or not path:
            return None

        return b_b62, a_b62, cost, path

    with ThreadPoolExecutor(max_workers=50) as exc:
        combinations = list(itertools.combinations(b62_list, 2))
        for future in progress_bar(
            as_completed([exc.submit(_delta_worker, x) for x in combinations]),
            count=len(combinations),
            prefix="Calculating deltas:" + " " * 7,
        ):
            item = future.result()
            if item is None:
                continue

            b_b62, a_b62, cost, path = item
            sizes = [
                x
                for t in digest_info[b_b62][0]
                for x in [_image_size_cached(f"{REPO}:{t}")]
            ]
            b_direct: int = min(
                [x for x in sizes if not isinstance(x, Future)]
                + cast(
                    list[int],
                    list(as_completed([x for x in sizes if isinstance(x, Future)])),
                ),
            )
            if cost >= b_direct * MAX_SIZE_RATIO:
                continue

            delta_map[b_b62][a_b62] = path

    for b_b62, item in progress_bar(
        delta_map.items(),
        prefix="Generating map labels:" + " " * 4,
    ):
        labels[f"map.{b_b62}"] = json.dumps(item, separators=(",", ":"), indent=2)

    labels["timestamp"] = datetime.now(tz=UTC).replace(microsecond=0).isoformat() + "Z"
    with tempfile.TemporaryDirectory() as tmpdir:
        containerfile = os.path.join(tmpdir, "Containerfile")
        with open(containerfile, "w") as f:
            _ = f.write("FROM scratch\nLABEL \\")
            for k, v in progress_bar(
                labels.items(), prefix="Generating Containerfile: "
            ):
                _ = f.write(f'\n  arkes.manifest.{k}="{escape_label(v)}" \\')

            _ = f.write('\n  arkes.manifest.version="1"\n')

        image = f"{REPO}:_manifest"
        print(f"Building {image}...")
        try:
            chronic(
                podman_cmd(
                    "build",
                    f"--tag={image}",
                    f"--file={containerfile}",
                    tmpdir,
                )
            )

        except:
            with (
                open(containerfile, "r") as f,
                open("/tmp/manifest.Containerfile", "w") as out,
            ):
                _ = out.write(f.read())

            raise
        if cast(bool, args.push):
            podman("push", image)


def _classify_tag(tag: str) -> tuple[str, str | None, str | None]:
    if tag == "_manifest":
        return "manifest", None, None

    if tag.startswith("_diff-"):
        if len(tag) != 93 or tag[49] != "-":
            return "other", None, None

        src_b62 = tag[6:49]
        dst_b62 = tag[50:]
        if len(src_b62) != 43 or len(dst_b62) != 43:
            return "other", None, None

        return "diff", src_b62, dst_b62

    if "_" not in tag:
        if all(c.isalnum() or c == "-" for c in tag):
            return "variant", tag, None

        return "other", None, None

    sep_idx = tag.rfind("_")
    if sep_idx <= 0:
        return "other", None, None

    variant = tag[:sep_idx]
    rest = tag[sep_idx + 1 :]
    if not (variant and all(c.isalnum() or c == "-" for c in variant)):
        return "other", None, None

    if "." in rest:
        last_dot = rest.rfind(".")
        if last_dot > 0:
            build_num = rest[last_dot + 1 :]
            if build_num.isdigit():
                version_part = rest[:last_dot]
                full_version = f"{version_part}.{build_num}"
                return "build", variant, full_version

    if rest and all(c.isalnum() or c in ".-" for c in rest):
        return "version", variant, rest

    return "other", None, None


def shortest_path(
    a: str, b: str, graph: dict[str, dict[str, tuple[str, int]]]
) -> tuple[int | None, list[str] | None]:
    if a == b:
        return 0, []

    queue = deque([(a, 0, cast(list[str], []))])
    visited: dict[str, tuple[int, list[str]]] = {a: (0, [])}
    while queue:
        node, cost, path = queue.popleft()
        for neigh, (tag, sz) in graph.get(node, {}).items():
            if sz == -1:
                continue

            new_cost = cost + sz
            if neigh not in visited or new_cost < visited[neigh][0]:
                visited[neigh] = (new_cost, path + [tag])
                queue.append((neigh, new_cost, path + [tag]))

    return visited.get(b, (None, None))


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
