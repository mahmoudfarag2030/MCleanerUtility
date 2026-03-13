"""Shared constants and utilities for MCleaner UI."""

import os
import sys
from pathlib import Path

APP_VERSION = "0.9.0"


def get_build_version() -> str:
    """Return a short build identifier based on the current git commit (if available)."""
    try:
        import subprocess

        repo_dir = Path(__file__).resolve().parent.parent
        out = subprocess.check_output(
            ["git", "describe", "--always", "--dirty"],
            cwd=repo_dir,
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


BUILD_VERSION = get_build_version()


def resource_path(relative_path: str) -> str:
    """Return a path to a resource, handling PyInstaller's _MEIPASS."""

    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


PREVIEW_SAMPLE_ROWS = 30
CPU_READER_INIT_DELAY_MS = 500
