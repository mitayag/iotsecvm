import os
from pathlib import Path

ROOT = Path(os.environ.get("IOTLAB_ROOT", Path(__file__).resolve().parents[2]))
LABS_DIR = ROOT / "labs"
FRONTEND_DIR = ROOT / "frontend"
VERSION_FILE = ROOT / "VERSION"

ALLOW_MUTATIONS = os.environ.get("IOTLAB_ALLOW_MUTATIONS", "0") == "1"
USE_SUDO = os.environ.get("IOTLAB_USE_SUDO", "0") == "1"
ACTION_TIMEOUT_SECONDS = int(os.environ.get("IOTLAB_ACTION_TIMEOUT", "300"))


def version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
