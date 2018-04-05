wakeupd
========

**wakeupd** provides a unified interface to set wakeup times with user permissions.
It can be used as a replacement for vdr-addon-acpiwakeup.

TODO
-----
- remove old rrule and static events after reading the configuration file


How it works
-------------
**wakeupd** runs as a DBus-activated service with elevated permissions and provides a DBus API to add, list and remove wakeup dates.
Multiple applications can set their preferred wakeup date (e.g. VDR, KODI).
You can also define recurring wakeup events (e.g. for nightly epg updates) in the configuration file using a RRULE syntax.
The nearest wakeup event will be set using the method configured in the configuration file. yavdr-wakeup defaults to `acpi` to set the wakeup time on `rtc0` and supports alternative wakeup methods (either written as python plugins or by calling an external script with the unix timestamp for the next wakeup event as an argument).

Configuration
--------------
**wakeupd** reads it's configuration from the file `/etc/yavdr/wakeup.conf`.

[Settings]
~~~~~~~~~~
The `[Settings]` section contains the following Options:

 - `StartAhead`  
 Substract the given ammount of minutes from the next wakeup time. This can be used to ensure the system had time to perform all startup actions (e.g. updating the EPG from external sources) before an scheduled action is executed.
 - `DateFormat`  
 Set the date format for displaying wakeup event dates.
 - `Method`  
 Set the wakeup method. Defaults to `acpi`, use `script` to call an external script with the unix timestamp for the wakeup time as an argument. 
 - `Path`  
 The path for the rtc or the script to be called.

``` conf
[Settings]
StartAhead = 5
DateFormat = %Y-%m-%d %H:%M:%S %Z
Method = acpi
Path = /sys/class/rtc/rtc0/wakealarm
```

[Wakeup]
~~~~~~~~~
The `[Wakeup]` section contains predefined wakeup events. You can use either Date strings (http://labix.org/python-dateutil#head-1443e0f14ad5dff07efd465e080d1110920673d8-2
) or RRULE strings (https://dateutil.readthedocs.io/en/stable/rrule.html#rrulestr-examples) to set up events.

``` conf
[Wakeup]
# wake up every night
Nightly EPG Update = RRULE:FREQ=DAILY;BYHOUR=01;BYMINUTE=0;BYSECOND=0
# wake up on a given date (timezone is optional, defaults to local time)
New year's morning= 2019-01-01 08:00 CET
```

wakeupctl
----------

This cli-tool allows easy use of the `wakeupd` DBus API.

Examples:
``` shell
# list existing wakeup times
$ wakeupctl
Wakeup Entries:
Nightly EPG Update            	2018-04-06 01:00:00 CEST      	rrule
VDR                           	2018-05-04 20:15:00 CEST      	dynamic
New year's morning            	2019-01-01 08:00:00 CET       	static

Next wakeup: 5 Minute(s) before 2018-04-06 01:00:00 CEST
```

# remove wakeup event by name
$ wakeupctl remove "VDR"
  "deleted VDR"

# get wakeup event by name
]$ ./wakeupctl getWakeup string:EPGUpdate
method return sender=:1.292 -> dest=:1.294 reply_serial=2
   boolean true
   int64 1366932628

# get human readable time string for wakeup event
$ ./wakeupctl getWakeupH string:EPGUpdate
method return sender=:1.292 -> dest=:1.293 reply_serial=2
   boolean true
   string "2013-04-26 01:30:28"

# get human readable time string for next wakeup event
$ ./wakeupctl getWakeupH string:
method return sender=:1.292 -> dest=:1.297 reply_serial=2
   boolean true
   string "2013-04-25 20:00:00"

# write next wakeup event to RTC
$ ./wakeupctl setWakeup string: string:
method return sender=:1.292 -> dest=:1.296 reply_serial=2
   boolean true
   string "set wakeup time to 2013-04-25 19:55:00"

# create a wakeup event in 6 minutes
$ ./wakeupctl setWakeup string:TestWakeup int64:"$(($(date +%s) + 600))"
method return sender=:1.292 -> dest=:1.305 reply_serial=2
   boolean true
   string "set wakeup time to 2013-04-25 09:34:44"
```
