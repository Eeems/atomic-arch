import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Any

from . import execute
from . import ostree
from . import OS_NAME
from . import is_root

RETAIN = 5

kwds = {"help": "Revert the last system upgrade"}


def register(parser: ArgumentParser):
    _ = parser.add_argument("--branch", default="system", help="System branch to prune")


def command(_: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    prune(cast(str, args.branch))


def prune(branch: str = "system"):
    ostree(
        "prune",
        "--commit-only",
        f"--retain-branch-depth={branch}={RETAIN}",
        f"--only-branch={OS_NAME}/{branch}",
        "--keep-younger-than=1 second",
    )
    execute("ostree", "admin", "cleanup")


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
