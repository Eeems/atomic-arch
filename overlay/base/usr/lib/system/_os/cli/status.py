from argparse import ArgumentParser
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor

from .. import OS_NAME

from ..system import baseImage
from ..ostree import deployments


def register(_: ArgumentParser):
    pass


def get_status(data: tuple[int, str, str]) -> str:
    index, checksum, type = data
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

    ref = baseImage(f"/ostree/deploy/{OS_NAME}/deploy/{checksum}/etc/system/Systemfile")
    version = osInfo.get("VERSION", "0")
    version_id = osInfo.get("VERSION_ID", "0")
    build_id = osInfo.get("BUILD_ID", "0")
    status = f"{index}: {ref}"
    if type:
        status += f" ({type})"

    status += f"\n  Version: {version}.{version_id}"
    status += f"\n  Build:   {build_id}"
    return status


def command(_: Namespace):
    with ThreadPoolExecutor(max_workers=50) as exc:
        for status in exc.map(get_status, deployments()):
            print(status)


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
