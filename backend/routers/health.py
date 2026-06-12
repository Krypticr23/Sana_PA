from fastapi import APIRouter
import httpx

from agent.core import agent_status

router = APIRouter()


@router.get("/")
async def health_check():
    return {"status": "online", "service": "SANA Backend"}


@router.get("/tools")
async def tools_status():
    """Diagnostic: is the calendar actually wired up on THIS server?

    calendar_tools_enabled=true means chat can read/write the calendar.
    On the Jetson it will be false (EventKit is macOS-only) — that's expected.
    """
    return agent_status()


@router.get("/ollama")
async def ollama_status():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://localhost:11434/api/tags")
            models = r.json().get("models", [])
            return {"status": "online", "models": [m["name"] for m in models]}
    except Exception as e:
        return {"status": "offline", "error": str(e)}
