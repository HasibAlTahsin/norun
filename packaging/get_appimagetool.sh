#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="${ROOT_DIR}/packaging/tools"
APPIMAGETOOL="${TOOLS_DIR}/appimagetool"

mkdir -p "${TOOLS_DIR}"

if [[ -x "${APPIMAGETOOL}" ]]; then
  echo "OK: ${APPIMAGETOOL}"
  "${APPIMAGETOOL}" --version || true
  exit 0
fi

ARCH_RAW="$(uname -m)"
case "${ARCH_RAW}" in
  x86_64|amd64) ARCH="x86_64" ;;
  aarch64|arm64) ARCH="aarch64" ;;
  *) ARCH="${ARCH_RAW}" ;;
esac

URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"

echo "Downloading appimagetool for ${ARCH} ..."
echo "  -> ${URL}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl not installed. Please install curl."
  exit 1
fi

tmp="$(mktemp)"
if ! curl -L --fail --retry 3 --retry-delay 1 -o "${tmp}" "${URL}"; then
  echo "ERROR: failed to download appimagetool from ${URL}"
  rm -f "${tmp}"
  exit 1
fi

chmod +x "${tmp}"
mv "${tmp}" "${APPIMAGETOOL}"

echo "OK: ${APPIMAGETOOL}"
"${APPIMAGETOOL}" --version || true

