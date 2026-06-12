#!/usr/bin/env bash
#
# Expose the SANA backend to the internet via ngrok, so the phone app can reach
# it WITHOUT Tailscale. Run this in a SECOND terminal, after ./run_mac.sh is up.
#
# One-time setup:
#   1. Sign up free at https://ngrok.com
#   2. brew install ngrok
#   3. ngrok config add-authtoken <your-token>
#   4. Claim your free static domain at https://dashboard.ngrok.com/domains
#   5. Run with that domain:
#        SANA_NGROK_DOMAIN=your-name.ngrok-free.app ./run_tunnel.sh
#
set -euo pipefail
cd "$(dirname "$0")"

PORT="${SANA_PORT:-8000}"
DOMAIN="${SANA_NGROK_DOMAIN:-}"

if ! command -v ngrok >/dev/null 2>&1; then
  echo "!! ngrok isn't installed.  Run:  brew install ngrok   then try again."
  exit 1
fi

if [ -z "$DOMAIN" ]; then
  echo "!! No static domain set."
  echo "   Claim a free one at https://dashboard.ngrok.com/domains, then run:"
  echo "       SANA_NGROK_DOMAIN=your-name.ngrok-free.app ./run_tunnel.sh"
  echo "   (Or run 'ngrok http $PORT' directly for a random URL that changes each restart.)"
  exit 1
fi

echo "==> Tunneling  https://$DOMAIN  ->  localhost:$PORT"
echo "    Put this in the app's src/config.js as SANA_URL:  https://$DOMAIN"
echo
exec ngrok http "--domain=$DOMAIN" "$PORT"
