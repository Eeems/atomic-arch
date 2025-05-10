import subprocess
import sys

from argparse import ArgumentParser
from argparse import Namespace

from . import is_root
from . import OS_NAME


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    status = subprocess.check_output(["ostree", "admin", "status"])
    deployments = [
        x
        for x in status.decode("utf-8").split("\n")
        if not x.startswith("    origin refspec:") and f" {OS_NAME} " in x
    ]
    info: list[tuple[str, str]] = []
    for deployment in deployments:
        parts = deployment.split()
        if len(parts) == 2:
            checksum = parts[1]
            type = ""

        elif parts[0] == "*":
            checksum = parts[2]
            type = "current"
        else:
            checksum = parts[1]
            type = parts[2].strip("()")

        info.append((checksum, type))

    sizes = list(
        reversed(
            subprocess.check_output(
                [
                    "du",
                    "-hs",
                    *[
                        f"/ostree/deploy/{OS_NAME}/deploy/{c}"
                        for c, _ in reversed(info)
                    ],
                ]
            )
            .strip()
            .decode("utf-8")
            .split("\n")
        )
    )
    for data in info:
        checksum, type = data
        index = info.index(data)
        diffsize = sizes[index].split()[0]
        size = (
            subprocess.check_output(
                ["du", "-hs", f"/ostree/deploy/{OS_NAME}/deploy/{checksum}"]
            )
            .strip()
            .decode("utf-8")
            .split()[0]
        )
        print(f"{index}: {size} (+{diffsize})", end="")
        if type:
            print(f" ({type})", end="")

        print()

    size = size = (
        subprocess.check_output(["du", "-hs", f"/ostree/deploy/{OS_NAME}/deploy"])
        .strip()
        .decode("utf-8")
        .split()[0]
    )
    print(f"total: {size}")


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
