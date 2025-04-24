#!/usr/bin/python
import subprocess

from time import time

_ = subprocess.check_call(
    [
        "podman",
        "--remote",
        "build",
        "--tag",
        "system:latest",
        "--tag",
        f"system:{int(time())}",
        "--file",
        "/etc/system/Systemfile",
    ]
)
