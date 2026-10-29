#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; APP="$(dirname "$HERE")"; REPO="$(dirname "$APP")"
PY="${PYTHON:-$APP/.venv/Scripts/python.exe}"
# the version is the app's own (pse_r/config.py), unless given; the edition is public
# unless EDITION=andrej (rule 38: the personal edition never goes to a download page)
VERSION="${1:-$(sed -n 's/^VERSION = "\([^"]*\)".*/\1/p' "$APP/pse_r/config.py")}"; PKG="pse-riemann"
EDITION="${EDITION:-public}"
STAGE="$HERE/stage-win"; OUT="$REPO/dist"
ISCC="${ISCC:-/c/Program Files (x86)/Inno Setup 6/ISCC.exe}"
echo "== llama-cpp (CPU wheel) for the local GGUF main/skeptic"
LLAMA_ARGS=()
if "$PY" -m pip install --only-binary :all: \
     --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu llama-cpp-python; then
  LLAMA_ARGS=(--collect-all llama_cpp)
  echo "   llama-cpp: included"
else
  echo "   llama-cpp: NO Windows wheel — the .exe runs with cloud models only (logged)"
fi
echo "== edition: $EDITION · version: $VERSION"
printf 'EDITION = "%s"\n' "$EDITION" > "$APP/pse_r/_edition.py"
trap 'rm -f "$APP/pse_r/_edition.py"' EXIT
PACKS=()
[ "$EDITION" = "andrej" ] && PACKS=(--add-data "$(cygpath -w "$REPO/research/qrh-2026-10/method-packs");method-packs")
echo "== PyInstaller bundle"
rm -rf "$APP/build/pyi" "$STAGE"
"$PY" -m PyInstaller --noconfirm --clean --onedir --windowed --name "$PKG" \
  --icon "$HERE/$PKG.ico" \
  --distpath "$APP/build/pyi/dist" --workpath "$APP/build/pyi/work" --specpath "$APP/build/pyi" \
  --collect-submodules pse_r --collect-data pse_r --collect-all matplotlib \
  "${PACKS[@]}" \
  --add-data "$(cygpath -w "$HERE/$PKG.png");packaging" \
  "${LLAMA_ARGS[@]}" \
  "$APP/main.py"
APPDIR="$STAGE/$PKG"; mkdir -p "$APPDIR"
cp -a "$APP/build/pyi/dist/$PKG/." "$APPDIR/"
cp "$HERE/$PKG.ico" "$APPDIR/"; cp "$REPO/LICENSE" "$APPDIR/LICENSE.txt"; cp "$REPO/NOTICE" "$APPDIR/NOTICE.txt"
echo "== Inno Setup"; mkdir -p "$OUT"
MSYS2_ARG_CONV_EXCL="*" "$ISCC" "/DAppVersion=$VERSION" "/DSourceDir=$(cygpath -w "$APPDIR")" "/DOutDir=$(cygpath -w "$OUT")" \
  "$(cygpath -w "$HERE/$PKG.iss")"
echo "built $OUT/PSERiemann-Setup-$VERSION.exe"
