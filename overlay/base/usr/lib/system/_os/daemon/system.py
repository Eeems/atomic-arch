import dbus  # pyright:ignore [reportMissingTypeStubs]
import dbus.service  # pyright:ignore [reportMissingTypeStubs]
import os
import subprocess
import threading

from typing import Callable

from ..podman import podman
from ..system import baseImage
from ..system import checkupdates
from ..system import upgrade
from ..dbus import groups_for_sender
from ..console import bytes_to_stdout
from ..console import bytes_to_stderr


class Object(dbus.service.Object):
    def __init__(self, bus_name: dbus.service.BusName):
        super().__init__(  # pyright:ignore [reportUnknownMemberType]
            bus_name=bus_name,
            object_path="/system",
        )
        self._updates: list[str] = []
        self._notification: dict[str, str] = {}
        self._upgrade_status: str = ""
        self._pull_status: str = ""
        self._checkupdates_status: str = ""
        self._upgrade_thread: threading.Thread | None = None
        self._pull_thread: threading.Thread | None = None
        self._checkupdates_thread: threading.Thread | None = None

    def notify_all(self, msg: str, action: str):
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
            if action in self._notification:
                args.append(f"--replace-id={self._notification[action]}")

            self._notification[action] = (
                subprocess.check_output([*args, msg]).strip().decode("utf-8")
            )

    @dbus.service.method(  # pyright:ignore [reportUnknownMemberType]
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

            if self._upgrade_status == "pending":
                success()
                return

            assert self._upgrade_thread is None
            self.upgrade_status("pending")
            self._upgrade_thread = threading.Thread(target=self._upgrade)
            self._upgrade_thread.start()
            success()

        except BaseException as e:
            error(e)

    def _upgrade(self):
        self.notify_all("Starting system upgrade", "upgrade")
        try:
            upgrade(onstdout=self.upgrade_stdout, onstderr=self.upgrade_stderr)
            self.upgrade_status("success")
            self.notify_all("System upgrade complete, reboot required", "upgrade")

        except BaseException as e:
            self.upgrade_stderr(str(e).encode("utf-8"))
            self.upgrade_status("error")
            self.notify_all("System upgrade failed", "upgrade")

        finally:
            self._upgrade_thread = None

        return False

    @dbus.service.signal(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.upgrade",
        signature="s",
    )
    def upgrade_status(self, status: str):
        self._upgrade_status = status
        print(f"upgrade status: {status}")

    @dbus.service.signal(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.upgrade",
        signature="s",
    )
    def upgrade_stdout(self, stdout: bytes):
        bytes_to_stdout(stdout)

    @dbus.service.signal(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.upgrade",
        signature="s",
    )
    def upgrade_stderr(self, stderr: bytes):
        bytes_to_stderr(stderr)

    @dbus.service.method(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.upgrade",
        out_signature="s",
    )
    def status(self) -> str:
        return self._upgrade_status

    @dbus.service.method(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.checkupdates",
        in_signature="",
        out_signature="",
        sender_keyword="sender",
        async_callbacks=("success", "error"),
    )
    def checkupdates(
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

            if self._checkupdates_status == "pending":
                success()
                return

            assert self._checkupdates_thread is None
            self.checkupdates_status("pending")
            self._checkupdates_thread = threading.Thread(target=self._checkupdates)
            self._checkupdates_thread.start()
            success()

        except BaseException as e:
            error(e)

    def _checkupdates(self):
        try:
            self._updates = checkupdates()
            if not self._updates:
                self.checkupdates_status("none")

            else:
                self.checkupdates_status("available")
                self.notify_all(
                    f"{len(self._updates)} updates available:\n"
                    + "\n".join(self._updates),
                    "checkupdates",
                )

        except BaseException as e:
            self.checkupdates_stderr(str(e).encode("utf-8"))
            self.checkupdates_status("error")
            self.notify_all("Failed to checkupdates base image", "checkupdates")
            raise

        finally:
            self._checkupdates_thread = None

        return False

    @dbus.service.signal(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.checkupdates",
        signature="s",
    )
    def checkupdates_status(self, status: str):
        self._checkupdates_status = status
        print(f"checkupdates status: {status}")

    @dbus.service.signal(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.checkupdates",
        signature="s",
    )
    def checkupdates_stderr(self, stderr: bytes):
        bytes_to_stderr(stderr)

    @dbus.service.method(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.checkupdates",
        in_signature="",
        out_signature="as",
    )
    def updates(self) -> list[str]:
        return self._updates

    @dbus.service.method(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.pull",
        in_signature="",
        out_signature="",
        sender_keyword="sender",
        async_callbacks=("success", "error"),
    )
    def pull(
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

            if self._pull_status == "pending":
                success()
                return

            assert self._pull_thread is None
            self.pull_status("pending")
            self._pull_thread = threading.Thread(target=self._pull)
            self._pull_thread.start()
            success()

        except BaseException as e:
            error(e)

    def _pull(self):
        self.notify_all("Pulling base image", "pull")
        try:
            image = baseImage()
            podman(
                "pull",
                image,
                onstdout=self.pull_stdout,
                onstderr=self.pull_stderr,
            )
            self.pull_status("success")
            self.notify_all("Base image pulled", "pull")

        except BaseException as e:
            self.pull_stderr(str(e).encode("utf-8"))
            self.pull_status("error")
            self.notify_all("Failed to pull base image", "pull")
            raise

        finally:
            self._pull_thread = None

        return False

    @dbus.service.signal(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.pull",
        signature="s",
    )
    def pull_status(self, status: str):
        self._pull_status = status
        print(f"pull status: {status}")

    @dbus.service.signal(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.pull",
        signature="s",
    )
    def pull_stdout(self, stdout: bytes):
        bytes_to_stdout(stdout)

    @dbus.service.signal(  # pyright:ignore [reportUnknownMemberType]
        dbus_interface="system.pull",
        signature="s",
    )
    def pull_stderr(self, stderr: bytes):
        bytes_to_stderr(stderr)
