#!/usr/bin/env python3
# Needed packages:
# python-pytz python-gi python-pydbus python-dateutil

import configparser
import datetime
import logging
import sys
from collections import namedtuple, OrderedDict
from functools import wraps

import pydbus
from dateutil import parser, rrule, tz
from gi.repository import GLib

WakeupEntry = namedtuple('WakeupEntry', 'date wakeup_type')


class ACPIWakeup:
    def __init__(self, path="/sys/class/rtc/rtc0/wakealarm"):
        self.path = path

    def setWakeupTime(self, wakeuptime):
        """takes a datetime object and writes it's unix timestamp to RTC"""
        with open(self.path, "w") as f:
            f.write("0")
        with open(self.path, "w") as f:
            timestamp_str = str(int(self.correct_rtc_offset(wakeuptime.date.timestamp())))
            print(timestamp_str)
            f.write(timestamp_str)

    def correct_rtc_offset(self, dt):
        """
        Check if RTC is set to localtime using the org.freedesktop.timedate1
        property LocalRTC. In this case, add the utc offset to the datetime
        object.
        """
        timedate1 = bus.get('.timedate1')
        if timedate1.LocalRTC:
            tz = tz.gettz(timedate1.Timezone)
            return dt + tz.utcoffset(ts)
        else:
            return dt


class WakeupManager(object):
    """
    <node>
      <interface name='org.yavdr.wakeup'>
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

    wakeup_methods = {
        'acpi': ACPIWakeup,
        }

    def __init__(self, bus=None, config='/etc/yavdr/wakeup.conf'):
        if bus is not None:
            self.bus = bus 
        else:
            self.bus = pydbus.SystemBus()

        # get timezone from system
        timedate1 = self.bus.get('.timedate1')
        self.tz = tz.gettz(timedate1.Timezone)

        self.wakeupTimer = {}
        self.dformat = '%Y-%m-%d %H:%M:%S %Z'
        self.config = config
        self.init_parser()

    def init_parser(self):
        cfg_parser = configparser.SafeConfigParser(delimiters=(":", "="), interpolation=None)
        cfg_parser.optionxform = str
        with open(self.config, 'r', encoding='utf-8') as f:
            cfg_parser.readfp(f)
        self.get_wakeup_dates(cfg_parser)
        self.get_settings(cfg_parser)
        
    def get_settings(self, cfg_parser):
        if cfg_parser.has_section("Settings"):
            self.startahead = cfg_parser.getint('Settings', 'StartAhead', fallback=0)

            wakeup_method = cfg_parser.get("Settings", "WakeupMethod",
                                                 fallback="acpi")

            self.wakeup = self.wakeup_methods.get(wakeup_method)()
            
            if cfg_parser.has_option('Settings', 'DateFormat'):
                try:
                    dformat = cfg_parser.get('Settings', 'DateFormat')
                    test = datetime.datetime.now().strftime(self.dformat)
                    self.dformat = dformat
                except Exception as e:
                    print("invalid DaTeformat In configuration file", e, file=sys.stderr)
            
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
        return timeobj.strftime(self.dformat)

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
            
        self.wakeup.setWakeupTime(wakeuptime)
        return True, "set wakeup time to %s" % self.dt_hr(wakeuptime.date)

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
    wakeup_manager = WakeupManager(bus=bus)
    bus.publish("org.yavdr.wakeup", wakeup_manager)
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        wakeup_manager.setWakeup()
        loop.quit()
