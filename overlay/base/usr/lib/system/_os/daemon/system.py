import os
import subprocess
import dbus
import dbus.service
import traceback

from ..system import upgrade
from ..system import execute
from ..system import checkupdates


class Object(dbus.service.Object):
    def __init__(self, bus_name):
        super().__init__(bus_name, "/system")

    @dbus.service.method(
        dbus_interface="system.upgrade", in_signature="", out_signature=""
    )
    def upgrade(self):
        try:
            self.upgrade_status("pending")
            upgrade()
            self.upgrade_status("success")

        except BaseException:
            traceback.print_exc()
            self.upgrade_status("error")

    @dbus.service.signal(dbus_interface="system.upgrade", signature="s")
    def upgrade_status(self, status: str):
        pass

    @dbus.service.method(
        dbus_interface="system.checkupdates", in_signature="", out_signature=""
    )
    def checkupdates(self):
        try:
            self.upgrade_status("pending")
            if not checkupdates():
                self.checkupdates_status("none")
                return

            self.checkupdates_status("available")
            for path in os.scandir("/run/user"):
                if not path.is_dir():
                    continue

                uid = path.name
                if uid == "0":
                    continue

                user = (
                    subprocess.check_output(["id", "-u", "-n", uid])
                    .decode("utf-8")
                    .strip()
                )
                execute(
                    "sudo",
                    "-u",
                    user,
                    f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
                    "notify-send",
                    "Updates detected",
                )

        except BaseException:
            traceback.print_exc()
            self.checkupdates_status("error")

    @dbus.service.signal(dbus_interface="system.checkupdates", signature="s")
    def checkupdates_status(self, status: str):
        pass
