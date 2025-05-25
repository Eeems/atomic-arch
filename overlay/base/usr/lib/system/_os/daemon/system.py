import os
import subprocess
import dbus
import dbus.service
import traceback

from ..system import execute
from ..system import execute_pipe


class Object(dbus.service.Object):
    def __init__(self, bus_name):
        super().__init__(bus_name, "/system")
        self._updates: list[str] = []

    def notify_all(self, msg: str):
        for path in os.scandir("/run/user"):
            if not path.is_dir():
                continue

            uid = path.name
            if uid == "0":
                continue

            user = (
                subprocess.check_output(["id", "-u", "-n", uid]).decode("utf-8").strip()
            )
            # TODO use org.freedesktop.Notifications over dbus intead
            execute(
                "sudo",
                "-u",
                user,
                f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
                "notify-send",
                "--urgency=normal",
                msg,
            )

    @dbus.service.method(
        dbus_interface="system.upgrade", in_signature="", out_signature=""
    )
    def upgrade(self):
        self.upgrade_status("pending")
        self.notify_all("Starting system upgrade")
        res = execute_pipe(
            "/usr/bin/os",
            "upgrade",
            onstderr=self.upgrade_sterr,
            onstdout=self.upgrade_stout,
        )
        if res:
            self.upgrade_status("error")
            self.notify_all("System upgrade failed")
            return

        self.upgrade_status("success")
        self.notify_all("System upgrade complete, reboot required")

    @dbus.service.signal(dbus_interface="system.upgrade", signature="s")
    def upgrade_status(self, status: str):
        pass

    @dbus.service.signal(dbus_interface="system.upgrade", signature="s")
    def upgrade_stout(self, stdout: bytes):
        pass

    @dbus.service.signal(dbus_interface="system.upgrade", signature="s")
    def upgrade_sterr(self, stdout: bytes):
        pass

    @dbus.service.method(
        dbus_interface="system.checkupdates", in_signature="", out_signature=""
    )
    def checkupdates(self):
        updates: list[str] = []

        def parse_line(line: bytes):
            updates.append(line.strip().decode("utf-8"))

        self.upgrade_status("pending")
        res = execute_pipe(
            "/usr/bin/os",
            "checkupdates",
            onstdout=parse_line,
        )
        if res == 0:
            self.checkupdates_status("none")
            return

        if res == 1:
            self.checkupdates_status("error")
            return

        self._updates = updates
        self.checkupdates_status("available")
        self.notify_all(f"{len(updates)} updates available")

    @dbus.service.signal(dbus_interface="system.checkupdates", signature="s")
    def checkupdates_status(self, status: str):
        pass

    @dbus.service.method(
        dbus_interface="system.checkupdates", in_signature="", out_signature="as"
    )
    def updates(self) -> list[str]:
        return self._updates
