from __future__ import annotations

from pathlib import Path


def frontend_dir() -> Path:
    return Path(__file__).resolve().parent / "frontend"
