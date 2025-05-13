import argparse
import sys

from argparse import ArgumentParser
from argparse import Namespace
from typing import cast
from typing import Callable
from typing import Any

from ..niri import getVolumeIn
from ..niri import setVolumeIn
from ..niri import muteIn
from ..niri import unmuteIn
from ..niri import toggleMuteIn

kwds = {"help": "Control system volume"}


def register(parser: ArgumentParser):
    parser.set_defaults(parser=parser)
    subparsers = parser.add_subparsers()
    subparser = subparsers.add_parser("get", help="Get the current system volume")
    subparser.set_defaults(func2=command_get)
    subparser = subparsers.add_parser("mute", help="Mute the current system speakers")
    subparser.set_defaults(func2=command_mute)
    subparser = subparsers.add_parser(
        "unmute", help="Unmute the current system speakers"
    )
    subparser.set_defaults(func2=command_unmute)
    subparser = subparsers.add_parser(
        "toggle-mute", help="Mute the current system speakers"
    )
    subparser.set_defaults(func2=command_toggleMute)
    subparser = subparsers.add_parser("set", help="Set the current system volume")
    _ = subparser.add_argument(
        "volume",
        help="Volume percentage to set to. The value is in percentage, and can start with a + or - to be relative to the current value",
    )
    _ = subparser.add_argument(
        "--max-volume",
        default=100,
        type=int,
        help="Maximum volume percentage to allow",
        dest="maxVolume",
    )
    subparser.set_defaults(func2=command_set)


def command(args: Namespace):
    if not hasattr(args, "func2"):
        args.parser.print_help()  # pyright:ignore [reportAny]
        sys.exit(1)

    cast(Callable[[argparse.Namespace], None], args.func2)(args)


def command_get(_: Namespace):
    print(f"{getVolumeIn()}%")


def command_mute(_: Namespace):
    muteIn()


def command_unmute(_: Namespace):
    unmuteIn()


def command_toggleMute(_: Namespace):
    toggleMuteIn()


def command_set(args: Namespace):
    volume = cast(str, args.volume)
    if volume.startswith("+"):
        value = getVolumeIn() + int(volume[1:])

    elif volume.startswith("-"):
        value = getVolumeIn() - int(volume[1:])
    else:
        value = int(volume)

    maxVolume = cast(int, args.maxVolume)
    print(f"{setVolumeIn(value, maxVolume)}%")


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
