#!/usr/bin/env python3
# Needed packages:
# python-pytz python-gi python-pydbus python-dateutil

import configparser
import datetime
import logging
import sys
from collections import namedtuple, OrderedDict

import pydbus
from dateutil import parser, rrule, tz
from gi.repository import GLib

WakeupEntry = namedtuple('WakeupEntry', 'date wakeup_type')

class WakeupManager(object):
    """
    <node>
      <interface name='org.yavdr.wakeup'>
        <method name='addWakeup'>
          <arg type='s' name='id' direction='in'/>
          <arg type='x' name='timestamp' direction='in'/>
          <arg type='b' name='result' direction='out'/>
          <arg type='s' name='message' direction='out'/>
        </method>
        <method name='addWakeupS'>
          <arg type='s' name='id' direction='in'/>
          <arg type='s' name='timestr' direction='in'/>
          <arg type='b' name='result' direction='out'/>
          <arg type='s' name='message' direction='out'/>
        </method>
        <method name='setWakeup'>
          <arg type='s' name='id' direction='in'/>
          <arg type='s' name='timestr' direction='in'/>
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
          <arg type='x' name='message' direction='out'/>
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

    def __init__(self, bus=None, config='/etc/yavdr/wakeup.conf'):
        if bus is not None:
            self.bus = bus 
        else:
            self.bus = pydbus.SystemBus()

        timedate1 = self.bus.get('.timedate1')
        self.tz = tz.gettz(timedate1.Timezone)

        self.wakeupTimer = {}
        self.dformat = '%Y-%m-%d %H:%M:%S %Z'
        self.config = config
        self.init_parser()

    def init_parser(self):
        self.parser = configparser.SafeConfigParser(delimiters=(":", "="), interpolation=None)
        self.parser.optionxform = str
        with open(self.config, 'r', encoding='utf-8') as f:
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
                    dt = list(rrule.rrulestr(rrulestring))[0]
                    wakeup_type = "rrule"
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

    def addWakeup(self, id="system", timestamp=None):
        if timestamp:
            dt = self.dt_fts_utc(timestamp)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=self.tz)
            wakeup_type = "dynamic"
            self.wakeupTimer[id] = WakeupEntry(date=dt, wakeup_type="dynamic")
            return True, "planned wakeup at %s for %s" % (self.dt_hr(self.wakeupTimer[id]), id)
            
    def addWakeupS(self, id="system", timestr=None):
        if timestr:
            try:
                dt = parser.parse(timestr)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=self.tz)
                self.wakeupTimer[id] = WakeupEntry(date=dt, wakeup_type="dynamic")
                return True, "planned wakeup at %s for %s" % (self.dt_hr(dt), id)
            except:
                return False, "wrong formattet timestring"

    def getWakeup(self, id):
        try:
            return True, self.wakeupTimer[id].date.timestamp()
        except (KeyError, AttributeError):
            return False, 0
        except Exception as e:
            print(e, sys.sterr)

    @property
    def NextWakeupTimestamp(self):
        self.init_parser()
        try:
            return self.dt2ts(sorted(self.wakeupTimer.values())[0].date)
        except IndexError:
            return 0
        
    def getWakeupH(self, id=None):
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

    def delWakeup(self, id=None):
        self.init_parser()
        entry = self.wakeupTimer.get(id)
        if entry is not None:
            return False, "could not delete %s" % id
        elif entry.wakeup_type == "dynamic":
            del self.wakeupTimer[id]
            return True, "deleted %s" % id
        else:
            return False, "could not delete %s, is defined in configuration file" % id

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

    def clearWakeup(self):
        self.wakeupTimer = {}
        self.init_parser()

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

class ACPIWakeup:
    def __init__(self, path="/sys/class/rtc/rtc0/wakealarm"):
        self.path = path

    def setWakeup(self, waketime):
        """takes a datetime object and writes it's unix timestamp to RTC"""
        wakestr = str(self.dt2ts(waketime))
        with open("/sys/class/rtc/rtc0/wakealarm", "w") as f:
            f.write("0")
        with open("/sys/class/rtc/rtc0/wakealarm", "w") as f:
            f.write(wakestr)

    def correct_rtc_offset(self, dt):
        """
        Check if RTC is set to localtime using the
        org.freedesktop.timedate1 property LocalRTC.
        In this case, add the utc offset to the
        datetime object.
        """
        timedate1 = self.bus.get('.timedate1')
        if timedate1.LocalRTC:
            tz = tz.gettz(timedate1.Timezone)
            return dt + tz.utcoffset(ts)
        else:
            return dt

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
