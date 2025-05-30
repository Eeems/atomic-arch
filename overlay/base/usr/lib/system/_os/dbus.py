import dbus  # pyright:ignore [reportMissingTypeStubs]
import dbus.service  # pyright:ignore [reportMissingTypeStubs]
import grp
import pwd
import sys

from dbus.mainloop.glib import DBusGMainLoop  # pyright:ignore [reportMissingTypeStubs,reportUnknownVariableType]
from gi.repository import GLib  # pyright:ignore [reportMissingTypeStubs,reportUnknownVariableType,reportAttributeAccessIssue]

from typing import Callable
from typing import cast


def checkupdates(force: bool = False) -> list[str]:
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    interface = dbus.Interface(
        bus.get_object(  # pyright:ignore [reportUnknownMemberType]
            "os.system",
            "/system",
        ),
        "system.checkupdates",
    )
    if not force:
        updates = cast(Callable[[], list[str]], interface.updates)()
        if updates:
            return updates

    loop = GLib.MainLoop()  # pyright:ignore [reportUnknownMemberType,reportUnknownVariableType]

    def on_stderr(stderr: str):
        print(stderr, file=sys.stderr, end="")

    def on_status(status: str):
        setattr(on_status, "status", status)
        if status in ["error", "none", "available"]:
            loop.quit()  # pyright:ignore [reportUnknownMemberType]

    connect_to_signal = cast(
        Callable[[str, Callable[[str], None]], None],
        interface.connect_to_signal,
    )
    connect_to_signal("checkupdates_status", on_status)
    connect_to_signal("checkupdates_stderr", on_stderr)
    cast(Callable[[], None], interface.checkupdates)()

    loop.run()  # pyright:ignore [reportUnknownMemberType]
    if getattr(on_status, "status") == "error":
        raise Exception("Checkupdates failed")

    return cast(Callable[[], list[str]], interface.updates)()


def pull():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    interface = dbus.Interface(
        bus.get_object(  # pyright:ignore [reportUnknownMemberType]
            "os.system",
            "/system",
        ),
        "system.pull",
    )
    loop = GLib.MainLoop()  # pyright:ignore [reportUnknownMemberType,reportUnknownVariableType]

    def on_stdout(stdout: str):
        print(stdout, end="")

    def on_stderr(stderr: str):
        print(stderr, file=sys.stderr, end="")

    def on_status(status: str):
        print(f"Status: {status}")
        setattr(on_status, "status", status)
        if status in ["error", "success"]:
            loop.quit()  # pyright:ignore [reportUnknownMemberType]

    connect_to_signal = cast(
        Callable[[str, Callable[[str], None]], None],
        interface.connect_to_signal,
    )
    connect_to_signal("pull_stdout", on_stdout)
    connect_to_signal("pull_stderr", on_stderr)
    connect_to_signal("pull_status", on_status)
    cast(Callable[[], None], interface.pull)()

    loop.run()  # pyright:ignore [reportUnknownMemberType]
    if getattr(on_status, "status") == "error":
        raise Exception("Base image pull failed")


def upgrade():
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    interface = dbus.Interface(
        bus.get_object(  # pyright:ignore [reportUnknownMemberType]
            "os.system",
            "/system",
        ),
        "system.upgrade",
    )
    loop = GLib.MainLoop()  # pyright:ignore [reportUnknownMemberType,reportUnknownVariableType]

    def on_stdout(stdout: str):
        print(stdout, end="")

    def on_stderr(stderr: str):
        print(stderr, file=sys.stderr, end="")

    def on_status(status: str):
        print(f"Status: {status}")
        setattr(on_status, "status", status)
        if status in ["error", "success"]:
            loop.quit()  # pyright:ignore [reportUnknownMemberType]

    connect_to_signal = cast(
        Callable[[str, Callable[[str], None]], None],
        interface.connect_to_signal,
    )
    connect_to_signal("upgrade_stdout", on_stdout)
    connect_to_signal("upgrade_stderr", on_stderr)
    connect_to_signal("upgrade_status", on_status)
    cast(Callable[[], None], interface.upgrade)()

    loop.run()  # pyright:ignore [reportUnknownMemberType]
    if getattr(on_status, "status") == "error":
        raise Exception("Upgrade failed")


def upgrade_status() -> str:
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    interface = dbus.Interface(
        bus.get_object(  # pyright:ignore [reportUnknownMemberType]
            "os.system",
            "/system",
        ),
        "system.upgrade",
    )
    return cast(Callable[[], str], interface.status)()


def groups_for_sender(obj: dbus.service.Object, sender: str) -> set[str]:
    userid = cast(
        Callable[[str], int],
        obj.connection.get_unix_user,  # pyright:ignore [reportAttributeAccessIssue,reportUnknownMemberType]
    )(sender)
    user = pwd.getpwuid(userid).pw_name
    return set([x.gr_name for x in grp.getgrall() if user in x.gr_mem])
