#!/usr/bin/env bash
# AppIcon/icon.svg から mmdview/Resources/AppIcon.icns を生成する。
# macOS 標準ツールのみ使用（rsvg-convert があればそちらを優先）。
set -euo pipefail

cd "$(dirname "$0")/.."

SVG="AppIcon/icon.svg"
ICNS="mmdview/Resources/AppIcon.icns"
WORK="$(mktemp -d)"
ICONSET="$WORK/AppIcon.iconset"
mkdir -p "$ICONSET"
trap 'rm -rf "$WORK"' EXIT

render_png() {
  local size="$1" out="$2"
  if command -v rsvg-convert &>/dev/null; then
    rsvg-convert -w "$size" -h "$size" "$SVG" -o "$out"
  else
    # QuickLook で SVG をラスタライズする（出力名は <元ファイル名>.png 固定）
    qlmanage -t -s "$size" -o "$WORK" "$SVG" >/dev/null
    mv "$WORK/$(basename "$SVG").png" "$out"
  fi
}

for size in 16 32 128 256 512; do
  render_png "$size" "$ICONSET/icon_${size}x${size}.png"
  render_png "$((size * 2))" "$ICONSET/icon_${size}x${size}@2x.png"
done

iconutil -c icns "$ICONSET" -o "$ICNS"
echo "generated: $ICNS"
