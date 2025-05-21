import dbus
import dbus.service
import traceback

from ..system import upgrade
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
            self.checkupdates_status("available" if checkupdates() else "none")

        except BaseException:
            traceback.print_exc()
            self.checkupdates_status("error")

    @dbus.service.signal(dbus_interface="system.checkupdates", signature="s")
    def checkupdates_status(self, status: str):
        pass
