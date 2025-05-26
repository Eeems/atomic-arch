import dbus  # pyright:ignore [reportMissingTypeStubs]
import dbus.service  # pyright:ignore [reportMissingTypeStubs]
import grp
import pwd

from typing import Callable
from typing import cast
from gi.repository import GLib


def checkupdates(force: bool = False) -> list[str]:
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

    interface.checkupdates()  # pyright:ignore [reportUnknownMemberType]
    return cast(Callable[[], list[str]], interface.updates)()


def upgrade():
    bus = dbus.SystemBus()
    interface = dbus.Interface(
        bus.get_object(  # pyright:ignore [reportUnknownMemberType]
            "os.system",
            "/system",
        ),
        "system.upgrade",
    )


def groups_for_sender(obj: dbus.service.Object, sender: str) -> set[str]:
    userid = cast(
        Callable[[str], int],
        obj.connection.get_unix_user,  # pyright:ignore [reportAttributeAccessIssue,reportUnknownMemberType]
    )(sender)
    user = pwd.getpwuid(userid).pw_name
    return set([x.gr_name for x in grp.getgrall() if user in x.gr_mem])
