import os
import sys
import pty
import select
import termios
import subprocess

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import image_exists
from . import podman_cmd
from .pull import pull

kwds: dict[str, str] = {
    "help": "Open the shell for a variant",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--variant",
        default="base",
        help="Which variant to use, defaults to base.",
    )


def command(args: Namespace):
    image = f"ghcr.io/eeems/arkes:{cast(str, args.variant)}"
    if not image_exists(image, False, True):
        if not image_exists(image, True, True):
            print(f"{image} does not exist")
            sys.exit(1)

        pull(image)

    shell(*podman_cmd("run", "--rm", "-it", image))


def shell(*args: str):
    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        args,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)
    old_tty = termios.tcgetattr(sys.stdin.fileno())
    try:
        import tty

        _ = tty.setraw(sys.stdin.fileno())
        while proc.poll() is None:
            r, _, _ = select.select([sys.stdin.fileno(), master_fd], [], [], 0.1)
            if sys.stdin.fileno() in r:
                data = os.read(sys.stdin.fileno(), 1024)
                if not data:
                    break

                _ = os.write(master_fd, data)

            if master_fd in r:
                try:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break

                    _ = os.write(sys.stdout.fileno(), data)

                except OSError as e:
                    if e.errno == 5:
                        break

    except KeyboardInterrupt:
        pass

    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_tty)
        _ = proc.wait()


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
