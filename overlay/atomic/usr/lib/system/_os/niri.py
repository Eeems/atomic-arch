import subprocess

from .system import chronic


def getOutputs() -> dict[str, dict[str, str]]:
    lines = (
        subprocess.check_output(["niri", "msg", "outputs"])
        .strip()
        .decode("utf-8")
        .split("\n")
    )
    outputs: dict[str, dict[str, str]] = {}
    current = None
    for line in lines:
        if line.startswith('Output "'):
            data = line.split('"', 3)
            current = data[2][2:-1]
            outputs[current] = {"name": data[1]}

        elif current is None:
            continue

        elif line.startswith("  Current Mode: "):
            outputs[current]["mode"] = line[16:].split("(", 1)[0]

        elif line.startswith("  Scale: "):
            outputs[current]["scale"] = line[9:]

    return outputs


def getOutputScale(display: str) -> int:
    return int(float(getOutputs()[display]["scale"]) * 100)


def setOutputScale(display: str, scale: int) -> int:
    if scale < 20:
        scale = 20

    chronic("niri", "msg", "output", display, "scale", str(scale / 100))
    return getOutputScale(display)


def getVolumeOut() -> int:
    return int(
        [
            float(x[8:])
            for x in subprocess.check_output(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]
            )
            .strip()
            .decode("utf-8")
            .split("\n")
            if x.startswith("Volume: ")
        ][0]
        * 100
    )


def setVolumeOut(volume: int, maxVolume: int = 100) -> int:
    if volume > maxVolume:
        volume = maxVolume

    elif volume < 0:
        volume = 0

    chronic("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume}%")
    return getVolumeOut()


def getVolumeIn() -> int:
    return int(
        [
            float(x[8:])
            for x in subprocess.check_output(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"]
            )
            .strip()
            .decode("utf-8")
            .split("\n")
            if x.startswith("Volume: ")
        ][0]
        * 100
    )


def setVolumeIn(volume: int, maxVolume: int = 100) -> int:
    if volume > maxVolume:
        volume = maxVolume

    elif volume < 0:
        volume = 0

    chronic("wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", f"{volume}%")
    return getVolumeIn()


def muteOut():
    chronic("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1")


def unmuteOut():
    chronic("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0")


def toggleMuteOut():
    chronic("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle")


def muteIn():
    chronic("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1")


def unmuteIn():
    chronic("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "0")


def toggleMuteIn():
    chronic("wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle")
