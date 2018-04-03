#!/usr/bin/env python3
import argparse
import sys
import pydbus
from gi.repository import GLib

def list_events(args):
    if wakeup.NextWakeupTimestamp:
        print("Wakeup Entries:")
        for event in wakeup.WakeupEventsHuman:
            name, date, wakeup_type = event
            print(f"{name:<30}\t{date:<30}\t{wakeup_type}")
        print()
        print(f"Next wakeup: {wakeup.StartAhead} Minute(s) before {wakeup.NextWakeup}")
    else:
        print("No Wakeup Events defined")

def add_event(args):
    if args.wakeuptime.isdigit():
        wakeuptime = GLib.Variant('i', int(args.wakeuptime))
    else:
        wakeuptime = GLib.Variant('s', args.wakeuptime)
    success, msg = wakeup.setWakeup(args.name, wakeuptime)
    if success:
        print(msg)
    else:
        print("Error:", msg, file=sys.stderr)

def remove_event(args):
    success, msg = wakeup.delWakeup(args.name)
    if success:
        print(msg)
    else:
        print("Error:", msg, file=sys.stderr)

parser = argparse.ArgumentParser(prog='wakeupctl', description='control yavdr-wakeup')
parser.set_defaults(func=list_events)
parser.add_argument('-c', '--clear', action='store_true', help='clear all dynamic wakeup events')
subparsers = parser.add_subparsers(help='supported commands')
parser_list = subparsers.add_parser('list', help='list all wakeup events')
parser_list.set_defaults(func=list_events)
parser_add = subparsers.add_parser('add', help='add wakeup event')
parser_add.add_argument('name', help='name of the wakeup event')
parser_add.add_argument('wakeuptime', help='date of the wakeup event')
parser_add.set_defaults(func=add_event)
parser_remove = subparsers.add_parser('remove', help='remove wakeup event')
parser_remove.add_argument('name', help='name of the wakeup event')
parser_remove.set_defaults(func=remove_event)

if __name__ == '__main__':
    args = parser.parse_args()
    bus = pydbus.SystemBus()
    wakeup = bus.get('org.yavdr.wakeup')
    if args.clear: wakeup.clearWakeup()
    args.func(args)
