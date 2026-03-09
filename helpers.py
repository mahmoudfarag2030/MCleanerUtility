import ctypes
from pathlib import Path
import psutil


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def format_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024


def file_in_use(path: Path):
    try:
        with open(path, "a"):
            return False
    except Exception:
        return True


def browser_running_improved():
    targets = {"chrome.exe", "msedge.exe", "brave.exe"}

    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").lower()

            if name in targets:
                return True

        except Exception:
            continue

    return False
