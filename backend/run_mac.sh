#!/usr/bin/env bash
#
# SANA backend launcher for the MAC (with Apple Calendar enabled).
# Run from the backend folder:   ./run_mac.sh
#
# Uses a self-contained virtual environment (.venv) so it never touches your
# Homebrew/system Python (avoids the PEP 668 "externally-managed" error).
#
# Override the model/port if you like:
#   SANA_MODEL=qwen2.5:7b ./run_mac.sh
#   SANA_PORT=8080        ./run_mac.sh
#
set -euo pipefail
cd "$(dirname "$0")"

MODEL="${SANA_MODEL:-qwen2.5:14b}"
PORT="${SANA_PORT:-8000}"
VENV=".venv"

echo "==> SANA Mac launcher"
echo "    model: $MODEL    port: $PORT"

# 0. API key — load from .env, or generate one (needed for the public tunnel).
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1091
  set -a; source "$ENV_FILE"; set +a
fi
if [ -z "${SANA_API_KEY:-}" ]; then
  echo "==> No SANA_API_KEY found — generating one and saving to $ENV_FILE"
  GEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  echo "SANA_API_KEY=$GEN" >> "$ENV_FILE"
  export SANA_API_KEY="$GEN"
fi
echo "==> API key (paste this into the app's src/config.js as SANA_API_KEY):"
echo "    $SANA_API_KEY"

# 1. Is Ollama up?
if ! curl -s -o /dev/null "http://localhost:11434/api/tags"; then
  echo "!! Ollama isn't responding on :11434."
  echo "   Start it first:  ollama serve   (or just open the Ollama app), then retry."
  exit 1
fi

# 2. Is the model available? (tool-calling needs a capable model like Qwen)
if ! curl -s "http://localhost:11434/api/tags" | grep -q "\"${MODEL%%:*}"; then
  echo "!! Model '$MODEL' not found in Ollama."
  echo "   Pull it (large download):   ollama pull $MODEL"
  echo "   ...or use one you have:      SANA_MODEL=qwen2.5:7b ./run_mac.sh"
  exit 1
fi

# 3. Is the port free? A stale SANA backend on the same port causes Errno 48
#    ("address already in use") and would keep serving OLD code to your app.
if lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
  HOLDER_PIDS=$(lsof -ti "tcp:$PORT")
  HOLDER_CMD=$(ps -o command= -p $HOLDER_PIDS 2>/dev/null || true)
  if echo "$HOLDER_CMD" | grep -qiE "uvicorn|main:app|python"; then
    echo "==> Port $PORT is held by an old SANA backend (pid: $HOLDER_PIDS) — stopping it."
    kill $HOLDER_PIDS 2>/dev/null || true
    sleep 1
    if lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
      kill -9 $(lsof -ti "tcp:$PORT") 2>/dev/null || true
      sleep 1
    fi
  else
    echo "!! Port $PORT is in use by something that isn't SANA:"
    lsof -i "tcp:$PORT"
    echo "   Stop it, or run on another port:  SANA_PORT=8080 ./run_mac.sh"
    exit 1
  fi
fi

# 4. Virtual environment — keeps Homebrew's Python clean and fixes PEP 668.
if [ ! -d "$VENV" ]; then
  echo "==> Creating Python virtual environment in $VENV (one-time) ..."
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# 5. Dependencies INSIDE the venv (installs pyobjc-framework-EventKit on macOS).
echo "==> Installing/refreshing dependencies in the venv ..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

# 6. Apple Calendar permission — first run pops the macOS prompt; click OK.
#    Non-fatal: if not granted yet, the server still starts so chat works; the
#    calendar just won't read until you grant it in System Settings.
echo "==> Checking Apple Calendar access (approve the prompt if it appears)..."
if ! python test_calendar.py access; then
  echo "!! WARNING: Calendar access not granted yet."
  echo "   Enable it under System Settings -> Privacy & Security -> Calendars,"
  echo "   then restart this script. Starting the server anyway..."
fi

# 7. Start the server. 0.0.0.0 so the phone can reach it at the Mac's Tailscale IP.
echo "==> Starting SANA backend on 0.0.0.0:$PORT  (Ctrl-C to stop)"
export SANA_MODEL="$MODEL"
exec python -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
