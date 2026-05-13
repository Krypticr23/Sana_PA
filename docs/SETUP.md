# SANA Setup Guide

Complete installation instructions for setting up SANA on a Jetson Orin Nano from scratch.

---

## Prerequisites

- Jetson Orin Nano (8GB)
- JetPack 6.x flashed on microSD (R36.4.4 tested)
- NVMe SSD (500GB recommended)
- Internet connection
- Display, keyboard, mouse for initial setup (can go headless after)

---

## Step 1 — JetPack Initial Setup

Flash JetPack 6.x to your SD card using NVIDIA SDK Manager or balenaEtcher with the JetPack image. Boot the Jetson and complete the Ubuntu setup wizard.

After first boot, update the system:

```bash
sudo apt update
sudo apt upgrade -y
```

---

## Step 2 — Mount the NVMe SSD

Find your SSD:

```bash
lsblk
```

You should see an `nvme0n1` device. Get its UUID:

```bash
sudo blkid /dev/nvme0n1p1
```

Copy the UUID, then format if it's a fresh SSD:

```bash
# ONLY if the SSD is brand new and unformatted
sudo mkfs.ext4 /dev/nvme0n1p1
```

Create mount point and add to fstab for auto-mounting on boot:

```bash
sudo mkdir -p /mnt/ssd
echo "UUID=<your-uuid-here> /mnt/ssd ext4 defaults 0 2" | sudo tee -a /etc/fstab
sudo mount -a
```

Verify:

```bash
df -h | grep ssd
```

Create project directories:

```bash
sudo mkdir -p /mnt/ssd/ollama/models
sudo mkdir -p /mnt/ssd/sana
sudo chown -R $USER:$USER /mnt/ssd
```

---

## Step 3 — Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Point Ollama to use the SSD for model storage by editing the systemd service:

```bash
sudo systemctl edit ollama
```

Add these lines:

```ini
[Service]
Environment="OLLAMA_MODELS=/mnt/ssd/ollama/models"
```

Fix permissions so Ollama can write to the SSD:

```bash
sudo chown -R ollama:ollama /mnt/ssd/ollama
```

Restart Ollama:

```bash
sudo systemctl restart ollama
```

Pull the Llama 3.2 1b model (small enough for Jetson Orin Nano's 8GB shared memory):

```bash
ollama pull llama3.2:1b
```

Verify:

```bash
ollama list
```

You should see `llama3.2:1b` in the list.

---

## Step 4 — Install Python and Set Up Backend

```bash
sudo apt install python3-pip python3-venv -y
```

Create the backend folder:

```bash
mkdir -p /mnt/ssd/sana/backend
cd /mnt/ssd/sana/backend
```

Create a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## Step 5 — Clone This Repo

```bash
cd /mnt/ssd/sana
git clone <your-repo-url> backend
cd backend
```

Or copy the backend files manually if not using git yet.

Install dependencies:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 6 — Test the Backend

```bash
python main.py
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open a browser on the Jetson and go to `http://localhost:8000/docs` to see the API documentation.

Test the chat endpoint:

```bash
curl -X POST http://localhost:8000/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello SANA", "user_id": "test"}'
```

You should get a response back from Llama 3.2.

---

## Step 7 — Set Up Auto-Start on Boot

Create the systemd service:

```bash
sudo tee /etc/systemd/system/sana.service > /dev/null << 'EOF'
[Unit]
Description=SANA Personal AI Agent
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=<your-username>
WorkingDirectory=/mnt/ssd/sana/backend
ExecStart=/mnt/ssd/sana/backend/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

Replace `<your-username>` with your actual Linux username.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sana
sudo systemctl start sana
sudo systemctl status sana
```

You should see `active (running)` in green.

---

## Step 8 — Install Tailscale for Remote Access

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Follow the printed URL to authenticate. Get your Tailscale IP:

```bash
tailscale ip -4
```

Install Tailscale on your phone and laptops (same account), and you can now access SANA from anywhere via `http://<tailscale-ip>:8000/docs`.

---

## Step 9 — Verify Everything Works After Reboot

```bash
sudo reboot
```

After reboot, just run:

```bash
curl http://localhost:8000/health/
```

If you get `{"status":"online","service":"SANA Backend"}`, autostart is working perfectly.

---

## Useful Commands

| Command | Purpose |
|---|---|
| `sudo systemctl status sana` | Check if SANA is running |
| `sudo systemctl restart sana` | Restart after code changes |
| `sudo journalctl -u sana -f` | Watch live logs |
| `sudo journalctl -u sana -n 50` | Last 50 log lines |
| `ollama list` | See installed models |
| `tailscale status` | See connected devices |

---

## Next Steps

- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if anything went wrong
- See [ARCHITECTURE.md](ARCHITECTURE.md) to understand how it all fits together
- Move on to building the mobile app (coming Week 2)
