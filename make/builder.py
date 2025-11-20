import os
import shutil
import subprocess

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import BUILDER
from . import podman

kwds: dict[str, str] = {
    "help": f"Build the {BUILDER} image",
}


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    args = []
    if shutil.which("niri") is not None:
        gomodcache = subprocess.check_output(["go", "env", "GOMODCACHE"])
        if gomodcache and os.path.exists(gomodcache):
            args.append(f"--volume={gomodcache}:/go/pkg/mod")
            print(f"Using GOMODCACHE: {gomodcache}")

    podman(
        "build",
        f"--tag={BUILDER}",
        *args,
        "--file=tools/builder/Containerfile",
        ".",
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
