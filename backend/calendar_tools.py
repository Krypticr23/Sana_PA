"""
calendar_tools.py — SANA agent tool layer for Apple Calendar.

Wraps AppleCalendar (apple_calendar.py) into LLM-callable "tools" for the
Qwen / Ollama function-calling loop. Two pieces:

  1. CALENDAR_TOOLS  — the JSON tool schemas you hand to Ollama via the
     `tools=` parameter (Ollama/OpenAI function-calling format).

  2. CalendarToolkit — a dispatcher. Feed it a tool name + arguments dict
     (exactly what the model emits) and it runs the right AppleCalendar method
     and returns a JSON-serializable result.

WRITE SAFETY
------------
create_event / update_event / delete_event do NOT execute unless the model
passes "confirm": true. Without it, the toolkit returns a
{"status": "confirmation_required", ...} payload describing exactly what would
happen. Surface that to Krishna, get a yes, then re-call the tool with
confirm=true. This is what "never writes to your calendar by surprise" means
in practice — the model has to take a deliberate second step.

Usage sketch (inside the agent loop):

    from calendar_tools import CalendarToolkit, CALENDAR_TOOLS
    toolkit = CalendarToolkit()              # holds one AppleCalendar instance

    resp = ollama.chat(model=..., messages=msgs, tools=CALENDAR_TOOLS)
    for call in resp.message.tool_calls or []:
        result = toolkit.dispatch(call.function.name, call.function.arguments)
        msgs.append({"role": "tool", "content": json.dumps(result)})
"""

from __future__ import annotations

import json
from typing import Any, Optional

from apple_calendar import AppleCalendar, CalendarError


# ---------------------------------------------------------------------------
# Tool schemas (Ollama / OpenAI function-calling format)
# ---------------------------------------------------------------------------
CALENDAR_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_calendars",
            "description": (
                "List the user's Apple calendars (name, id, whether writable, "
                "and which is the default for new events). Call this first if "
                "you need a calendar_id to create an event in a specific calendar."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": (
                "Get calendar events that overlap a time window. Use this to "
                "answer 'what's on my calendar', check availability, or find an "
                "event before updating/deleting it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "string",
                        "description": "Window start, ISO-8601 local time, e.g. '2026-06-12T00:00'.",
                    },
                    "end": {
                        "type": "string",
                        "description": "Window end, ISO-8601 local time, e.g. '2026-06-12T23:59'.",
                    },
                },
                "required": ["start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming",
            "description": "Get events from now through N days ahead (default 7). Quick agenda lookup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How many days ahead. Default 7."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": (
                "Create a new calendar event. WRITE ACTION: must be called with "
                "confirm=true to actually write. Call once without confirm to get "
                "a preview to show the user, then again with confirm=true once they agree."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title."},
                    "start": {"type": "string", "description": "Start, ISO-8601 local, e.g. '2026-06-12T14:30'."},
                    "end": {"type": "string", "description": "End, ISO-8601 local. Omit to use duration_minutes."},
                    "duration_minutes": {"type": "integer", "description": "Used when end is omitted. Default 60."},
                    "calendar_id": {"type": "string", "description": "Target calendar id. Omit for the default calendar."},
                    "all_day": {"type": "boolean", "description": "True for an all-day event."},
                    "location": {"type": "string", "description": "Optional location."},
                    "notes": {"type": "string", "description": "Optional notes/description."},
                    "confirm": {"type": "boolean", "description": "Set true to actually create. Omit/false returns a preview."},
                },
                "required": ["title", "start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_event",
            "description": (
                "Update / reschedule an existing event by id. WRITE ACTION: must "
                "be called with confirm=true. Only the fields you pass change. "
                "Get the event id first via get_events / get_upcoming."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Identifier of the event to change."},
                    "title": {"type": "string"},
                    "start": {"type": "string", "description": "New start, ISO-8601 local."},
                    "end": {"type": "string", "description": "New end, ISO-8601 local."},
                    "location": {"type": "string"},
                    "notes": {"type": "string"},
                    "all_day": {"type": "boolean"},
                    "confirm": {"type": "boolean", "description": "Set true to actually update. Omit/false returns a preview."},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": (
                "Delete an event by id. WRITE ACTION: must be called with "
                "confirm=true. Get the event id first via get_events."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Identifier of the event to delete."},
                    "confirm": {"type": "boolean", "description": "Set true to actually delete. Omit/false returns a preview."},
                },
                "required": ["event_id"],
            },
        },
    },
]

# Names that mutate the calendar and therefore require confirm=true.
_WRITE_TOOLS = {"create_event", "update_event", "delete_event"}


class CalendarToolkit:
    """Dispatches model tool calls to a single AppleCalendar instance."""

    def __init__(self, calendar: Optional[AppleCalendar] = None, allow_writes: bool = True):
        # Lazy: don't trigger the macOS permission prompt until first use.
        self._calendar = calendar
        self._allow_writes = allow_writes

    @property
    def calendar(self) -> AppleCalendar:
        if self._calendar is None:
            self._calendar = AppleCalendar(allow_writes=self._allow_writes)
        return self._calendar

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _coerce_args(arguments: Any) -> dict:
        """Models sometimes emit arguments as a JSON string; normalize to dict."""
        if arguments is None:
            return {}
        if isinstance(arguments, str):
            arguments = arguments.strip()
            if not arguments:
                return {}
            return json.loads(arguments)
        if isinstance(arguments, dict):
            return arguments
        raise CalendarError(f"Unexpected tool arguments type: {type(arguments)!r}")

    # -- main entry ---------------------------------------------------------
    def dispatch(self, name: str, arguments: Any) -> dict:
        """Run a tool call. Always returns a JSON-serializable dict.

        Never raises for normal tool errors — converts them into
        {"status": "error", "message": ...} so the agent loop can keep going
        and tell the user what went wrong.
        """
        try:
            args = self._coerce_args(arguments)
        except (ValueError, CalendarError) as exc:
            return {"status": "error", "message": f"Bad arguments: {exc}"}

        # Write-safety gate: require an explicit confirm flag.
        if name in _WRITE_TOOLS and not bool(args.get("confirm")):
            return self._preview(name, args)

        try:
            handler = getattr(self, f"_do_{name}", None)
            if handler is None:
                return {"status": "error", "message": f"Unknown tool: {name}"}
            return handler(args)
        except CalendarError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:  # defensive: keep the agent loop alive
            return {"status": "error", "message": f"Unexpected error: {exc}"}

    # -- previews (returned when confirm is missing/false) ------------------
    @staticmethod
    def _preview(name: str, args: dict) -> dict:
        proposed = {k: v for k, v in args.items() if k != "confirm"}
        verb = {"create_event": "create", "update_event": "update", "delete_event": "delete"}[name]
        return {
            "status": "confirmation_required",
            "action": verb,
            "proposed": proposed,
            "message": (
                f"This will {verb} a calendar event. Confirm the details with the "
                f"user, then call {name} again with confirm=true."
            ),
        }

    # -- read handlers ------------------------------------------------------
    def _do_list_calendars(self, args: dict) -> dict:
        return {"status": "ok", "calendars": self.calendar.list_calendars()}

    def _do_get_events(self, args: dict) -> dict:
        events = self.calendar.get_events(args["start"], args["end"])
        return {"status": "ok", "count": len(events), "events": events}

    def _do_get_upcoming(self, args: dict) -> dict:
        days = int(args.get("days", 7))
        events = self.calendar.get_upcoming(days)
        return {"status": "ok", "days": days, "count": len(events), "events": events}

    # -- write handlers (only reached when confirm=true) --------------------
    def _do_create_event(self, args: dict) -> dict:
        event = self.calendar.create_event(
            title=args["title"],
            start=args["start"],
            end=args.get("end"),
            duration_minutes=args.get("duration_minutes"),
            calendar_id=args.get("calendar_id"),
            all_day=bool(args.get("all_day", False)),
            location=args.get("location"),
            notes=args.get("notes"),
        )
        return {"status": "created", "event": event}

    def _do_update_event(self, args: dict) -> dict:
        event = self.calendar.update_event(
            event_id=args["event_id"],
            title=args.get("title"),
            start=args.get("start"),
            end=args.get("end"),
            location=args.get("location"),
            notes=args.get("notes"),
            all_day=args.get("all_day"),
        )
        return {"status": "updated", "event": event}

    def _do_delete_event(self, args: dict) -> dict:
        self.calendar.delete_event(args["event_id"])
        return {"status": "deleted", "event_id": args["event_id"]}
