import os
import sys
import xattr  # pyright:ignore [reportMissingTypeStubs]

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Callable

from ..system import is_root
from ..system import execute

xattrList = cast(
    Callable[[str], list[bytes]],
    getattr(xattr, "list"),
)
xattrRemove = cast(
    Callable[[str, bytes], None],
    getattr(xattr, "remove"),
)


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    os.makedirs("/var/ostree/state-overlays/opt/work", 0o775, exist_ok=True)
    os.makedirs("/var/ostree/state-overlays/opt/work", 0o775, exist_ok=True)
    os.makedirs("/var/ostree/state-overlays/opt/upper", 0o775, exist_ok=True)
    if not os.path.ismount("/opt"):
        # Work around ESTALE issue
        # https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt
        rmfattr("/var/ostree/state-overlays/opt/upper", b"trusted.overlay.origin")
        rmfattr("/var/ostree/state-overlays/opt/upper", b"trusted.overlay.uuid")
        execute("ostree", "admin", "state-overlay", "opt", "/opt")

    os.chmod("/var/ostree/state-overlays/opt", 0o755)


def rmfattr(path: str, attr: bytes):
    if attr in xattrList(path):
        xattrRemove(path, attr)


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
