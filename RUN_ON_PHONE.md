# Run SANA on your phone (no Tailscale) + build a real installed app

This sets up two things:

1. A **public tunnel** (ngrok) so the app reaches your Mac from anywhere, no
   Tailscale. Protected by an **API key** so it isn't open to the world.
2. A **real installed app** on your iPhone (a home-screen icon) via an EAS build.

Architecture: phone app  ->  ngrok https URL  ->  your Mac (Qwen 14B + calendar).
The Mac is still the brain. The key is what keeps the tunnel private.

---

## Part 1 — Backend + tunnel

### 1a. Start the backend (it now manages an API key)

```bash
cd ~/Downloads/sana-repo/backend && ./run_mac.sh
```

On first run it prints something like:

```
==> API key (paste this into the app's src/config.js as SANA_API_KEY):
    Xa1b2c3...   <-- copy this
[SANA] API-key auth: ENABLED
```

Copy that key. It's saved in `backend/.env` (gitignored) and reused next time.

### 1b. One-time ngrok setup

1. Sign up free at https://ngrok.com
2. `brew install ngrok`
3. `ngrok config add-authtoken <token-from-dashboard>`
4. Claim your free static domain at https://dashboard.ngrok.com/domains
   (something like `your-name.ngrok-free.app`).

### 1c. Start the tunnel (second terminal)

```bash
cd ~/Downloads/sana-repo/backend
SANA_NGROK_DOMAIN=your-name.ngrok-free.app ./run_tunnel.sh
```

Leave it running. Your backend is now reachable at `https://your-name.ngrok-free.app`.

---

## Part 2 — Point the app at the tunnel

Edit `sana-app/src/config.js`:

```js
export const SANA_URL = "https://your-name.ngrok-free.app";
export const SANA_API_KEY = "the-key-run_mac.sh-printed";
```

The app sends that key on every request as `X-SANA-Key`. Without it the backend
returns 401, so a stranger who finds the URL can't use your AI or calendar.

### Test it quickly in Expo Go first

```bash
cd ~/Documents/sana-app && ./run_app.sh
```

Scan the QR, make sure chat + calendar work over the tunnel (the "Tunnel" server
is the default now). Confirm before building the standalone app.

---

## Part 3 — Build the real installed app (EAS)

Requires an **Apple Developer account** ($99/yr) to install on a physical iPhone.

```bash
npm install -g eas-cli
cd ~/Documents/sana-app
eas login                       # create a free Expo account if needed
eas device:create               # register your iPhone (follow the link/QR once)
eas build --platform ios --profile preview
```

When the build finishes, EAS gives you a QR/link — open it on the iPhone to
install SANA as a real app. The tunnel URL + key are baked in from
`src/config.js`, so it just works on launch.

Notes:
- `bundleIdentifier` is set to `com.krishnar.sana` in app.json — change it if you
  want a different ID (must be unique on your Apple account).
- `NSAllowsArbitraryLoads` is enabled so the app can talk to the tunnel; fine for
  a personal app.
- To update the app later, change code and run `eas build` again.

---

## Security reality check

A public tunnel means your Mac is reachable from the internet. What protects you:

- **API key** on every non-health request (401 otherwise).
- `/health` stays open (only returns "online") so ngrok can health-check.
- ngrok gives you HTTPS automatically.

If you want it locked down further later: ngrok paid plans add OAuth/IP
allowlists, or switch to a Cloudflare Tunnel behind Cloudflare Access. For now,
keep `src/config.js` and `backend/.env` private (both are gitignored) and don't
share the URL + key.
