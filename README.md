# SANA — Private Personal AI Agent

A fully private, self-hosted AI personal assistant running on a Jetson Orin Nano. Accessible from all your devices (iOS, Android, macOS, Windows) via Tailscale. No cloud, no APIs, no telemetry.

![Status](https://img.shields.io/badge/status-week_1_complete-green)
![Platform](https://img.shields.io/badge/platform-Jetson_Orin_Nano-76B900)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## What Is SANA?

SANA is a personal AI agent that runs entirely on your own hardware. It uses a local large language model (Llama 3.2) for natural conversation, with persistent memory and integrations for calendar, tasks, and more.

**Core principles:**
- **Private by design** — every byte stays on your network
- **Cross-platform** — works on all your devices
- **Self-hosted** — no subscriptions, no vendor lock-in
- **Extensible** — add integrations as needed

---

## Architecture

```
                Jetson Orin Nano (Server)
                ┌──────────────────────────┐
                │  Ollama (Llama 3.2 1b)   │
                │  FastAPI Backend         │
                │  SQLite Memory           │
                │  Auto-start (systemd)    │
                └──────────┬───────────────┘
                           │
                    Tailscale VPN
                           │
        ┌──────────┬───────┴───────┬──────────┐
        │          │               │          │
     iPhone     Android           Mac      Windows
```

---

## Hardware Requirements

| Component | Spec |
|---|---|
| Compute | Jetson Orin Nano (8GB) |
| Storage | 500GB NVMe SSD (for models + data) |
| Boot | microSD with JetPack 6.x |
| Network | Ethernet recommended, WiFi works |

---

## Project Roadmap

- [x] **Week 1** — Backend, local LLM, auto-start, remote access
- [ ] **Week 2** — React Native mobile app (iOS + Android)
- [ ] **Week 3** — Google Calendar + Tasks integration
- [ ] **Week 4** — Desktop clients (macOS + Windows)
- [ ] **Week 5** — Voice interface (Whisper + Piper)
- [ ] **Week 6** — Polish, final testing, physical enclosure

**Target:** Fully functional cross-platform PA by end of June.

---

## Quick Links

- [Setup Guide](docs/SETUP.md) — Full installation from scratch
- [Architecture](docs/ARCHITECTURE.md) — Deep dive into how it works
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Common issues and fixes
- [Backend README](backend/README.md) — Backend-specific docs

---

## Tech Stack

**Backend (Jetson):**
- Ollama (local LLM runtime)
- Llama 3.2 1b (language model)
- FastAPI (web framework)
- SQLite (memory storage)
- Tailscale (private networking)

**Mobile (coming Week 2):**
- React Native + Expo
- Axios (API client)
- AsyncStorage (local cache)

---

## Quick Start (Already Set Up)

If you've already done the initial setup, here's how to start SANA after a reboot:

```bash
# Everything should auto-start, but if needed:
sudo systemctl start ollama
sudo systemctl start sana

# Check status
sudo systemctl status sana

# View logs
sudo journalctl -u sana -f
```

Access SANA at `http://<jetson-ip>:8000/docs`.

---

## Author

Built by **Krishna** as a personal project — privacy-first AI for the people who don't want to trust Big Tech with their lives.

Mechatronics Engineering student exploring the intersection of embedded systems, AI, and full-stack development.

---

## License

MIT — see [LICENSE](LICENSE) for details.
