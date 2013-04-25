#!/usr/bin/env/python3
# Needed packages: python-pytz python-dbus python-dateutil

from gi.repository import GObject
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import datetime
from dateutil import tz
from dateutil import parser
from dateutil import rrule
import logging
import configparser


class Main(dbus.service.Object):
    def __init__(self, config='/etc/acpiwakeup.conf'):
        self.wakeupTimer = {}
        bus_name = dbus.service.BusName('org.acpi.wakeup', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self, bus_name, '/Wakeup')
        self.dformat = '%Y-%m-%d %H:%M:%S'
        self.init_parser(config)
        self.config = config
        
    def init_parser(self, config):
        self.parser = configparser.SafeConfigParser(delimiters=(":", "="), interpolation=None)
        self.parser.optionxform = str
        with open(config, 'r', encoding='utf-8') as f:
            self.parser.readfp(f)
        self.get_wakeup_dates()
        self.get_settings()
        
    def get_settings(self):
        if self.parser.has_section("Settings") and self.parser.has_option('Settings', 'StartAhead'):
            self.startahead = int(self.parser.get('Settings', 'StartAhead'))
        else:
            self.startahead = 0
            
        if self.parser.has_section("Settings") and self.parser.has_option('Settings', 'DateFormat'):
            try:
                dformat = self.parser.get('Settings', 'DateFormat')
                test = datetime.datetime.now().strftime(self.dformat)
                self.dformat = dformat
            except:
                print("wrong DateFormat")
            
    def get_wakeup_dates(self):
        if self.parser.has_section("Wakeup"):
            for wakeuptimer, rrulestring in self.parser.items('Wakeup'):
                if rrulestring.startswith("RRULE"):
                    rrulestring = rrulestring+";COUNT=1"
                    self.wakeupTimer[wakeuptimer] = list(rrule.rrulestr(rrulestring))[0]
                else:
                    self.wakeupTimer[wakeuptimer] = parser.parse(rrulestring)

    def dt_fts_utc(self, timeobj):
        """unix timestamp to datetime-object"""
        return datetime.datetime.fromtimestamp(timeobj)

    def dt_fs_lt(self, timeobj):
        """datetime object from formatted string in local time"""
        return datetime.datetime.strptime(timeobj, self.dformat, dateutil.tz.tzlocal())

    def dt2ts(self, timeobj):
        """datetime object to unix timestamp"""
        return int(timeobj.strftime("%s"))

    def dt_hr(self, timeobj):
        """datetime object to formatted string"""
        return timeobj.strftime(self.dformat)

    @dbus.service.method('org.acpi.wakeup', in_signature='sx')
    def addWakeup(self, id="system", timestamp=None):
        if timestamp:
            self.wakeupTimer[id] = self.dt_fts_utc(timestamp)
            return True, "planned wakeup at %s for %s" % (self.dt_hr(self.wakeupTimer[id]), id)
            
    @dbus.service.method('org.acpi.wakeup', in_signature='ss')
    def addWakeupS(self, id="system", timestr=None):
        if timestr:
            try:
                self.wakeupTimer[id] = parser.parse(timestr)
                return True, "planned wakeup at %s for %s" % (self.dt_hr(self.wakeupTimer[id]), id)
            except:
                return False, "wrong formattet timestring"

    @dbus.service.method('org.acpi.wakeup', in_signature='s', out_signature='bx', id=None)
    def getWakeup(self, id=None):
        if id and id in self.wakeupTimer:
            return True, self.dt2ts(self.wakeupTimer[id])
        elif not id:
            return False, self.dt2ts(sorted(self.wakeupTimer.values())[0])
        else:
            return True, self.dt2ts(sorted(self.wakeupTimer.values())[0])

    @dbus.service.method('org.acpi.wakeup', in_signature='s', out_signature='bs', id=None)
    def getWakeupH(self, id=None):
        if id and id in self.wakeupTimer:
            return True, self.dt_hr(self.wakeupTimer[id])
        elif not id:
            return False, self.dt_hr(sorted(self.wakeupTimer.values())[0])
        else:
            return True, self.dt_hr(sorted(self.wakeupTimer.values())[0])

    @dbus.service.method('org.acpi.wakeup', in_signature='s', out_signature='bs', id=None)
    def delWakeup(self, id=None):
        if id and id in self.wakeupTimer:
            del self.wakeupTimer[id]
            return True, "deleted %s" % id
        else:
            return False

    @dbus.service.method('org.acpi.wakeup', out_signature='a(sx)')
    def listWakeup(self):
        wakelist = []
        for wakeuptime in self.wakeupTimer.keys():
            wakelist.append((wakeuptime, self.dt2ts(self.wakeupTimer[wakeuptime])))
        return wakelist

    @dbus.service.method('org.acpi.wakeup')
    def clearWakeup(self):
        self.wakeupTimer = {}

    @dbus.service.method('org.acpi.wakeup', in_signature="s")
    def loadConfig(self, config=None):
        if not config:
            self.init_parser(self.config)
        else:
            self.init_parser(config)
        return True

    @dbus.service.method('org.acpi.wakeup', in_signature='sx')
    def setWakeup(self, id="system", timestamp=None):
        if timestamp:
            self.addWakeup(id, timestamp)
        if len(self.wakeupTimer) is 0:
            return False, "no wakeuptimer set"
        waketime = sorted(self.wakeupTimer.values())[0] - datetime.timedelta(minutes=self.startahead)
        if waketime > datetime.datetime.utcnow():
            wakestr = str(self.dt2ts(waketime))
            with open("/sys/class/rtc/rtc0/wakealarm", "w") as f:
                f.write("0")
            with open("/sys/class/rtc/rtc0/wakealarm", "w") as f:
                f.write(wakestr)
            return True, "set wakeup time to %s" % self.dt_hr(waketime)
        else:
            return False, "no wakeup time set"

if __name__ == '__main__':
    DBusGMainLoop(set_as_default=True)
    main = Main()
    loop = GObject.MainLoop()
    loop.run()

