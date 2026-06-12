#!/usr/bin/env bash
#
# SANA app launcher (Expo). Run from the app folder:   ./run_app.sh
#
# Same Wi-Fi as your Mac? Just run it and scan the QR with Expo Go.
# Different networks? Use the relay:   ./run_app.sh --tunnel
# Stuck/weird cache?  Clear it:        ./run_app.sh -c
#
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Starting Expo for the SANA app."
echo "    Open Expo Go on your iPhone and scan the QR code below."
echo "    Different Wi-Fi than the Mac?  Ctrl-C and rerun:  ./run_app.sh --tunnel"
echo
exec npx expo start "$@"
