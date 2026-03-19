"""Shared constants and utilities for MCleaner UI."""

import os
import sys
from pathlib import Path

APP_VERSION = "1.0.0"


def get_build_version() -> str:
    """Return the short hash of the latest commit."""
    try:
        import subprocess

        repo_dir = Path(__file__).resolve().parent.parent
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


BUILD_VERSION = get_build_version()

if BUILD_VERSION == "unknown":
    try:
        from build_info import BUILD_VERSION as _BUILD_VERSION

        BUILD_VERSION = _BUILD_VERSION
    except ImportError:
        pass


def resource_path(relative_path: str) -> str:
    """Return a path to a resource, handling PyInstaller's _MEIPASS."""

    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = Path(__file__).resolve().parent.parent

    return os.path.join(str(base_path), relative_path)


PREVIEW_SAMPLE_ROWS = 30
CPU_READER_INIT_DELAY_MS = 500
