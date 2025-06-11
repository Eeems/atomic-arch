import os
import sys
import json
import subprocess

from argparse import ArgumentParser
from argparse import Namespace
from typing import Callable, cast
from typing import Any

from ..system import _execute as __execute  # pyright:ignore [reportPrivateUsage]

_execute = cast(Callable[[str], int], __execute)

kwds = {"help": "Display the weather"}

ICONS = [
    "✨",
    "☁️",
    "🌫",
    "🌧",
    "🌧",
    "❄️",
    "❄️",
    "🌦",
    "🌦",
    "🌧",
    "🌧",
    "🌨",
    "🌨",
    "⛅️",
    "☀️",
    "🌩",
    "⛈",
    "⛈",
    "☁️",
]


def register(parser: ArgumentParser):
    _ = parser.add_argument(
        "--waybar", action="store_true", help="Output short waybar information"
    )
    _ = parser.add_argument(
        "--ready",
        action="store_true",
        help="Check if ready to display weather information",
    )


def command(args: Namespace):
    useWego = os.path.exists(os.path.expanduser("~/.wegorc"))
    if cast(bool, args.ready):
        if useWego:
            return

        res = _execute("ping -c 1 wttr.in")
        if res:
            sys.exit(res)

        return

    if not cast(bool, args.waybar):
        cmd = "wego" if useWego else "curl wttr.in"
        res = _execute(f"{cmd} | less -R")
        if res:
            sys.exit(res)

        return

    if not useWego:
        res = _execute(
            'echo "$(curl --silent wttr.in?format=%t%c | xargs)\n$(curl --silent wttr.in?format=%l:%20%C%c%0DWind:%20%w%0DPrecipitation:%20%p%0DPressure:%20󰷃%P%0DUV%Index:%20󱟾%20%u)\n"'
        )
        if res:
            sys.exit(res)

        return

    data = cast(
        dict[str, dict[str, str | float | int]],
        json.loads(subprocess.check_output(["wego", "-f", "json", "-jsn-no-indent"])),
    )
    current = data["Current"]
    icon = ICONS[cast(int, current["Code"])]
    temp = int(cast(str, current["TempC"]))
    if temp > 0:
        temp = f"+{temp}"

    temp = f"{temp}⁰C"

    print(f"{icon} {temp}")
    location = "Edmonton"  # TODO - pull location from ~/.wegorc and get name
    print(f"{location}: {current['Desc']} {temp}")
    windspeed = int(cast(str, current["WindspeedKmph"]))
    print(f"Wind: {windspeed} kph")
    humidity = int(cast(str, current["Humidity"]))
    print(f"Humidity: {humidity}%")
    precipitation = int(cast(str, current["PrecipM"]))
    print(f"Precipitation: {precipitation} mm/3 hours")
    # TODO display pressure and uv index


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
