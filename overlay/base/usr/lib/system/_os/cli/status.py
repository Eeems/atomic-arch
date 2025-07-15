from argparse import ArgumentParser
from argparse import Namespace

from .. import OS_NAME

from ..system import baseImage
from ..ostree import deployments


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    for index, checksum, type in deployments():
        with open(
            f"/ostree/deploy/{OS_NAME}/deploy/{checksum}/usr/lib/os-release", "r"
        ) as f:
            osInfo = {
                x[0]: x[1]
                for x in [
                    x.strip().split("=", 1)
                    for x in f.readlines()
                    if x.startswith("VERSION_ID=")
                    or x.startswith("VERSION=")
                    or x.startswith("BUILD_ID=")
                ]
            }

        ref = baseImage(
            f"/ostree/deploy/{OS_NAME}/deploy/{checksum}/etc/system/Systemfile"
        )
        print(f"{index}: {ref}", end="")
        if type:
            print(f" ({type})", end="")

        print()
        version = osInfo.get("VERSION", "0")
        version_id = osInfo.get("VERSION_ID", "0")
        print(f"  Version: {version}.{version_id}")
        build_id = osInfo.get("BUILD_ID", "0")[:19]
        print(f"  Build:   {build_id}")


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
