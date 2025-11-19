import sys
import os

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import is_root
from . import in_system
from . import REPO

kwds: dict[str, str] = {
    "help": "Scan a container",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "target",
        metavar="VARIANT",
        help="Variant to scan",
    )


def command(args: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    os.makedirs(".trivy", exist_ok=True)
    volumes: list[str] = ["./.trivy:/trivy"]
    in_ci = "CI" in os.environ
    if in_ci:
        volumes.append("./markdown.tpl:/template")

    ret = in_system(
        "-c",
        f"""
        set -e
        /usr/lib/system/initialize_pacman
        /usr/lib/system/install_packages trivy
        if [[ "{"x" if in_ci else ""}" == "" ]]; then
            trivy rootfs \
                --cache-dir /trivy \
                --skip-dirs=/ostree \
                --skip-dirs=/sysroot \
                --skip-dirs=/var/lib/system \
                --skip-dirs=/usr/share/doc \
                --skip-dirs=/usr/share/man \
                --skip-dirs=/trivy \
                --skip-files=/usr/bin/trivy \
                --skip-files=/usr/lib/qt6/mkspecs/features/data/testserver/Dockerfile \
                --scanners vuln,misconfig,secret \
                /
        else
            trivy rootfs \
                --cache-dir /trivy \
                --format json \
                --output /trivy/report.json \
                --skip-dirs=/ostree \
                --skip-dirs=/sysroot \
                --skip-dirs=/var/lib/system \
                --skip-dirs=/usr/share/doc \
                --skip-dirs=/usr/share/man \
                --skip-dirs=/trivy \
                --skip-files=/usr/bin/trivy \
                --skip-files=/usr/lib/qt6/mkspecs/features/data/testserver/Dockerfile \
                --scanners vuln,misconfig,secret \
                /
            trivy convert \
                --format sarif \
                /trivy/report.json \
            > /trivy/report.sarif
            trivy convert \
                --format template \
                --template "@/template" \
                /trivy/report.json \
            > /trivy/report.md
            trivy convert \
                --format table \
                /trivy/report.json
        fi
        """,
        target=f"{REPO}:{cast(str, args.target)}",
        entrypoint="/bin/bash",
        volumes=volumes,
    )
    if ret:
        sys.exit(ret)


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
