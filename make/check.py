import shlex
import json
import os
import sys
import shutil

from argparse import ArgumentParser
from argparse import Namespace
from typing import Any
from typing import cast

from . import image_qualified_name
from . import bytes_to_stderr
from . import bytes_to_stdout
from . import execute_pipe
from . import chronic
from . import _execute  # pyright: ignore[reportPrivateUsage]
from . import _osDir  # pyright: ignore[reportPrivateUsage]
from . import REPO
from . import IMAGE

kwds: dict[str, str] = {
    "help": "Check the codebase and ensure it follows standards",
}


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply any automatic fixes that can be applied",
    )


def command(args: Namespace):
    failed = False
    fix = cast(bool, args.fix)

    def _assert_name(name: str, expected: str) -> bool:
        image = image_qualified_name(name)
        if image == expected:
            return True

        print(f" Failed: image_qualified_name({json.dumps(name)})")
        print(f"  Expected: {json.dumps(expected)}")
        print(f"  Actual: {json.dumps(image)}")
        return False

    print("[check] Running tests")
    failed = failed or not _assert_name(
        "hello-world:latest@sha256:123",
        "docker.io/hello-world@sha256:123",
    )
    failed = failed or not _assert_name(
        "hello-world@sha256:123",
        "docker.io/hello-world@sha256:123",
    )
    failed = failed or not _assert_name(
        "hello-world:latest",
        "docker.io/hello-world:latest",
    )
    failed = failed or not _assert_name("hello-world", "docker.io/hello-world")
    failed = failed or not _assert_name("system:latest", "localhost/system:latest")
    failed = failed or not _assert_name(
        f"{REPO}:latest@sha256:123",
        f"{REPO}@sha256:123",
    )
    failed = failed or not _assert_name(f"{REPO}:latest", f"{REPO}:latest")
    failed = failed or not _assert_name(f"{REPO}@sha256:123", f"{REPO}@sha256:123")
    failed = failed or not _assert_name(REPO, REPO)
    failed = failed or not _assert_name(
        f"{IMAGE}:latest@sha256:123",
        f"{REPO}@sha256:123",
    )
    failed = failed or not _assert_name(f"{IMAGE}:latest", f"{REPO}:latest")
    failed = failed or not _assert_name(IMAGE, REPO)
    if shutil.which("niri") is not None:
        print("[check] Checking niri config", file=sys.stderr)
        cmd = shlex.join(
            [
                "niri",
                "validate",
                "--config=overlay/atomic/usr/share/niri/config.kdl",
            ]
        )
        res = _execute(cmd)
        if res:
            print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
            failed = True

    if shutil.which("gofmt") is not None:
        print("[check] Checking go formatting", file=sys.stderr)
        cmd = (
            ["gofmt", "-e"]
            + (["-w", "-l"] if fix else ["-d"])
            + ["tools/dockerfile2llbjson"]
        )
        gofmt_failed = False

        def _onstderr(data: bytes):
            nonlocal gofmt_failed
            gofmt_failed = True
            bytes_to_stderr(data)

        def _onstdout(data: bytes):
            nonlocal gofmt_failed
            gofmt_failed = True
            bytes_to_stdout(data)

        res = execute_pipe(*cmd, onstderr=_onstderr, onstdout=_onstdout)
        if res or gofmt_failed:
            print(
                f"[check] Failed: {shlex.join(cmd)}\nStatus code: {res}",
                file=sys.stderr,
            )
            failed = True

    if shutil.which("go") is not None:
        cwd = os.getcwd()
        print("[check] Analyzing go code", file=sys.stderr)
        cmd = shlex.join(["go", "vet"])
        os.chdir("tools/dockerfile2llbjson")
        res = _execute(cmd)
        os.chdir(cwd)
        if res:
            print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
            failed = True

    print("[check] Setting up venv", file=sys.stderr)
    if not os.path.exists(".venv/bin/activate"):
        chronic("python", "-m", "venv", ".venv")

    chronic(
        "bash",
        "-ec",
        ";".join(
            [
                "source .venv/bin/activate",
                "pip install "
                + " ".join(
                    [
                        "ruff",
                        "basedpyright",
                        "requests",
                        "dbus-python",
                        "PyGObject",
                        "xattr",
                    ]
                ),
            ]
        ),
    )
    cmd = shlex.join(
        [
            "bash",
            "-ec",
            ";".join(
                [
                    "source .venv/bin/activate",
                    f"ruff check {'--fix' if fix else ''} .",
                ]
            ),
        ]
    )
    print("[check] Checking python formatting", file=sys.stderr)
    res = _execute(cmd)
    if res:
        print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
        failed = True

    cmd = shlex.join(
        [
            "bash",
            "-ec",
            ";".join(
                [
                    "source .venv/bin/activate",
                    shlex.join(
                        [
                            "basedpyright",
                            "--pythonversion=3.12",
                            "--pythonplatform=Linux",
                            "--venvpath=.venv",
                            "make.py",
                            f"{_osDir}",
                        ]
                    ),
                ]
            ),
        ]
    )
    print("[check] Checking python types", file=sys.stderr)
    res = _execute(cmd)
    if res:
        print(f"[check] Failed: {cmd}\nStatus code: {res}", file=sys.stderr)
        failed = True

    if failed:
        print("[check] One or more checks failed", file=sys.stderr)
        sys.exit(1)

    print("[check] All checks passed", file=sys.stderr)


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
