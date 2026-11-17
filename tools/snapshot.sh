#!/usr/bin/env bash
# Static PNG of a figpack figure, for the GitHub rendering of a report (GitHub drops iframes).
# Usage: tools/snapshot.sh <figure url> <out.png> [width height]
set -euo pipefail
url=$1; out=$2; w=${3:-1280}; h=${4:-720}
google-chrome --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1.5 \
  --window-size="$w,$h" --virtual-time-budget=15000 --screenshot="$out" "$url" 2>/dev/null
echo "wrote $out"
