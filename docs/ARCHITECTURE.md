# SANA Architecture

How the pieces fit together.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    JETSON ORIN NANO (Server)                    │
│                                                                  │
│  ┌──────────────┐    ┌────────────────┐    ┌─────────────────┐ │
│  │   Ollama     │    │    FastAPI     │    │    SQLite       │ │
│  │              │◄──►│    Backend     │◄──►│    Memory       │ │
│  │ Llama 3.2 1b │    │   (port 8000)  │    │ /mnt/ssd/sana/  │ │
│  └──────────────┘    └────────┬───────┘    └─────────────────┘ │
│       :11434                  │                                  │
└───────────────────────────────┼──────────────────────────────────┘
                                │
                       Tailscale VPN
                                │
        ┌────────────┬──────────┴──────────┬────────────┐
        │            │                     │            │
   ┌─────────┐  ┌─────────┐          ┌─────────┐  ┌─────────┐
   │ iPhone  │  │ Android │          │   Mac   │  │ Windows │
   └─────────┘  └─────────┘          └─────────┘  └─────────┘
```

---

## Component Breakdown

### Ollama
Local LLM runtime that runs language models on the Jetson's GPU. Exposes an HTTP API on port 11434.

- **Model:** Llama 3.2 1b (chosen for Jetson's 8GB shared memory constraint)
- **Storage:** `/mnt/ssd/ollama/models`
- **Service:** Runs as systemd service, auto-starts on boot

### FastAPI Backend
The main "brain" of SANA. Handles all incoming requests from devices and orchestrates the conversation.

- **Port:** 8000
- **Workers:** Single Uvicorn worker (sufficient for personal use)
- **Storage:** `/mnt/ssd/sana/backend`
- **Service:** Runs as systemd service, depends on Ollama

### SQLite Memory
Lightweight database for persistent conversation history and (eventually) user facts.

- **Location:** `/mnt/ssd/sana/data/sana.db`
- **Tables:**
  - `conversations` — chat session metadata
  - `messages` — every message ever sent
  - `user_facts` — reserved for stored preferences

### Tailscale
Private mesh VPN connecting all your devices to the Jetson without exposing anything to the public internet.

- Uses WireGuard underneath
- Each device gets a `100.x.x.x` IP
- Direct peer-to-peer encrypted connections

---

## Request Flow

What happens when you send a message:

```
1. iPhone sends POST /chat/ to Jetson via Tailscale
        ↓
2. FastAPI receives request at routers/chat.py
        ↓
3. AgentCore.chat() is called
        ↓
4. MemoryManager loads past conversation history
        ↓
5. System prompt + history + new message sent to Ollama
        ↓
6. Llama 3.2 generates response (~1-3 seconds)
        ↓
7. Response saved to SQLite
        ↓
8. JSON returned to iPhone
        ↓
9. App displays response
```

---

## Why This Architecture?

### Why Local LLM Instead of Cloud API?

| Aspect | Local (Ollama) | Cloud (OpenAI/Anthropic) |
|---|---|---|
| Privacy | Full | None |
| Cost | Free | Per-token |
| Latency | Local network | Internet roundtrip |
| Model size | Limited by hardware | Massive |
| Reliability | Depends on your power | Depends on provider |

For a personal PA, the privacy and cost trade-offs make local the right choice. Quality is "good enough" for scheduling, reminders, and casual chat. For complex reasoning, we could swap models later.

### Why FastAPI?

- Pythonic and async-ready
- Auto-generates OpenAPI docs (useful for testing)
- Easy to extend with new routes
- Good async support for streaming responses (future)

### Why SQLite Over Postgres?

- Single file, zero configuration
- More than enough for single-user data
- Easy to back up (just copy the file)
- No separate database process to manage

### Why Tailscale Over Port Forwarding?

- Zero network configuration
- No public internet exposure
- Encrypted by default
- Works on mobile data and any WiFi

---

## Storage Layout

```
/mnt/ssd/                          ← NVMe SSD mount
├── ollama/
│   └── models/                    ← LLM model files
│       └── blobs/                 ← (~1.3GB for Llama 3.2 1b)
└── sana/
    ├── backend/
    │   ├── main.py                ← FastAPI entry point
    │   ├── requirements.txt
    │   ├── venv/                  ← Python virtual env (not in git)
    │   ├── agent/
    │   │   ├── core.py            ← LLM interaction logic
    │   │   └── memory.py          ← SQLite memory manager
    │   └── routers/
    │       ├── chat.py            ← /chat endpoints
    │       ├── health.py          ← /health endpoints
    │       ├── calendar.py        ← (Week 3)
    │       └── tasks.py           ← (Week 3)
    └── data/
        └── sana.db                ← SQLite database (not in git)
```

---

## Memory Management

Each conversation works like this:

1. **First message** — new conversation_id is generated (UUID)
2. **Subsequent messages** — same conversation_id reuses the thread
3. **History** — last 20 messages are sent to the LLM each time
4. **Storage** — every message saved to SQLite forever

The 20-message limit prevents the context window from getting too large and slowing down responses. For longer-term memory of facts ("user prefers morning meetings"), we'll use the `user_facts` table later.

---

## Auto-Start Chain

When the Jetson boots:

```
1. systemd starts at boot
        ↓
2. mounts /mnt/ssd from fstab
        ↓
3. ollama.service starts (loads from /mnt/ssd/ollama/models)
        ↓
4. sana.service waits for ollama.service (Requires=)
        ↓
5. sana.service starts main.py
        ↓
6. SANA is ready to receive requests
```

Total cold-boot to ready time: ~30-45 seconds.

---

## Extending SANA

Adding new capabilities follows this pattern:

1. Create a new module in `agent/` for the logic
2. Create a new router in `routers/` for the endpoints
3. Register the router in `main.py`
4. Restart the service: `sudo systemctl restart sana`

Example — adding a weather integration:

```python
# agent/weather.py
class WeatherService:
    async def get_current(self, location: str):
        # call open-meteo API
        ...

# routers/weather.py
from agent.weather import WeatherService

@router.get("/{location}")
async def get_weather(location: str):
    return await WeatherService().get_current(location)

# main.py
from routers import weather
app.include_router(weather.router, prefix="/weather", tags=["weather"])
```

---

## Future Architecture (Post-June)

```
                      Jetson Orin Nano
                            │
            ┌───────────────┼───────────────┐
            │               │               │
        Whisper          FastAPI         Piper TTS
        (voice in)      (orchestrator)   (voice out)
            │               │               │
            └───────────────┼───────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
          Ollama       Integrations    Sensors
          (LLM)        (Cal/Tasks)    (Camera/PIR)
```

Adding voice and physical sensors converts SANA from a chatbot into a true embodied AI assistant.
