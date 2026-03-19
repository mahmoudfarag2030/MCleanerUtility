"""Shared constants and utilities for MCleaner UI."""

import os
import subprocess
import sys
from pathlib import Path

DEFAULT_APP_VERSION = "1.0.1"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _normalize_version(raw_version: str) -> str:
    """Strip the leading tag prefix from a git version string."""
    return raw_version.removeprefix("v").strip()


def _is_frozen_app() -> bool:
    """Return True when running from a packaged executable."""
    return bool(getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None))


def _run_git_command(args: list[str], repo_dir: Path) -> str:
    """Run a git command without flashing a console window on Windows."""
    kwargs = {
        "cwd": repo_dir,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = NO_WINDOW

    out = subprocess.check_output(args, **kwargs)
    return out.decode().strip()


def _get_embedded_app_version() -> str | None:
    try:
        from build_info import APP_VERSION as _APP_VERSION

        if _APP_VERSION:
            return _normalize_version(_APP_VERSION)
    except ImportError:
        pass
    return None


def _get_embedded_build_version() -> str | None:
    try:
        from build_info import BUILD_VERSION as _BUILD_VERSION

        if _BUILD_VERSION:
            return _BUILD_VERSION
    except ImportError:
        pass
    return None


def get_app_version() -> str:
    """Return the latest tagged app version."""
    repo_dir = Path(__file__).resolve().parent.parent
    if _is_frozen_app():
        return _get_embedded_app_version() or DEFAULT_APP_VERSION

    try:
        version = _normalize_version(
            _run_git_command(
                ["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"],
                repo_dir,
            )
        )
        if version:
            return version
    except Exception:
        pass

    return _get_embedded_app_version() or DEFAULT_APP_VERSION


def get_build_version() -> str:
    """Return the short hash of the latest commit."""
    repo_dir = Path(__file__).resolve().parent.parent
    if _is_frozen_app():
        return _get_embedded_build_version() or "unknown"

    try:
        return _run_git_command(["git", "rev-parse", "--short", "HEAD"], repo_dir)
    except Exception:
        pass

    return _get_embedded_build_version() or "unknown"


APP_VERSION = get_app_version()
BUILD_VERSION = get_build_version()


def resource_path(relative_path: str) -> str:
    """Return a path to a resource, handling PyInstaller's _MEIPASS."""

    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = Path(__file__).resolve().parent.parent

    return os.path.join(str(base_path), relative_path)


PREVIEW_SAMPLE_ROWS = 30
CPU_READER_INIT_DELAY_MS = 500
