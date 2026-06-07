#!/usr/bin/env python3
"""SVG → PNG → .icns 変換スクリプト（macOS 専用）"""

import shutil
import subprocess
import sys
from pathlib import Path

import cairosvg

ROOT = Path(__file__).parent.parent
SVG = ROOT / "static/icons/icon.svg"
ICONSET = ROOT / "static/icons/icon.iconset"
ICNS = ROOT / "static/icons/icon.icns"

# (通常解像度サイズ, @2x として使われるサイズ) のペア
# iconutil が要求するファイル名の一覧:
#   icon_16x16.png, icon_16x16@2x.png (=32px),
#   icon_32x32.png, icon_32x32@2x.png (=64px),
#   icon_128x128.png, icon_128x128@2x.png (=256px),
#   icon_256x256.png, icon_256x256@2x.png (=512px),
#   icon_512x512.png, icon_512x512@2x.png (=1024px)
ICONSET_SIZES = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]


def build() -> None:
    if not SVG.exists():
        print(f"Error: SVG not found: {SVG}", file=sys.stderr)
        sys.exit(1)

    if ICONSET.exists():
        shutil.rmtree(ICONSET)
    ICONSET.mkdir(parents=True)

    svg_data = SVG.read_bytes()

    for size, filename in ICONSET_SIZES:
        png = cairosvg.svg2png(bytestring=svg_data, output_width=size, output_height=size)
        (ICONSET / filename).write_bytes(png)

    try:
        result = subprocess.run(
            ["iconutil", "-c", "icns", str(ICONSET), "-o", str(ICNS)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("Error: iconutil not found — this script requires macOS", file=sys.stderr)
        shutil.rmtree(ICONSET)
        sys.exit(1)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        shutil.rmtree(ICONSET)
        sys.exit(1)

    shutil.rmtree(ICONSET)
    print(f"Created: {ICNS}")


if __name__ == "__main__":
    build()
