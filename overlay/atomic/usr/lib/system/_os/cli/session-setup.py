import os

from collections.abc import Iterable
from argparse import ArgumentParser
from argparse import Namespace
from typing import cast

from .. import system


def register(_: ArgumentParser):
    pass


def command(_: Namespace):
    # TODO load settings from a config file
    for display in cast(
        Iterable[str],
        system.getOutputs().keys(),  # pyright:ignore [reportUnknownMemberType]
    ):
        system.setOutputScale(display, 100)

    # Ensure volumes are clipped to the max allowed
    system.setVolumeOut(system.getVolumeOut())
    system.setVolumeIn(system.getVolumeIn())
    if not os.path.exists("~/.config/waypaper/config.ini"):
        os.symlink("/usr/share/waypaper/config.ini", "~/.config/waypaper/config.ini")


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
