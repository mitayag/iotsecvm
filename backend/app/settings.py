from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_root() -> Path:
    return Path(os.environ.get("IOTLAB_ROOT", Path(__file__).resolve().parents[2]))


def _read_version(root: Path) -> str:
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


@dataclass(frozen=True)
class Settings:
    root: Path
    frontend_dir: Path
    helper_socket: Path | None
    enable_actions: bool
    helper_timeout: float
    action_timeout: float
    version: str

    @property
    def labs_dir(self) -> Path:
        return self.root / "labs"

    @property
    def evidence_dir(self) -> Path:
        return self.root / "var" / "evidence"

    @classmethod
    def from_env(cls) -> "Settings":
        root = _default_root().resolve()
        socket_value = os.environ.get("IOTLAB_HELPER_SOCKET", "").strip()
        return cls(
            root=root,
            frontend_dir=root / "frontend",
            helper_socket=Path(socket_value) if socket_value else None,
            enable_actions=os.environ.get("IOTLAB_ENABLE_ACTIONS", "0") == "1",
            helper_timeout=float(os.environ.get("IOTLAB_HELPER_TIMEOUT", "330")),
            action_timeout=float(os.environ.get("IOTLAB_ACTION_TIMEOUT", "300")),
            version=_read_version(root),
        )


SETTINGS = Settings.from_env()


def get_settings() -> Settings:
    return SETTINGS
