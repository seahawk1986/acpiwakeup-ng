import datetime
import sys

from dateutil import tz
from dateutil.relativedelta import relativedelta
import pydbus

class Wakeup:
    """set the wakeup time using the kernel's rtc interface"""
    path = "/sys/class/rtc/rtc0/wakealarm"

    def __init__(self, path=None):
        if path:
            self.path = path
        self.bus = pydbus.SystemBus()

    def setWakeupTime(self, wakeuptime):
        """takes a datetime object and writes it's unix timestamp to RTC"""
        print(f"Setting wakeup time to {wakeuptime} ({int(wakeuptime.timestamp())})", file=sys.stderr)
        try:
            timestamp = int(self.correct_rtc_offset(wakeuptime).timestamp())
            with open(self.path, "r") as rtc:
                ts = rtc.read().rstrip()
                if ts and not ts.isdigit():
                    raise ValueError("target file does not contain a timestamp!")
            with open(self.path, "w") as rtc:
                rtc.write("0\n")
                rtc.flush()
                rtc.write(f"{timestamp}\n")
        except OSError:
            print(f"RTC did not accept timestamp {timestamp}", file=sys.stderr)
            # Newer kernel versions (>= 4.14) check if the RTC supports waking on a given timestamp.
            # Good RTCs allow up to one year in the future, some only a month and some only a day.
            # So we need to retry with a lower value (or give up if this doesn't help)
            now = datetime.datetime.now(tz.tzutc())
            if wakeuptime > now + relativedelta(years=+1):
                print("Wakeup is more than a year in the future")
                wakeuptime = now + relativedelta(years=+1, seconds=-1)
            elif wakeuptime > now + relativedelta(months=+1):
                print("Wakeup is more than a month in the future")
                wakeuptime = now + relativedelta(months=+1, seconds=-1)
            elif now + relativedelta(days=+1) < wakeuptime:
                print("Wakeup is more than a day in the future")
                wakeuptime = now + relativedelta(days=+1, seconds=-1)
            else:
                return None
            wakeuptime = self.setWakeupTime(wakeuptime)
        except Exception as e:
            print(f"Error: Could not set wakeup time: {e}", file=sys.stderr)
            wakeuptime = None
        return wakeuptime

    def correct_rtc_offset(self, dt):
        """
        Check if RTC is set to localtime using the org.freedesktop.timedate1
        property LocalRTC. In this case, add the utc offset to the datetime
        object.
        """
        timedate1 = self.bus.get('.timedate1')
        if timedate1.LocalRTC:
            tz = tz.gettz(timedate1.Timezone)
            return dt + tz.utcoffset(ts)
        else:
            return dt
