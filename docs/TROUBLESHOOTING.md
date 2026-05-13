# SANA Troubleshooting

Common issues and their fixes.

---

## Chromium Won't Install on JetPack R36

**Symptoms:**
```
cannot locate "matchpathcon" executable
snap-confine is packaged without necessary permissions
required permitted capability cap_dac_override not found
```

**Cause:** Snap's confinement system is broken on JetPack R36.4.4 due to kernel-level capability limitations.

**Fix:** Download a working snapd revision manually:

```bash
sudo snap remove chromium
sudo snap remove firefox
snap download snapd --revision=24724
sudo snap ack snapd_24724.assert
sudo snap install snapd_24724.snap
sudo systemctl restart snapd
sudo snap install chromium
chromium &
```

**Alternative:** Use Flatpak instead of Snap:

```bash
sudo apt install flatpak -y
sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
sudo flatpak install flathub org.chromium.Chromium
```

---

## SSD Not Auto-Mounting After Reboot

**Symptoms:** `/mnt/ssd` is empty after boot.

**Cause:** Missing or incorrect fstab entry.

**Fix:**

```bash
# Check current fstab
cat /etc/fstab

# Get SSD UUID
sudo blkid /dev/nvme0n1p1

# Add to fstab (replace UUID)
echo 'UUID=<your-uuid> /mnt/ssd ext4 defaults 0 2' | sudo tee -a /etc/fstab

# Test mount
sudo mount -a
ls /mnt/ssd
```

---

## CUDA Out Of Memory When Loading Model

**Symptoms:**
```
cudaMalloc failed: out of memory
error loading model: unable to allocate CUDA0 buffer
```

**Cause:** Model is too large for Jetson Orin Nano's 8GB shared memory (CPU + GPU split).

**Fix:** Use a smaller model:

```bash
# Pull the 1b model instead of 8b/3b
ollama pull llama3.2:1b

# Update SANA to use it
sed -i 's/llama3.2:3b/llama3.2:1b/g' /mnt/ssd/sana/backend/agent/core.py
sed -i 's/llama3.1:8b/llama3.2:1b/g' /mnt/ssd/sana/backend/agent/core.py

# Restart SANA
sudo systemctl restart sana
```

**Model recommendations for Jetson Orin Nano:**

| Model | Size | Status |
|-------|------|--------|
| llama3.2:1b | 1.3GB | Recommended |
| llama3.2:3b | 2GB | Works but tight |
| phi3:mini | 2.3GB | Works |
| llama3.1:8b | 4.9GB | Will OOM |

---

## Ollama Permission Denied On SSD

**Symptoms:**
```
Error: open /mnt/ssd/ollama/models/blobs/...partial-0: permission denied
```

**Cause:** Ollama runs as the `ollama` user but the folder is owned by another user.

**Fix:**

```bash
sudo chown -R ollama:ollama /mnt/ssd/ollama
```

---

## Ollama Loads From Wrong Path After Service Restart

**Symptoms:** Ollama still loads models from `/usr/share/ollama/.ollama/models` instead of `/mnt/ssd/ollama/models`.

**Cause:** Environment variable not set in systemd service.

**Fix:**

```bash
sudo systemctl edit ollama
```

Add:

```ini
[Service]
Environment="OLLAMA_MODELS=/mnt/ssd/ollama/models"
```

Save and restart:

```bash
sudo systemctl restart ollama
```

---

## SANA Returns 500 Error On Chat

**Symptoms:** API call returns 500 Internal Server Error with empty detail.

**Cause #1:** Ollama isn't running or model isn't loaded.

**Fix:**

```bash
sudo systemctl status ollama
ollama list
```

If Ollama isn't running:

```bash
sudo systemctl start ollama
```

**Cause #2:** Out of memory (see above).

**Cause #3:** `conversation_id` sent as literal `"string"` placeholder.

**Fix:** Already handled in updated `chat.py` (treats `"string"` as None). Otherwise, omit the field in the request.

---

## Port 8000 Already In Use

**Symptoms:**
```
Error: [Errno 98] address already in use
```

**Cause:** Another SANA instance is already running (likely the systemd service).

**Fix:**

```bash
# Find what's using port 8000
sudo lsof -i :8000

# Stop the SANA service if running
sudo systemctl stop sana

# Or kill the process
sudo kill -9 <PID>
```

---

## Can't Reach SANA From Phone

**Symptoms:** SANA works locally but phone can't connect.

**Diagnostic steps:**

```bash
# On Jetson — confirm SANA is listening on all interfaces
sudo netstat -tulpn | grep 8000
# Should show 0.0.0.0:8000, not 127.0.0.1:8000

# Check Tailscale is connected
tailscale status

# Get the Tailscale IP
tailscale ip -4
```

On phone, ensure Tailscale app is logged in and connected. Visit `http://<tailscale-ip>:8000/docs` in mobile browser.

---

## ImportError When Starting Backend

**Symptoms:** `ModuleNotFoundError: No module named 'fastapi'` etc.

**Cause:** Virtual environment not activated.

**Fix:**

```bash
cd /mnt/ssd/sana/backend
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## Editor "nano: command not found"

**Symptoms:** Trying to edit a file with nano fails.

**Fix:**

```bash
sudo apt install nano -y
```

Alternative — use `vi`, or skip the editor entirely with `tee`:

```bash
sudo tee /path/to/file > /dev/null << 'EOF'
file contents here
EOF
```

---

## Need More Help?

Check the systemd logs for the real error:

```bash
sudo journalctl -u sana -n 100
sudo journalctl -u ollama -n 100
```
