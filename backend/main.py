import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from routers import chat, calendar, tasks, health

app = FastAPI(
    title="SANA - Personal AI Agent",
    description="Your private PA",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API-key auth.
#
# When SANA_API_KEY is set (REQUIRED if you expose the backend over a public
# tunnel), every request must carry the key in either:
#     X-SANA-Key: <key>
#   or
#     Authorization: Bearer <key>
#
# /health stays open so the tunnel/host can be health-checked. CORS preflight
# (OPTIONS) is allowed through so the browser/app can negotiate.
#
# If SANA_API_KEY is NOT set, auth is disabled — fine for local use or a private
# Tailscale network, but DO NOT expose the backend publicly without it.
# ---------------------------------------------------------------------------
SANA_API_KEY = os.environ.get("SANA_API_KEY")
_OPEN_PREFIXES = ("/health",)

if SANA_API_KEY:
    print("[SANA] API-key auth: ENABLED")
else:
    print("[SANA] API-key auth: DISABLED (set SANA_API_KEY before exposing publicly)")


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    if SANA_API_KEY and request.method != "OPTIONS":
        path = request.url.path
        if not any(path.startswith(p) for p in _OPEN_PREFIXES):
            provided = request.headers.get("x-sana-key", "")
            if not provided:
                auth = request.headers.get("authorization", "")
                if auth.lower().startswith("bearer "):
                    provided = auth[7:]
            if provided != SANA_API_KEY:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )
    return await call_next(request)


app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
