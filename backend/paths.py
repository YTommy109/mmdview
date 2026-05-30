import sys
from pathlib import Path

# In PyInstaller bundle, files are extracted to sys._MEIPASS; otherwise use project root.
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"
STATIC_DIR = BASE_DIR / "static"

APP_DATA_DIR = Path.home() / "Library" / "Application Support" / "mmdview"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

WINDOW_STATE_FILE = APP_DATA_DIR / "window_state.json"
