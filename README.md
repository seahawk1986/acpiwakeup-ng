acpiwakeup-ng
============

a replacement for vdr-addon-acpiwakeup, run it as a service (as root), call it via dbus from everywhere without need for root permissions

acpiwakeupctl
---------------

add requests for the next wakeup Time as a user.

Examples:
```
$ ./acpiwakeupctl listWakeup
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

$ ./acpiwakeupctl delWakeup string:ISO
method return sender=:1.292 -> dest=:1.295 reply_serial=2
   boolean true
   string "deleted ISO"

]$ ./acpiwakeupctl getWakeup string:EPGUpdate
method return sender=:1.292 -> dest=:1.294 reply_serial=2
   boolean true
   int64 1366932628

$ ./acpiwakeupctl getWakeupH string:EPGUpdate
method return sender=:1.292 -> dest=:1.293 reply_serial=2
   boolean true
   string "2013-04-26 01:30:28"

$ ./acpiwakeupctl getWakeupH
method return sender=:1.292 -> dest=:1.297 reply_serial=2
   boolean false
   string "2013-04-25 20:00:00"

$ ./acpiwakeupctl setWakeup
method return sender=:1.292 -> dest=:1.296 reply_serial=2
   boolean true
   string "set wakeup time to 2013-04-25 19:55:00"

$ ./acpiwakeupctl setWakeup string:TestWakeup int64:"$(($(date +%s) + 600))"
method return sender=:1.292 -> dest=:1.305 reply_serial=2
   boolean true
   string "set wakeup time to 2013-04-25 09:34:44"
```
