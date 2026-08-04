#!/bin/bash
# 本机复现 CI 的 macOS .app 打包（需 Apple Silicon + PyInstaller）
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p build/eggplant.iconset
for size in 16 32 64 128 256 512; do
  sips -z "$size" "$size" eggplant.png --out "build/eggplant.iconset/icon_${size}x${size}.png"
  sips -z $((size * 2)) $((size * 2)) eggplant.png --out "build/eggplant.iconset/icon_${size}x${size}@2x.png"
done
iconutil -c icns build/eggplant.iconset -o build/eggplant.icns

pyinstaller \
  --windowed \
  --name "茄子桌宠" \
  --icon=build/eggplant.icns \
  --add-data "eggplant.png:." \
  --add-data "eggplant.ico:." \
  --add-data "VERSION:." \
  --hidden-import bubble \
  --hidden-import chat \
  --hidden-import tray \
  --hidden-import storage \
  --hidden-import bookmarks \
  --hidden-import todos \
  --hidden-import ui_theme \
  --hidden-import updater \
  main.py

ditto -c -k --keepParent "dist/茄子桌宠.app" "dist/EggplantPet-macOS.zip"
echo "OK: dist/EggplantPet-macOS.zip"
