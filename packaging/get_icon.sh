#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/packaging/norun.png"

# If already present, keep it
if [[ -f "$OUT" ]]; then
  echo "Icon exists: $OUT"
  exit 0
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# Try to download a usable PNG (512 or any size)
URL="https://github.com/AppImage/appimagekit/raw/master/resources/appimage.png"

echo "Downloading icon..."
if curl -L -f --retry 3 --retry-delay 1 -o "$TMPDIR/icon.png" "$URL"; then
  :
else
  echo "WARN: icon download failed; generating tiny fallback icon."
  # 1x1 png fallback (valid PNG)
  python3 - <<'PY' > "$OUT"
import base64, sys
data = base64.b64decode(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/6X9n3oAAAAASUVORK5CYII="
)
sys.stdout.buffer.write(data)
PY
  echo "OK: $OUT"
  exit 0
fi

# Resize to 256x256 if ImageMagick available
if command -v magick >/dev/null 2>&1; then
  magick "$TMPDIR/icon.png" -resize 256x256 "$OUT"
elif command -v convert >/dev/null 2>&1; then
  convert "$TMPDIR/icon.png" -resize 256x256 "$OUT"
else
  cp -f "$TMPDIR/icon.png" "$OUT"
fi

echo "OK: $OUT"

