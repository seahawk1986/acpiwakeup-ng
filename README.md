yavdr-wakeup
============

**yavdr-wakeup** provides a unified interface to set wakeup times with user permissions.
It can be used as a replacement for vdr-addon-acpiwakeup.

How it works
-------------
**yavdr-wakeup** runs as a DBus-activated service with elevated permissions and provides a DBus API to set, view and remove wakeup dates. Multiple applications can set their preferred wakeup date (e.g. VDR, KODI).
You can also define recurring wakeup events (e.g. for nightly epg updates) in the configuration file using RRULE syntax.
The nearest future wakeupevent will be set using the method configured in the configuration file. yavdr-wakeup defaults to acpi to set the wakeup time but supports additional wakeup methods.

wakeupctl
---------------

This tool allows you to use yavdr-wakeup's DBusAPI.

Examples:
```
# list existing wakeup times
$ ./wakeupctl listWakeup
method return sender=:1.285 -> dest=:1.286 reply_serial=2
   array [
      struct {
         string "ISO"
         int64 1367414100
      }
      struct {
         string "EPGUpdate"
         int64 1366932638
      }
      struct {
         string "Tagesschau"
         int64 1366912800
      }
   ]

# remove wakeup event by name
$ ./wakeupctl delWakeup string:ISO
method return sender=:1.292 -> dest=:1.295 reply_serial=2
   boolean true
   string "deleted ISO"

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
