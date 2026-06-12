# Apple Calendar (EventKit) integration

SANA reads and writes your **Apple Calendar** natively via Apple's **EventKit**
framework. No app-specific password, no stored secret, no direct iCloud
round-trip — it reads/writes the local calendar store the Mac keeps in sync with
iCloud. Supports **read + write**.

## The one constraint that drives everything

**EventKit is macOS-only.** So the calendar works *only when the backend runs on
the Mac server* — not on the Jetson. The code is written to handle this
automatically:

- `requirements.txt` marks `pyobjc-framework-EventKit` as `sys_platform ==
  "darwin"`, so `pip install -r requirements.txt` still works on the Jetson (it
  just skips the package).
- The `/calendar/*` endpoints return **HTTP 503** with a clear message on the
  Jetson instead of crashing. Chat, tasks, and health keep working there.
- The chat agent **auto-enables calendar tools only when EventKit is present**
  (i.e. on the Mac). On the Jetson the agent behaves exactly as before.

If you ever want the always-on Jetson to reach the calendar too, the move is a
CalDAV engine behind the same `apple_calendar.AppleCalendar` API — the router and
agent wouldn't change.

## Files

```
backend/apple_calendar.py     # EventKit engine (read + write)
backend/calendar_tools.py     # LLM tool schemas + dispatcher (used by the agent)
backend/routers/calendar.py   # REST endpoints (mounted at /calendar)
backend/test_calendar.py      # CLI smoke test — run on the Mac
backend/agent/core.py         # chat loop, now with calendar tool-calling
```

## Setup on the Mac

```bash
cd backend
pip install -r requirements.txt          # installs pyobjc-framework-EventKit on macOS

python test_calendar.py access           # approve the Calendar permission prompt
python test_calendar.py roundtrip        # creates + reads + deletes a temp event
```

The first run triggers a macOS prompt: *"<app> would like to access your
Calendar"* — click OK. If you miss it, enable it under **System Settings →
Privacy & Security → Calendars** for whatever launches Python (Terminal, or the
launchd label if SANA runs as a service). The permission is tied to that
launching app; if SANA runs under launchd, seed the grant once from a normal
Terminal as the same user first.

## Running the Mac server with a tool-capable model

`llama3.2:1b` (the Jetson default) is weak at tool-calling. On the Mac, point
SANA at a model that does tools well (Qwen):

```bash
cd backend
SANA_MODEL=qwen2.5:14b uvicorn main:app --host 0.0.0.0 --port 8000
```

Environment variables the agent reads:

| Variable | Default | Purpose |
|---|---|---|
| `SANA_MODEL` | `llama3.2:1b` | Ollama model name |
| `SANA_OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama chat endpoint |
| `SANA_ENABLE_CALENDAR_TOOLS` | auto (on when EventKit present) | force-enable/disable calendar tools (`true`/`false`) |

## REST endpoints (for the phone app, over Tailscale)

```
GET    /calendar/                 -> upcoming events (default 7 days)
GET    /calendar/upcoming?days=7
GET    /calendar/events?start=2026-06-12T00:00&end=2026-06-12T23:59
GET    /calendar/calendars
GET    /calendar/events/{id}
POST   /calendar/events           {title, start, end|duration_minutes, ...}
PATCH  /calendar/events/{id}      {start, end, title, ...}
DELETE /calendar/events/{id}
```

## How writes stay safe in chat

`create_event` / `update_event` / `delete_event` do nothing unless called with
`"confirm": true`. In conversation, SANA first calls the tool without confirm,
gets a preview, shows you the exact change, and only writes after you say yes.
The REST write endpoints are direct (no confirm gate) — they're meant for your
own trusted app on your private Tailscale network.

## Datetimes

Everything is ISO-8601 **local** time, e.g. `2026-06-12T14:30`. Naive datetimes
are interpreted in the Mac's timezone. A trailing `Z` is tolerated but still
treated as local.
