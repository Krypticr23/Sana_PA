#!/usr/bin/env python3
"""
test_calendar.py — run this ON THE MAC to verify the Apple Calendar integration.

Examples:
    python test_calendar.py access            # request/confirm permission
    python test_calendar.py calendars         # list your calendars
    python test_calendar.py upcoming --days 7 # next 7 days of events
    python test_calendar.py events --start 2026-06-12T00:00 --end 2026-06-12T23:59
    python test_calendar.py roundtrip         # create a temp event, show it, delete it

The 'roundtrip' command is the real end-to-end test: it writes a clearly-labeled
test event ~1 hour from now, reads it back, then deletes it. Safe to run.
"""

import argparse
import sys
from datetime import datetime, timedelta

from apple_calendar import AppleCalendar, CalendarError


def cmd_access(_args):
    AppleCalendar()  # __init__ requests access; raises if denied
    print("Calendar access granted.")


def cmd_calendars(_args):
    cal = AppleCalendar()
    for c in cal.list_calendars():
        flag = " (default)" if c["is_default"] else ""
        rw = "rw" if c["allows_modifications"] else "ro"
        print(f"[{rw}] {c['title']}{flag}")
        print(f"      id={c['id']}  source={c['source']}")


def cmd_upcoming(args):
    cal = AppleCalendar()
    events = cal.get_upcoming(args.days)
    if not events:
        print(f"No events in the next {args.days} days.")
        return
    for e in events:
        allday = " [all-day]" if e["all_day"] else ""
        print(f"{e['start']} -> {e['end']}{allday}  {e['title']}  ({e['calendar']})")


def cmd_events(args):
    cal = AppleCalendar()
    events = cal.get_events(args.start, args.end)
    if not events:
        print("No events in that window.")
        return
    for e in events:
        print(f"{e['start']} -> {e['end']}  {e['title']}  ({e['calendar']})")
        print(f"      id={e['id']}")


def cmd_roundtrip(_args):
    cal = AppleCalendar(allow_writes=True)
    start = datetime.now() + timedelta(hours=1)
    print("Creating a temporary test event...")
    ev = cal.create_event(
        title="SANA test event (safe to delete)",
        start=start,
        duration_minutes=30,
        notes="Created by test_calendar.py roundtrip. Will be deleted automatically.",
    )
    print(f"  created: {ev['title']} @ {ev['start']}  (calendar: {ev['calendar']})")
    print(f"  id: {ev['id']}")

    fetched = cal.get_event(ev["id"])
    print(f"  read back OK: {fetched is not None and fetched['title'] == ev['title']}")

    print("Deleting the test event...")
    cal.delete_event(ev["id"])
    gone = cal.get_event(ev["id"]) is None
    print(f"  deleted OK: {gone}")
    print("\nRoundtrip complete — read + write are working.")


def main():
    parser = argparse.ArgumentParser(description="SANA Apple Calendar test CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("access", help="Request / confirm Calendar permission")
    sub.add_parser("calendars", help="List calendars")

    p_up = sub.add_parser("upcoming", help="Events in the next N days")
    p_up.add_argument("--days", type=int, default=7)

    p_ev = sub.add_parser("events", help="Events in a window")
    p_ev.add_argument("--start", required=True, help="ISO-8601 local, e.g. 2026-06-12T00:00")
    p_ev.add_argument("--end", required=True, help="ISO-8601 local, e.g. 2026-06-12T23:59")

    sub.add_parser("roundtrip", help="Create + read + delete a temp event (full test)")

    args = parser.parse_args()
    handlers = {
        "access": cmd_access,
        "calendars": cmd_calendars,
        "upcoming": cmd_upcoming,
        "events": cmd_events,
        "roundtrip": cmd_roundtrip,
    }
    try:
        handlers[args.command](args)
    except CalendarError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
