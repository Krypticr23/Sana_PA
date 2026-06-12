import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from agent.memory import MemoryManager

# Calendar tools are optional: only meaningfully available on the Mac (EventKit).
# Importing apple_calendar is always safe — it guards the EventKit import — so
# this never breaks the Jetson.
try:
    from calendar_tools import CalendarToolkit, CALENDAR_TOOLS
    from apple_calendar import _EVENTKIT_AVAILABLE
except Exception:  # pragma: no cover - defensive
    CalendarToolkit = None
    CALENDAR_TOOLS = []
    _EVENTKIT_AVAILABLE = False

# Configurable so the Mac can run a tool-capable model (e.g. Qwen) while the
# Jetson stays on llama3.2:1b. Matches the SANA_MODEL convention.
OLLAMA_URL = os.environ.get("SANA_OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.environ.get("SANA_MODEL", "llama3.2:1b")

# Max round-trips where the model calls tools before we force a text answer.
MAX_TOOL_ITERS = 5


def _calendar_tools_enabled() -> bool:
    """Single source of truth for whether calendar tools are active."""
    flag = os.environ.get("SANA_ENABLE_CALENDAR_TOOLS")
    if flag is not None:
        return flag.lower() in ("1", "true", "yes", "on")
    return bool(_EVENTKIT_AVAILABLE and CalendarToolkit)


def agent_status() -> dict:
    """Config snapshot for the /health/tools diagnostic endpoint."""
    return {
        "model": MODEL,
        "ollama_url": OLLAMA_URL,
        "eventkit_available": _EVENTKIT_AVAILABLE,
        "calendar_tools_enabled": _calendar_tools_enabled(),
        "tool_names": [t["function"]["name"] for t in CALENDAR_TOOLS],
    }


SYSTEM_PROMPT = """You are SANA, a personal AI assistant running privately on a local server.
You help the user with:
- Scheduling and calendar management
- Task and appointment planning
- General questions and planning
- Reminders and follow-ups

You are concise, efficient, and proactive. When the user mentions dates, times, or tasks,
you identify them and offer to add them to their calendar or task list.

IMPORTANT: You do NOT have live calendar access unless calendar tools are provided
to you in this request. If you are asked about specific calendar events and you have
no calendar tools available, say plainly that you can't read the calendar on this
server and suggest switching to the Mac server. Never invent events.

Always respond in a helpful, natural tone.
"""

# Appended only when calendar tools are active (i.e. running on the Mac).
TOOLS_ADDENDUM = """

You have live access to the user's Apple Calendar through tools.
The current date and time is {now} ({weekday}).

DATE REFERENCE — use these EXACT dates. Do NOT calculate dates yourself:
{date_ref}
When the user says a relative day like "tomorrow", "Monday", or "next Friday",
copy the matching date from the list above. Always send times as ISO-8601 local,
e.g. 2026-06-12T14:30.

Rules for calendar tools:
- To read the schedule, use get_upcoming or get_events. ALWAYS call a tool before
  answering any question about what's scheduled or when the user is free.
- CRITICAL: Only state events that a tool actually returned. If you have not called
  a calendar tool, or it returned zero events, say the calendar is empty for that
  period. NEVER invent events, dates, times, titles, or locations. If a tool
  returns an error, tell the user what went wrong instead of guessing.
- Creating, updating, or deleting an event is a two-step, confirm-first action.
  First call the tool WITHOUT confirm to get a preview, show the user exactly
  what will change, and only after they agree call the same tool again with
  "confirm": true. Never write to the calendar without explicit user agreement.
"""


class AgentCore:
    def __init__(self):
        self.memory = MemoryManager()
        # Enable tools when EventKit is present, unless explicitly disabled.
        self._tools_enabled = _calendar_tools_enabled()
        self.toolkit = CalendarToolkit() if self._tools_enabled else None
        print(
            f"[SANA] AgentCore ready | model={MODEL} "
            f"| eventkit={_EVENTKIT_AVAILABLE} "
            f"| calendar_tools={'ON' if self._tools_enabled else 'OFF'}"
        )

    def _system_prompt(self) -> str:
        if not self._tools_enabled:
            return SYSTEM_PROMPT
        now = datetime.now()
        today = now.date()
        ref_lines = []
        for i in range(8):
            d = today + timedelta(days=i)
            tag = "   <- today" if i == 0 else ("   <- tomorrow" if i == 1 else "")
            ref_lines.append(f"  {d.isoformat()} ({d.strftime('%A')}){tag}")
        return SYSTEM_PROMPT + TOOLS_ADDENDUM.format(
            now=now.strftime("%Y-%m-%dT%H:%M"),
            weekday=now.strftime("%A"),
            date_ref="\n".join(ref_lines),
        )

    async def chat(self, user_id: str, message: str, conversation_id: Optional[str] = None) -> dict:
        history = self.memory.get_history(user_id, conversation_id)
        messages = [{"role": "system", "content": self._system_prompt()}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        assistant_message = ""
        async with httpx.AsyncClient(timeout=120.0) as client:
            for _ in range(MAX_TOOL_ITERS):
                payload = {"model": MODEL, "messages": messages, "stream": False}
                if self._tools_enabled:
                    payload["tools"] = CALENDAR_TOOLS

                response = await client.post(OLLAMA_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                msg = data.get("message", {})

                tool_calls = msg.get("tool_calls")
                if not tool_calls:
                    if self._tools_enabled:
                        print("[SANA] model answered with NO tool calls this turn")
                    assistant_message = msg.get("content", "")
                    break

                names = [(c.get("function", {}) or {}).get("name") for c in tool_calls]
                print(f"[SANA] model requested {len(tool_calls)} tool call(s): {names}")

                # Record the assistant's tool-call turn, then run each tool.
                messages.append(msg)
                for call in tool_calls:
                    fn = call.get("function", {}) or {}
                    name = fn.get("name", "")
                    args = fn.get("arguments", {})
                    # EventKit is blocking — run it off the event loop.
                    result = await asyncio.to_thread(self.toolkit.dispatch, name, args)
                    print(f"[SANA]   tool {name} args={args} -> {result.get('status')}")
                    messages.append({"role": "tool", "content": json.dumps(result)})
            else:
                # Loop exhausted without a final text answer.
                assistant_message = (
                    "I started working on that but ran out of tool steps. "
                    "Could you rephrase or break it into smaller parts?"
                )

        conv_id = self.memory.save_message(
            user_id=user_id,
            conversation_id=conversation_id,
            user_message=message,
            assistant_message=assistant_message,
        )
        return {"response": assistant_message, "conversation_id": conv_id}
