# SANA — Mobile App

The React Native (Expo) client for **SANA**, a fully-local personal AI assistant.
This is the phone front-end; the brain (the LLM + Apple Calendar) lives in the
FastAPI backend at the repo root ([`../backend`](../backend)).

## What it does

- Chat with SANA from your phone.
- Conversation history — load, delete one, or clear all.
- Switch between servers (Tunnel / MacBook / Jetson) from Settings.
- Reaches the backend over an ngrok tunnel (default) or your Tailscale network.
- Calendar actions ("what's on tomorrow?", "add a dentist appointment at 3pm")
  happen through chat — the backend handles Apple Calendar via EventKit.

## Stack

Expo SDK 54 · React Native 0.81 · React 19 · axios · AsyncStorage

## Structure

```
app/
  App.js              # UI: chat, slide-in drawer, settings
  index.js            # entry point
  app.json            # Expo config (bundle id, ATS)
  eas.json            # EAS build profiles
  run_app.sh          # quick Expo launcher
  RUN_ON_PHONE.md     # full tunnel + install guide
  src/
    config.js         # your tunnel URL + API key (GITIGNORED — create locally)
    services/api.js   # backend client; sends the X-SANA-Key header
```

## Setup

1. Install dependencies:

   ```bash
   npm install
   ```

2. Create `src/config.js` (it's gitignored because it holds your key):

   ```js
   export const SANA_URL = "https://your-name.ngrok-free.app";
   export const SANA_API_KEY = "the-key-run_mac.sh-printed";
   ```

3. Make sure the backend is running and (for off-network use) the tunnel is up.
   See [`../backend`](../backend) and [RUN_ON_PHONE.md](./RUN_ON_PHONE.md).

## Run (development)

```bash
./run_app.sh        # or: npx expo start
```

Scan the QR code with **Expo Go**. On a different network than the Mac? Use
`./run_app.sh --tunnel`.

## Build a real installed app

Full steps in [RUN_ON_PHONE.md](./RUN_ON_PHONE.md). Short version (needs an Apple
Developer account):

```bash
npm install -g eas-cli
eas login
eas device:create
eas build --platform ios --profile preview
```

## Servers

| Server  | What it is                                   |
|---------|----------------------------------------------|
| Tunnel  | Default. Reach the Mac from anywhere (ngrok) |
| MacBook | Qwen 14B, same Tailscale network             |
| Jetson  | Always-on, lightweight model                 |

Switch in Settings. The API key from `config.js` is sent on every request as
`X-SANA-Key`; the backend rejects anything without the matching key.

## Security

Never commit `src/config.js` — it holds your API key and tunnel URL (it's
gitignored). If the key ever leaks, regenerate it on the backend (delete
`backend/.env`, re-run `run_mac.sh`) and update `config.js`.
