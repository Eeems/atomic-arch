import dbus  # pyright:ignore [reportMissingTypeStubs]
import dbus.service  # pyright:ignore [reportMissingTypeStubs]
import os
import sys
import subprocess
import threading

from typing import cast
from typing import Callable
from gi.repository import GLib

from ..system import checkupdates
from ..system import upgrade
from ..dbus import groups_for_sender
from ..console import bytes_to_stdout
from ..console import bytes_to_stderr


class Object(dbus.service.Object):
    def __init__(self, bus_name: dbus.service.BusName):
        super().__init__(bus_name=bus_name, object_path="/system")
        self._updates: list[str] = []
        self._notification: str | None = None
        self._status: str = ""
        self._thread: threading.Thread | None = None

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
            args = [
                "sudo",
                "-u",
                user,
                f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus",
                "notify-send",
                "--print-id",
                "--urgency=normal",
            ]
            if self._notification is not None:
                args.append(f"--replace-id={self._notification}")

            self._notification = (
                subprocess.check_output([*args, msg]).strip().decode("utf-8")
            )

    @dbus.service.method(
        dbus_interface="system.upgrade",
        sender_keyword="sender",
        async_callbacks=("success", "error"),
    )
    def upgrade(
        self,
        success: Callable[[], None],
        error: Callable[..., None],
        sender: str | None = None,
    ):
        try:
            assert sender is not None
            if not set(["adm", "wheel", "root"]) & groups_for_sender(self, sender):
                error("Permission denied")
                return

            if self._status == "pending":
                success()
                return

            assert self._thread is None
            self.upgrade_status("pending")
            self._thread = threading.Thread(target=self._upgrade)
            self._thread.start()
            success()

        except BaseException as e:
            error(e)

    def _upgrade(self):
        self.notify_all("Starting system upgrade")
        try:
            upgrade(onstdout=self.upgrade_stdout, onstderr=self.upgrade_stderr)
            self.upgrade_status("success")
            self.notify_all("System upgrade complete, reboot required")

        except BaseException as e:
            self.upgrade_stderr(str(e).encode("utf-8"))
            self.upgrade_status("error")
            self.notify_all("System upgrade failed")

        self._thread = None
        return False

    @dbus.service.signal(dbus_interface="system.upgrade", signature="s")
    def upgrade_status(self, status: str):
        self._status = status

    @dbus.service.signal(dbus_interface="system.upgrade", signature="s")
    def upgrade_stdout(self, stdout: bytes):
        bytes_to_stdout(stdout)

    @dbus.service.signal(dbus_interface="system.upgrade", signature="s")
    def upgrade_stderr(self, stderr: bytes):
        bytes_to_stderr(stderr)

    @dbus.service.method(dbus_interface="system.upgrade", out_signature="s")
    def status(self) -> str:
        return self._status

    @dbus.service.method(
        dbus_interface="system.checkupdates",
        in_signature="",
        out_signature="b",
        sender_keyword="sender",
    )
    def checkupdates(self, sender: str | None = None) -> bool:
        assert sender is not None
        if not set(["adm", "wheel", "root"]) & groups_for_sender(self, sender):
            raise Exception("Permission denied")

        updates: list[str] = []

        def parse_line(line: bytes):
            updates.append(line.strip().decode("utf-8"))

        self.checkupdates_status("pending")
        try:
            self._updates = checkupdates()

        except BaseException as e:
            self.checkupdates_status("error")
            raise

        if not self._updates:
            self.checkupdates_status("none")
            return False

        self.checkupdates_status("available")
        self.notify_all(
            f"{len(self._updates)} updates available:\n" + "\n".join(self._updates)
        )
        return True

    @dbus.service.signal(dbus_interface="system.checkupdates", signature="s")
    def checkupdates_status(self, status: str):
        pass

    @dbus.service.method(
        dbus_interface="system.checkupdates", in_signature="", out_signature="as"
    )
    def updates(self) -> list[str]:
        return self._updates
