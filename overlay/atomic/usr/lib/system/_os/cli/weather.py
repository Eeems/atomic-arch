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

WEATHER_ICON = [
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
WIND_ICONS = [
    "↓",
    "↙",
    "←",
    "↖",
    "↑",
    "↗",
    "→",
    "↘",
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
    wegoRc = os.path.expanduser("~/.wegorc")
    useWego = os.path.exists(wegoRc)
    if useWego:
        with open(wegoRc, "r") as f:
            useWego = bool(
                [
                    x.split("=", 1)[1]
                    for x in f.read().splitlines()
                    if x.startswith("owm-api-key=")
                ]
            )

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
        print(
            (
                subprocess.check_output(["curl", "--silent", "wttr.in?format=%t%c"])
                .decode("utf-8")
                .replace("\n", "\r")
            )
        )
        print(
            subprocess.check_output(
                [
                    "curl",
                    "--silent",
                    "wttr.in?format=%l:%20%C%c%0AWind:%20%w%0APrecipitation:%20%p%0APressure:%20󰷃%P%0AUV%Index:%20󱟾%20%u",
                ]
            )
            .decode("utf-8")
            .replace("\n", "\r"),
            end="",
        )
        return

    data = cast(
        dict[str, dict[str, str | float | int]],
        json.loads(subprocess.check_output(["wego", "-f", "json", "-jsn-no-indent"])),
    )
    current = data["Current"]
    icon = WEATHER_ICON[cast(int, current["Code"])]
    temp = int(cast(str, current["TempC"]))
    if temp > 0:
        temp = f"+{temp}"

    temp = f"{temp}⁰C"

    print(f"{temp} {icon}")
    location = "Edmonton"  # TODO - pull location from ~/.wegorc and get name
    print(f"{location}: {current['Desc']} {icon}", end="\r")
    windspeed = int(cast(str, current["WindspeedKmph"]))
    direction = cast(int | None, current["WinddirDegree"])
    if direction is None:
        icon = "?"

    else:
        icon = WIND_ICONS[int(((direction + 22) % 360) / 45)]

    print(f"Wind: {icon} {windspeed} km/h", end="\r")
    humidity = int(cast(str, current["Humidity"]))
    print(f"Humidity: {humidity}%", end="\r")
    precipitation = round(float(current["PrecipM"]), 1)
    print(f"Precipitation:  {precipitation}mm", end="")
    # TODO display pressure and uv index


if __name__ == "__main__":
    parser = ArgumentParser(
        **cast(dict[str, Any], kwds),  # pyright:ignore [reportAny,reportExplicitAny]
    )
    register(parser)
    args = parser.parse_args()
    command(args)
