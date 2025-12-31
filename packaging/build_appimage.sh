#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# ---------------- config ----------------
APP_NAME="Norun"
APP_ID="io.github.hasib.norun"
ICON_BASENAME="norun"
PKG_ICON="${ROOT_DIR}/packaging/norun.png"
TOOLS_DIR="${ROOT_DIR}/packaging/tools"
APPIMAGETOOL="${TOOLS_DIR}/appimagetool"
APPDIR="${ROOT_DIR}/AppDir"
# ---------------------------------------

ARCH_RAW="$(uname -m)"
case "${ARCH_RAW}" in
  x86_64|amd64) ARCH="x86_64" ;;
  aarch64|arm64) ARCH="aarch64" ;;
  *) ARCH="${ARCH_RAW}" ;;
esac

# ---------- appimagetool ----------
bash "${ROOT_DIR}/packaging/get_appimagetool.sh"

if [[ ! -x "${APPIMAGETOOL}" ]]; then
  echo "ERROR: appimagetool missing"
  exit 1
fi

PY="${PYTHON:-python3}"
if ! command -v "${PY}" >/dev/null 2>&1; then
  echo "ERROR: python3 not found on host"
  exit 1
fi

PYVER="$("${PY}" - <<'EOF'
import sys
print(f"python{sys.version_info[0]}.{sys.version_info[1]}")
EOF
)"

SITEPKG="${APPDIR}/usr/lib/${PYVER}/site-packages"

rm -rf "${APPDIR}"
mkdir -p \
  "${APPDIR}/usr/bin" \
  "${APPDIR}/usr/share/applications" \
  "${APPDIR}/usr/share/metainfo" \
  "${APPDIR}/usr/share/icons/hicolor/256x256/apps" \
  "${SITEPKG}"

echo "Bundling Python package into AppDir (target: ${SITEPKG}) ..."
"${PY}" -m pip install --upgrade pip >/dev/null
"${PY}" -m pip install . --target "${SITEPKG}"

# ---------- norun launcher ----------
cat > "${APPDIR}/usr/bin/norun" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PYTHON:-python3}"

if ! command -v "${PY}" >/dev/null 2>&1; then
  echo "python3 not found on host"
  exit 1
fi

for d in "${HERE}"/usr/lib/python*/site-packages; do
  if [[ -d "$d" ]]; then
    export PYTHONPATH="$d:${PYTHONPATH:-}"
    break
  fi
done

exec "${PY}" -m norun.cli "$@"
EOF
chmod +x "${APPDIR}/usr/bin/norun"

# ---------- AppRun ----------
install -m 755 packaging/AppRun "${APPDIR}/AppRun"

# ---------- Desktop ----------
DESKTOP_ROOT="${APPDIR}/${APP_ID}.desktop"
DESKTOP_USR="${APPDIR}/usr/share/applications/${APP_ID}.desktop"

cat > "${DESKTOP_ROOT}" <<EOF
[Desktop Entry]
Type=Application
Name=NORUN
Exec=norun
Icon=${ICON_BASENAME}
Terminal=false
Categories=Utility;
EOF

chmod 0644 "${DESKTOP_ROOT}"
cp -f "${DESKTOP_ROOT}" "${DESKTOP_USR}"

# ---------- Icon (optional) ----------
if [[ -f "${PKG_ICON}" ]]; then
  echo "Icon exists: ${PKG_ICON}"
  cp -f "${PKG_ICON}" "${APPDIR}/${ICON_BASENAME}.png"
  cp -f "${PKG_ICON}" \
    "${APPDIR}/usr/share/icons/hicolor/256x256/apps/${ICON_BASENAME}.png"
  ln -sf "${ICON_BASENAME}.png" "${APPDIR}/.DirIcon" || true
else
  echo "WARN: packaging/norun.png not found (icon skipped)"
fi

# ---------- AppStream ----------
APPDATA="${APPDIR}/usr/share/metainfo/${APP_ID}.appdata.xml"
cat > "${APPDATA}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>${APP_ID}</id>
  <name>NORUN</name>
  <summary>GUI+CLI Windows app runner (Wine + Proton)</summary>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>MIT</project_license>
  <launchable type="desktop-id">${APP_ID}.desktop</launchable>
  <description>
    <p>Run Windows apps using Wine or Proton with optional sandboxing.</p>
  </description>
  <url type="homepage">https://example.com/</url>
</component>
EOF

# ---------- Build ----------
OUT="${ROOT_DIR}/${APP_NAME}-${ARCH}.AppImage"
echo "Building AppImage -> ${OUT}"

set +e
ARCH="${ARCH}" "${APPIMAGETOOL}" "${APPDIR}" "${OUT}"
rc=$?
set -e

if [[ ${rc} -ne 0 && ! -f "${OUT}" ]]; then
  echo "ERROR: AppImage build failed"
  exit ${rc}
fi

chmod +x "${OUT}"
echo "Built: ${OUT}"
ls -lh "${OUT}"

