#!/bin/sh
# Re-render the 1200x630 social preview image (site/og.jpg) from the live page in poster mode.
# Needs the site served locally, e.g.:  python3 -m http.server 8766 -d site
URL="${1:-http://localhost:8766/?poster}"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 --window-size=1200,630 --virtual-time-budget=20000 \
  --blink-settings=preferredColorScheme=1 --screenshot=/tmp/og.png "$URL" && python3 -c "from PIL import Image; Image.open('/tmp/og.png').convert('RGB').save('site/og.jpg', quality=84, optimize=True, progressive=True)"
