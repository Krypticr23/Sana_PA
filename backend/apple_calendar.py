"""
apple_calendar.py — SANA's native Apple Calendar engine (macOS / EventKit).

This is the low-level wrapper around macOS EventKit (via PyObjC). It reads and
writes the *local* calendar store that the Calendar app keeps in sync with
iCloud — so there is NO app-specific password, NO stored secret, and NO direct
iCloud round-trip from SANA. Everything stays on the Mac, which fits SANA's
privacy-first design.

Constraints (by design, since this runs on the "Mac brain"):
  * Only works on macOS.
  * Only works while the Mac is on.
  * Requires a one-time Calendar permission grant (System Settings ->
    Privacy & Security -> Calendars). See SETUP.md.

All datetimes are LOCAL time. Naive datetimes are interpreted in the Mac's
local timezone (which is what you want for calendar events). You may also pass
ISO-8601 strings (e.g. "2026-06-12T14:30") and they'll be parsed as local time.

Public API (see AppleCalendar):
    cal = AppleCalendar()              # creates store, requests access
    cal.list_calendars()
    cal.get_events(start, end)
    cal.get_upcoming(days=7)
    cal.create_event(title, start, end, ...)
    cal.update_event(event_id, ...)
    cal.delete_event(event_id)
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime, timedelta
from typing import Iterable, Optional, Union

# ---------------------------------------------------------------------------
# EventKit import guard — give a clear, actionable error off-Mac or uninstalled.
# ---------------------------------------------------------------------------
try:
    from EventKit import (  # type: ignore
        EKEventStore,
        EKEvent,
        EKEntityTypeEvent,
        EKSpanThisEvent,
    )
    from Foundation import NSDate  # type: ignore
    _EVENTKIT_AVAILABLE = True
    _IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - depends on platform
    _EVENTKIT_AVAILABLE = False
    _IMPORT_ERROR = exc


DateLike = Union[datetime, str]


class CalendarError(RuntimeError):
    """Raised for any EventKit / permission / write-guard problem."""


class CalendarAccessDenied(CalendarError):
    """Raised when the user has not granted Calendar permission."""


def _require_eventkit() -> None:
    if not _EVENTKIT_AVAILABLE:
        raise CalendarError(
            "EventKit is not available. This module only runs on macOS with "
            "PyObjC installed. Install it with:\n"
            "    pip install pyobjc-framework-EventKit\n"
            f"Original import error: {_IMPORT_ERROR!r}"
        )


def _to_datetime(value: DateLike) -> datetime:
    """Normalize a datetime or ISO-8601 string into a (local, naive) datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        # Allow a trailing 'Z' (UTC) by stripping it; we treat input as local.
        if s.endswith("Z"):
            s = s[:-1]
        try:
            return datetime.fromisoformat(s)
        except ValueError as exc:
            raise CalendarError(
                f"Could not parse datetime string {value!r}. "
                "Use ISO-8601 like '2026-06-12T14:30'."
            ) from exc
    raise CalendarError(f"Expected datetime or ISO string, got {type(value)!r}.")


def _to_nsdate(value: DateLike):
    """Python datetime/str -> NSDate (interprets naive datetimes as local time)."""
    dt = _to_datetime(value)
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _from_nsdate(nsdate) -> Optional[datetime]:
    """NSDate -> local naive datetime (or None)."""
    if nsdate is None:
        return None
    return datetime.fromtimestamp(nsdate.timeIntervalSince1970())


class AppleCalendar:
    """Native Apple Calendar access for SANA.

    Parameters
    ----------
    allow_writes:
        Master safety switch. When False, create/update/delete raise
        CalendarError. Defaults to True (the user opted into read + write),
        but the agent layer can construct with allow_writes=False for a
        read-only mode during testing.
    request_timeout:
        Seconds to wait for the macOS permission dialog / callback.
    auto_request:
        If True (default), request access in __init__. Set False to defer.
    """

    def __init__(
        self,
        allow_writes: bool = True,
        request_timeout: float = 60.0,
        auto_request: bool = True,
    ) -> None:
        _require_eventkit()
        self.allow_writes = allow_writes
        self.request_timeout = request_timeout
        self._store = EKEventStore.alloc().init()
        self._access_granted = False
        if auto_request:
            self.request_access()

    # ------------------------------------------------------------------ access
    def request_access(self) -> bool:
        """Request Calendar access. Blocks until the user responds or timeout.

        Returns True if granted. Uses the macOS 14+ full-access selector when
        available and falls back to the legacy selector on older systems.
        """
        result = {"granted": False, "error": None}
        done = threading.Event()

        def _handler(granted, error):  # called on a background queue by EventKit
            result["granted"] = bool(granted)
            result["error"] = error
            done.set()

        store = self._store
        if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
            # macOS 14 (Sonoma) and later — read + write.
            store.requestFullAccessToEventsWithCompletion_(_handler)
        elif hasattr(store, "requestAccessToEntityType_completion_"):
            # Legacy (macOS 13 and earlier).
            store.requestAccessToEntityType_completion_(EKEntityTypeEvent, _handler)
        else:  # pragma: no cover
            raise CalendarError("No known EventKit access-request selector found.")

        if not done.wait(timeout=self.request_timeout):
            raise CalendarError(
                "Timed out waiting for Calendar permission. If no dialog "
                "appeared, grant access manually in System Settings -> "
                "Privacy & Security -> Calendars."
            )

        self._access_granted = result["granted"]
        if not self._access_granted:
            err = result["error"]
            raise CalendarAccessDenied(
                "Calendar access was denied. Enable it under System Settings "
                "-> Privacy & Security -> Calendars for the app running SANA "
                f"(Terminal / Python). {('Detail: ' + str(err)) if err else ''}"
            )
        return True

    def _ensure_access(self) -> None:
        if not self._access_granted:
            self.request_access()

    # --------------------------------------------------------------- calendars
    def list_calendars(self) -> list[dict]:
        """Return all event calendars as dicts."""
        self._ensure_access()
        out = []
        for cal in self._store.calendarsForEntityType_(EKEntityTypeEvent):
            out.append(
                {
                    "id": str(cal.calendarIdentifier()),
                    "title": str(cal.title()),
                    "source": str(cal.source().title()) if cal.source() else None,
                    "allows_modifications": bool(cal.allowsContentModifications()),
                    "is_default": False,  # filled in below
                }
            )
        default = self._store.defaultCalendarForNewEvents()
        if default is not None:
            default_id = str(default.calendarIdentifier())
            for c in out:
                c["is_default"] = c["id"] == default_id
        return out

    def _calendar_by_id(self, calendar_id: Optional[str]):
        """Resolve a calendar id to an EKCalendar, or the default if None."""
        if calendar_id is None:
            cal = self._store.defaultCalendarForNewEvents()
            if cal is None:
                raise CalendarError(
                    "No default calendar for new events. Pass calendar_id "
                    "explicitly (see list_calendars())."
                )
            return cal
        cal = self._store.calendarWithIdentifier_(calendar_id)
        if cal is None:
            raise CalendarError(f"No calendar with id {calendar_id!r}.")
        return cal

    # ------------------------------------------------------------------- reads
    def get_events(
        self,
        start: DateLike,
        end: DateLike,
        calendar_ids: Optional[Iterable[str]] = None,
    ) -> list[dict]:
        """Return events between start and end (inclusive of overlap).

        calendar_ids: restrict to specific calendars; None = all calendars.
        """
        self._ensure_access()
        ns_start = _to_nsdate(start)
        ns_end = _to_nsdate(end)

        cals = None
        if calendar_ids is not None:
            cals = [self._calendar_by_id(cid) for cid in calendar_ids]

        predicate = self._store.predicateForEventsWithStartDate_endDate_calendars_(
            ns_start, ns_end, cals
        )
        events = self._store.eventsMatchingPredicate_(predicate) or []
        result = [self._event_to_dict(ev) for ev in events]
        result.sort(key=lambda e: (e["start"] or "", e["title"] or ""))
        return result

    def get_upcoming(self, days: int = 7, calendar_ids: Optional[Iterable[str]] = None) -> list[dict]:
        """Convenience: events from now through `days` ahead."""
        now = datetime.now()
        return self.get_events(now, now + timedelta(days=days), calendar_ids)

    def get_event(self, event_id: str) -> Optional[dict]:
        """Fetch a single event by its identifier (or None)."""
        self._ensure_access()
        ev = self._store.eventWithIdentifier_(event_id)
        return self._event_to_dict(ev) if ev is not None else None

    # ------------------------------------------------------------------ writes
    def _guard_writes(self) -> None:
        if not self.allow_writes:
            raise CalendarError(
                "Writes are disabled (allow_writes=False). Construct "
                "AppleCalendar(allow_writes=True) to create/update/delete events."
            )

    def create_event(
        self,
        title: str,
        start: DateLike,
        end: Optional[DateLike] = None,
        calendar_id: Optional[str] = None,
        all_day: bool = False,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        url: Optional[str] = None,
        duration_minutes: Optional[int] = None,
    ) -> dict:
        """Create a new event and return it as a dict.

        If `end` is omitted, `duration_minutes` (default 60) is used.
        """
        self._guard_writes()
        self._ensure_access()

        if end is None:
            mins = duration_minutes if duration_minutes is not None else 60
            end = _to_datetime(start) + timedelta(minutes=mins)

        cal = self._calendar_by_id(calendar_id)
        if not cal.allowsContentModifications():
            raise CalendarError(
                f"Calendar {cal.title()!r} is read-only; choose a writable one."
            )

        ev = EKEvent.eventWithEventStore_(self._store)
        ev.setTitle_(title)
        ev.setCalendar_(cal)
        ev.setAllDay_(bool(all_day))
        ev.setStartDate_(_to_nsdate(start))
        ev.setEndDate_(_to_nsdate(end))
        if location:
            ev.setLocation_(location)
        if notes:
            ev.setNotes_(notes)
        if url:
            from Foundation import NSURL  # local import: only needed here
            ev.setURL_(NSURL.URLWithString_(url))

        ok, err = self._store.saveEvent_span_error_(ev, EKSpanThisEvent, None)
        if not ok:
            raise CalendarError(f"Failed to save event: {err}")
        return self._event_to_dict(ev)

    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start: Optional[DateLike] = None,
        end: Optional[DateLike] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        all_day: Optional[bool] = None,
    ) -> dict:
        """Update fields on an existing event. Only provided fields change."""
        self._guard_writes()
        self._ensure_access()

        ev = self._store.eventWithIdentifier_(event_id)
        if ev is None:
            raise CalendarError(f"No event with id {event_id!r}.")

        if title is not None:
            ev.setTitle_(title)
        if all_day is not None:
            ev.setAllDay_(bool(all_day))
        if start is not None:
            ev.setStartDate_(_to_nsdate(start))
        if end is not None:
            ev.setEndDate_(_to_nsdate(end))
        if location is not None:
            ev.setLocation_(location)
        if notes is not None:
            ev.setNotes_(notes)

        ok, err = self._store.saveEvent_span_error_(ev, EKSpanThisEvent, None)
        if not ok:
            raise CalendarError(f"Failed to update event: {err}")
        return self._event_to_dict(ev)

    def delete_event(self, event_id: str) -> bool:
        """Delete an event by identifier. Returns True on success."""
        self._guard_writes()
        self._ensure_access()

        ev = self._store.eventWithIdentifier_(event_id)
        if ev is None:
            raise CalendarError(f"No event with id {event_id!r}.")
        ok, err = self._store.removeEvent_span_error_(ev, EKSpanThisEvent, None)
        if not ok:
            raise CalendarError(f"Failed to delete event: {err}")
        return True

    # --------------------------------------------------------------- internals
    @staticmethod
    def _event_to_dict(ev) -> dict:
        start = _from_nsdate(ev.startDate())
        end = _from_nsdate(ev.endDate())
        cal = ev.calendar()
        return {
            "id": str(ev.eventIdentifier()) if ev.eventIdentifier() else None,
            "title": str(ev.title()) if ev.title() else "",
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "all_day": bool(ev.isAllDay()),
            "location": str(ev.location()) if ev.location() else None,
            "notes": str(ev.notes()) if ev.notes() else None,
            "calendar": str(cal.title()) if cal else None,
            "calendar_id": str(cal.calendarIdentifier()) if cal else None,
        }


# ---------------------------------------------------------------------------
# Tiny manual check when run directly:  python apple_calendar.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    try:
        cal = AppleCalendar()
        print("Calendars:")
        for c in cal.list_calendars():
            flag = " (default)" if c["is_default"] else ""
            rw = "rw" if c["allows_modifications"] else "ro"
            print(f"  [{rw}] {c['title']}{flag}  id={c['id']}")
        print("\nNext 7 days:")
        for e in cal.get_upcoming(7):
            print(f"  {e['start']}  {e['title']}  ({e['calendar']})")
    except CalendarError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
