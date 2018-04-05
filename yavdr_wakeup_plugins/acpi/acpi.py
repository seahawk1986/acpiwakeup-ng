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
        except Exception as e:
            print("Error: Could not set wakeup time", e)

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
