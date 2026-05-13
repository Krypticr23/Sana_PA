# SANA Backend

FastAPI server that runs on the Jetson Orin Nano and handles all AI interactions.

## Quick Start

```bash
cd /mnt/ssd/sana/backend
source venv/bin/activate
python main.py
```

Server runs on `http://0.0.0.0:8000`. Interactive docs at `/docs`.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health/` | Server health check |
| GET | `/health/ollama` | Ollama status + available models |
| POST | `/chat/` | Send a message to SANA |
| GET | `/chat/history/{user_id}` | List all conversations |
| GET | `/chat/history/{user_id}/{conversation_id}` | Get specific conversation |
| GET | `/calendar/` | (Coming Week 3) |
| GET | `/tasks/` | (Coming Week 3) |

## File Structure

```
backend/
├── main.py              # FastAPI entry point
├── requirements.txt     # Python dependencies
├── agent/
│   ├── __init__.py
│   ├── core.py          # LLM interaction (Ollama)
│   └── memory.py        # SQLite conversation memory
└── routers/
    ├── __init__.py
    ├── chat.py
    ├── health.py
    ├── calendar.py
    └── tasks.py
```

## Configuration

The model is set in `agent/core.py`:

```python
MODEL = "llama3.2:1b"
```

To change models, pull a new one with `ollama pull <model>` and update this line.

## Development

Run with auto-reload during development:

```bash
python main.py
```

The `reload=True` flag in `main.py` watches for file changes and restarts automatically.

In production (via systemd), reload is implicit through `Restart=always`.

## Testing

Test the chat endpoint:

```bash
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello SANA", "user_id": "test"}'
```

Expected response:

```json
{
  "response": "Hi! How can I help you today?",
  "conversation_id": "abc-123-def-456"
}
```

## Logs

When running as systemd service:

```bash
sudo journalctl -u sana -f          # live tail
sudo journalctl -u sana -n 100      # last 100 lines
sudo journalctl -u sana --since today
```
