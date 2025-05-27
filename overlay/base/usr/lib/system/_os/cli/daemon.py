from ntpath import exists
import sys
import os
import importlib
import dbus
import dbus.service

from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from argparse import ArgumentParser
from argparse import Namespace
from glob import iglob

from ..system import is_root
from ..system import chronic


def register(_: ArgumentParser):
    pass


POLICY = """
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy user="root">
    <allow own="os.system"/>
  </policy>
  <policy context="default">
    <allow send_destination="os.system"/>
    <allow receive_sender="os.system" receive_type="signal"/>
  </policy>
</busconfig>
"""


def command(args: Namespace):  # pyright:ignore [reportUnusedParameter]
    if not is_root():
        print("Must be run as root")
        sys.exit(1)

    os.makedirs("/etc/dbus-1/system.d", exist_ok=True)
    with open("/etc/dbus-1/system.d/os.conf", "w") as f:
        _ = f.write(POLICY)

    chronic("systemctl", "reload", "dbus")
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    bus_name = dbus.service.BusName("os.system", bus)
    objects = []
    for file in iglob(os.path.join(os.path.dirname(__file__), "..", "daemon", "*.py")):
        if file.endswith("__.py"):
            continue

        name = os.path.splitext(os.path.basename(file))[0]
        parent = ".".join(__name__.split(".")[:-2])
        module = importlib.import_module(f"{parent}.daemon.{name}", parent)
        objects.append(module.Object(bus_name))

    loop = GLib.MainLoop()
    loop.run()


if __name__ == "__main__":
    parser = ArgumentParser()
    register(parser)
    args = parser.parse_args()
    command(args)
