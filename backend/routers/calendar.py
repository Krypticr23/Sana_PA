"""
Calendar router — Apple Calendar (native EventKit) for SANA.

Mounted by main.py at prefix "/calendar", so routes here are declared WITHOUT
that prefix.

This only does real work when the backend runs ON THE MAC (EventKit is
macOS-only). On the Jetson (Linux) the engine is unavailable, so every endpoint
returns HTTP 503 with a clear message instead of crashing — that keeps the rest
of the backend (chat, tasks, health) working normally on the Jetson.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from apple_calendar import (
    AppleCalendar,
    CalendarAccessDenied,
    CalendarError,
    _EVENTKIT_AVAILABLE,
)

router = APIRouter()

# Lazily-created singleton so the macOS permission prompt only fires on first use.
_calendar: Optional[AppleCalendar] = None


def get_calendar() -> AppleCalendar:
    if not _EVENTKIT_AVAILABLE:
        # Running on the Jetson (or any non-Mac) — calendar lives on the Mac.
        raise HTTPException(
            status_code=503,
            detail=(
                "Apple Calendar is only available on the Mac server (EventKit "
                "is macOS-only). Switch SANA to the Mac server to use the calendar."
            ),
        )
    global _calendar
    if _calendar is None:
        try:
            _calendar = AppleCalendar(allow_writes=True)
        except CalendarAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        except CalendarError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
    return _calendar


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------
class CreateEventBody(BaseModel):
    title: str
    start: str
    end: Optional[str] = None
    duration_minutes: Optional[int] = None
    calendar_id: Optional[str] = None
    all_day: bool = False
    location: Optional[str] = None
    notes: Optional[str] = None


class UpdateEventBody(BaseModel):
    title: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    all_day: Optional[bool] = None


def _guard(fn):
    """Run an engine call, mapping CalendarError -> clean HTTP responses."""
    try:
        return fn()
    except HTTPException:
        raise
    except CalendarAccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except CalendarError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------
# Routes (declared as plain `def` so FastAPI runs the blocking EventKit calls
# in a threadpool instead of blocking the async event loop)
# --------------------------------------------------------------------------
@router.get("/")
def get_events_default(days: int = Query(7, ge=1, le=365)):
    """Default: upcoming events for the next `days` (replaces the old stub)."""
    cal = get_calendar()
    events = _guard(lambda: cal.get_upcoming(days))
    return {"days": days, "count": len(events), "events": events}


@router.get("/calendars")
def list_calendars():
    cal = get_calendar()
    return {"calendars": _guard(cal.list_calendars)}


@router.get("/events")
def get_events(
    start: str = Query(..., description="ISO-8601 local, e.g. 2026-06-12T00:00"),
    end: str = Query(..., description="ISO-8601 local, e.g. 2026-06-12T23:59"),
):
    cal = get_calendar()
    events = _guard(lambda: cal.get_events(start, end))
    return {"count": len(events), "events": events}


@router.get("/upcoming")
def get_upcoming(days: int = Query(7, ge=1, le=365)):
    cal = get_calendar()
    events = _guard(lambda: cal.get_upcoming(days))
    return {"days": days, "count": len(events), "events": events}


@router.get("/events/{event_id}")
def get_event(event_id: str):
    cal = get_calendar()
    event = _guard(lambda: cal.get_event(event_id))
    if event is None:
        raise HTTPException(status_code=404, detail=f"No event with id {event_id}")
    return event


@router.post("/events", status_code=201)
def create_event(body: CreateEventBody):
    cal = get_calendar()
    event = _guard(
        lambda: cal.create_event(
            title=body.title,
            start=body.start,
            end=body.end,
            duration_minutes=body.duration_minutes,
            calendar_id=body.calendar_id,
            all_day=body.all_day,
            location=body.location,
            notes=body.notes,
        )
    )
    return {"status": "created", "event": event}


@router.patch("/events/{event_id}")
def update_event(event_id: str, body: UpdateEventBody):
    cal = get_calendar()
    event = _guard(
        lambda: cal.update_event(
            event_id=event_id,
            title=body.title,
            start=body.start,
            end=body.end,
            location=body.location,
            notes=body.notes,
            all_day=body.all_day,
        )
    )
    return {"status": "updated", "event": event}


@router.delete("/events/{event_id}")
def delete_event(event_id: str):
    cal = get_calendar()
    _guard(lambda: cal.delete_event(event_id))
    return {"status": "deleted", "event_id": event_id}
