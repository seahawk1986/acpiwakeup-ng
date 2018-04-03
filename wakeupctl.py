#!/usr/bin/env python3
import pydbus

if __name__ == '__main__':
    bus = pydbus.SystemBus()
    wakeup = bus.get('org.yavdr.wakeup')
    if wakeup.NextWakeupTimestamp:
        print("Wakeup Entries:")
        for event in wakeup.WakeupEventsHuman:
            name, date, wakeup_type = event
            print(f"{name:<30}\t{date:<30}\t{wakeup_type}")
        print()
        print(f"Next wakeup: {wakeup.StartAhead} Minute(s) before {wakeup.NextWakeup}")
    else:
        print("No Wakeup Events defined")
