import os
import sys
import pty
import select
import tempfile
import termios
import subprocess

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import image_exists
from .pull import pull

kwds: dict[str, str] = {
    "help": "Open a builder shell similar to what runs in github actions",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--branch",
        default=None,
        help="Which branch of builder to use, defaults to the current checked out branch.",
    )


def command(args: Namespace):
    branch = cast(str | None, args.branch)
    if branch is None:
        branch = (
            subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            .decode("utf-8")
            .strip()
        )

    image = f"ghcr.io/eeems/arkes-builder:{branch}"
    if not image_exists(image, False, True):
        if not image_exists(image, True, True):
            print(f"{image} does not exist")
            sys.exit(1)

        pull(image)

    master_fd, slave_fd = pty.openpty()
    with tempfile.TemporaryDirectory() as tmpdir:
        __e = os.path.join(tmpdir, "__e")
        os.makedirs(__e)
        __t = os.path.join(tmpdir, "__t")
        os.makedirs(__t)
        _temp = os.path.join(tmpdir, "_temp")
        _github_home = os.path.join(_temp, "_github_home")
        os.makedirs(_github_home)
        _github_workflow = os.path.join(_temp, "_github_workflow")
        os.makedirs(_github_workflow)
        _actions = os.path.join(tmpdir, "_actions")
        os.makedirs(_actions)
        __w = os.path.join(tmpdir, "__w")
        os.makedirs(__w)
        proc = subprocess.Popen(
            [
                "docker",
                "run",
                "--rm",
                "-it",
                "--workdir=/__w/arkes/arkes",
                "--privileged",
                "--security-opt=seccomp=unconfined",
                "--security-opt=apparmor=unconfined",
                "--cap-add=SYS_ADMIN",
                "--cap-add=NET_ADMIN",
                "--device=/dev/fuse",
                "--tmpfs=/tmp",
                "--tmpfs=/run",
                "--userns=host",
                "--volume=/:/run/host",
                "--env=HOME=/github/home",
                "--env=GITHUB_ACTIONS=true",
                "--env=CI=true",
                "--volume=/var/run/docker.sock:/var/run/docker.sock",
                f"--volume={__w}:/__w",
                f"--volume={os.path.realpath('.')}:/__w/arkes/arkes:O",
                f"--volume={__e}:/__e:ro",
                f"--volume={_temp}:/__w/temp",
                f"--volume={_actions}:/__w/_actions",
                f"--volume={__t}:/__t",
                f"--volume={_github_home}:/github/home",
                f"--volume={_github_workflow}:/github/workflow",
                f"--volume={os.path.realpath('seccomp.json')}:/etc/containers/seccomp.json",
                "--entrypoint=/usr/bin/bash",
                image,
                "-c",
                "\n".join(
                    [
                        "cp /etc/resolv.conf /etc/hosts /etc/hostname /tmp/",
                        "mount --make-rprivate /",
                        "umount /etc/resolv.conf /etc/hosts /etc/hostname",
                        "mv /tmp/resolv.conf /tmp/hosts /tmp/hostname /etc/",
                        "mkdir -p /github/home/.docker /home/runner",
                        "if ! [ -f /github/home/.docker/config.json ];then",
                        "  echo '{\"auths\":{}}' > /github/home/.docker/config.json",
                        "fi",
                        "mkdir -p /run/podman $TMPDIR",
                        "podman system service --time 0 unix:///run/podman/podman.sock &",
                        "_pid=$!",
                        "trap 'echo \"Goodbye\" && kill $_pid && wait $_pid || true' EXIT",
                        "bash",
                    ]
                ),
            ],
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
