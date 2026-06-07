"""Download bundled JavaScript libraries into static/js/.

Run this script when upgrading htmx or mermaid to a new version:
    uv run python scripts/download_js.py
"""

import urllib.request
from pathlib import Path

LIBS = [
    {
        "name": "htmx.min.js",
        "url": "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js",
    },
    {
        "name": "mermaid.min.js",
        "url": "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js",
    },
    {
        "name": "_hyperscript.min.js",
        "url": "https://unpkg.com/hyperscript.org@0.9.14/dist/_hyperscript.min.js",
    },
    {
        "name": "htmx-ext-sse.js",
        "url": "https://unpkg.com/htmx-ext-sse@2.2.2/sse.js",
    },
]

OUT_DIR = Path(__file__).parent.parent / "static" / "js"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for lib in LIBS:
        dest = OUT_DIR / lib["name"]
        print(f"Downloading {lib['name']} ...", end=" ", flush=True)
        urllib.request.urlretrieve(lib["url"], dest)
        size_kb = dest.stat().st_size / 1024
        print(f"done ({size_kb:.1f} KB)")
    print("All libraries saved to", OUT_DIR)


if __name__ == "__main__":
    main()
