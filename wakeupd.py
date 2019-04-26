#!/usr/bin/env python3

import configparser
import datetime
import logging
import pkg_resources
import sys
from collections import namedtuple, OrderedDict
from functools import wraps
from threading import Lock

import importlib
import pkgutil

import pydbus
from dateutil import parser, rrule, tz
from gi.repository import GLib

import yavdr_wakeup_plugins

WakeupEntry = namedtuple('WakeupEntry', 'date wakeup_type')

IFACE = 'org.yavdr.wakeup'
S_IFACE = IFACE + '.Setup'

def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

class Settings(object):
    dbus = f"""
    <node>
      <interface name='{S_IFACE}'>
        <property name="AvailableWakeupMethods" type="as" access="read">
        </property>
        <property name="WakeupMethod" type="s" access="readwrite">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
        <property name="StartAhead" type="i" access="readwrite">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
        <property name="Path" type="s" access="readwrite">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
        <property name="DateFormat" type="s" access="readwrite">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
      </interface>
    </node>
    """
    wakeup_methods = {}
    wakeup_method = 'acpi'
    wakeup_methods_lock = Lock()
    startahead = 5
    path = "/sys/class/rtc/rtc0/wakealarm"
    PropertiesChanged = pydbus.generic.signal()
    config = "/etc/yavdr/wakeup.conf"
    dformat = '%Y-%m-%d %H:%M:%S %Z'

    def __init__(self, cfg=None):
        if cfg:
            self.config = cfg
        self.update_available_wakeup_methods()
        
    def init_parser(self):
        cfg_parser = configparser.SafeConfigParser(delimiters=(":", "="), interpolation=None)
        cfg_parser.optionxform = str
        try:
            with open(self.config, 'r', encoding='utf-8') as f:
                cfg_parser.readfp(f)
        except:
            with open('wakeup.conf', 'r', encoding='utf-8') as f:
                cfg_parser.readfp(f)
        self.get_wakeup_dates(cfg_parser)
        self.get_settings(cfg_parser)

    def update_available_wakeup_methods(self):
        with self.wakeup_methods_lock:
            old_wakeup_methods = set(self.wakeup_methods)
            for finder, name, ispkg in iter_namespace(yavdr_wakeup_plugins):
                method = name.rsplit('.', maxsplit=1)[-1]
                old_wakeup_methods.discard(method)
                self.wakeup_methods[method] = getattr(importlib.import_module(name), method).Wakeup
            for m in old_wakeup_methods:
                self.wakeup_methods.pop(m, None)
        

class WakeupManager(object):
    dbus = f"""
    <node>
      <interface name='{IFACE}'>
        <method name='setWakeup'>
          <arg type='s' name='id' direction='in'/>
          <arg type='v' name='timestr' direction='in'/>
          <arg type='b' name='result' direction='out'/>
          <arg type='s' name='message' direction='out'/>
        </method>
        <method name='getWakeup'>
          <arg type='s' name='id' direction='in'/>
          <arg type='b' name='success' direction='out'/>
          <arg type='x' name='timestamp' direction='out'/>
        </method>
        <method name='getWakeupH'>
          <arg type='s' name='id' direction='in'/>
          <arg type='s' name='timestamp' direction='out'/>
        </method>
        <method name='delWakeup'>
          <arg type='s' name='id' direction='in'/>
          <arg type='b' name='success' direction='out'/>
          <arg type='s' name='message' direction='out'/>
        </method>
        <method name='clearWakeup'>
        </method>
        <property name="NextWakeupTimestamp" type="x" access="read">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
        <property name="NextWakeup" type="s" access="read">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
        <property name="WakeupEventsHuman" type="a(sss)" access="read">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
        <property name="WakeupEvents" type="a(sxs)" access="read">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
        <property name="StartAhead" type="i" access="read">
          <annotation name="org.freedesktop.DBus.Property.EmitsChangedSignal" value="true"/>
        </property>
      </interface>
    </node>
    """

    wakeup_methods = {}
    wakeupTimer = {}
    dformat = '%Y-%m-%d %H:%M:%S %Z'

    def __init__(self, settings):
        for finder, name, ispkg in iter_namespace(yavdr_wakeup_plugins):
            method = name.rsplit('.', maxsplit=1)[-1]
            self.wakeup_methods[method] = getattr(importlib.import_module(name), method).Wakeup
        self.config = settings
        self.wakeup_methods = settings.wakeup_methods
        self.bus = pydbus.SystemBus()

        # get timezone from system
        timedate1 = self.bus.get('.timedate1')
        self.tz = tz.gettz(timedate1.Timezone)

        self.init_parser()

    def init_parser(self):
        cfg_parser = configparser.SafeConfigParser(delimiters=(":", "="), interpolation=None)
        cfg_parser.optionxform = str
        try:
            with open(self.config, 'r', encoding='utf-8') as f:
                cfg_parser.readfp(f)
        except:
            with open('wakeup.conf', 'r', encoding='utf-8') as f:
                cfg_parser.readfp(f)
        self.get_wakeup_dates(cfg_parser)
        self.get_settings(cfg_parser)

    def get_settings(self, cfg_parser):
        if cfg_parser.has_section("Settings"):
            self.startahead = cfg_parser.getint('Settings', 'StartAhead',
                    fallback=0)

            wakeup_method = cfg_parser.get("Settings", "WakeupMethod",
                    fallback="acpi")
            path = cfg_parser.get("Settings", "Path",
                    fallback='/sys/class/rtc/rtc0/wakealarm')
            self.wakeup = self.wakeup_methods.get(wakeup_method)(path)

            if cfg_parser.has_option('Settings', 'DateFormat'):
                try:
                    dformat = cfg_parser.get('Settings', 'DateFormat')
                    test = datetime.datetime.now().strftime(dformat)
                    self.dformat = dformat
                except Exception as e:
                    print("invalid DateFormat in configuration file", e,
                            file=sys.stderr)

    def get_wakeup_dates(self, cfg_parser):
        if cfg_parser.has_section("Wakeup"):
            for wakeuptimer, rrulestring in cfg_parser.items('Wakeup'):
                if rrulestring.startswith("RRULE"):
                    rrulestring = rrulestring+";COUNT=1"
                    dt = list(rrule.rrulestr(rrulestring))[0]
                    wakeup_type = "rrule"
                elif rrulestring.startswith("@"):
                    dt = datetime.datetime.fromtimestamp(rrulestring.lstrip("@"))
                    wakeup_type = "dynamic"
                else:
                    dt = parser.parse(rrulestring)
                    wakeup_type = "static"

                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=self.tz)
                self.wakeupTimer[wakeuptimer] = WakeupEntry(date=dt, wakeup_type=wakeup_type)


    def dt_fts_utc(self, timeobj):
        """unix timestamp to datetime-object"""
        return datetime.datetime.fromtimestamp(timeobj)

    def dt_fs_lt(self, timeobj):
        """datetime object from formatted string in local time"""
        return datetime.datetime.strptime(timeobj, self.dformat, dateutil.tz.tzlocal())

    def dt2ts(self, timeobj):
        """datetime object to unix timestamp"""
        return timeobj.timestamp()

    def dt_hr(self, timeobj):
        """datetime object to formatted string"""
        return timeobj.astimezone(datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo).strftime(self.dformat)

    def setWakeup(self, id="system", timestamp=None):
        if timestamp:
            try:
                if isinstance(timestamp, int):
                    dt = self.dt_fts_utc(timestamp)
                elif isinstance(timestamp, str):
                    dt = parser.parse(timestamp)
            except Exception as e:
                return False, str(e)
            else:
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=self.tz)
                wakeup_type = "dynamic"
                self.wakeupTimer[id] = WakeupEntry(date=dt, wakeup_type="dynamic")
        if not self.wakeupTimer:
            return False, "no wakeuptimer set"
        try:
            wakeuptime = next(
                dt for dt in sorted(self.wakeupTimer.values())
                if (dt.date - datetime.timedelta(minutes=self.startahead)
                    ) > datetime.datetime.now(datetime.timezone.utc)
            )
        except StopIteration:
            return False, "no wakeup time set"

        real_wakeuptime = self.wakeup.setWakeupTime(wakeuptime.date)
        if real_wakeuptime:
            return True, f"set wakeup time to {self.dt_hr(real_wakeuptime)} ({int(real_wakeuptime.timestamp())})"
        else:
            return False, "Error: could not set wakeup time"

    def getWakeup(self, id):
        try:
            return True, self.wakeupTimer[id].date.timestamp()
        except (KeyError, AttributeError):
            return False, 0
        except Exception as e:
            print(e, file=sys.sterr)

    @property
    def NextWakeupTimestamp(self):
        self.init_parser()
        try:
            return self.dt2ts(sorted(self.wakeupTimer.values())[0].date)
        except IndexError:
            return 0

    def getWakeupH(self, id):
        self.init_parser()
        if id and id in self.wakeupTimer:
            return self.dt_hr(self.wakeupTimer[id].date)
        else:
            return 0

    @property
    def NextWakeup(self):
        self.init_parser()
        try:
            return self.dt_hr(sorted(self.wakeupTimer.values())[0].date)
        except IndexError:
            return ""

    def delWakeup(self, id):
        self.init_parser()
        entry = self.wakeupTimer.get(id)
        if entry is None:
            return False, "could not delete %s" % id
        elif entry.wakeup_type == "dynamic":
            self.wakeupTimer.pop(id, None)
            return True, "deleted %s" % id
        else:
            return False, "could not delete %s, is defined in configuration file" % id

    def clearWakeup(self):
        self.wakeupTimer = {}
        self.init_parser()

    @property
    def WakeupEvents(self):
        self.init_parser()
        return [(id, self.dt2ts(event.date), event_wakeup_type) for id, event in sorted(
            self.wakeupTimer.items(), key=lambda x: x[1].date)]

    @property
    def WakeupEventsHuman(self):
        self.init_parser()
        return [(id, self.dt_hr(event.date), event.wakeup_type) for id, event in sorted(
            self.wakeupTimer.items(), key=lambda x: x[1].date)]

    @property
    def StartAhead(self):
        self.init_parser()
        return self.startahead

if __name__ == '__main__':
    bus = pydbus.SystemBus()
    settings = Settings()
    wakeup_manager = WakeupManager(settings=settings)
    bus.publish(IFACE, wakeup_manager,
                ('/org/yavdr/wakeup/Setup', settings))
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        wakeup_manager.setWakeup()
        loop.quit()
