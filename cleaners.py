import os
import time
from pathlib import Path
from helpers import file_in_use, format_size

NEW_FILE_PROTECTION_SECONDS = 300
UI_BATCH_SIZE = 50
PROGRESS_UPDATE_INTERVAL = 25


def iter_files(folder):
    for root_dir, _, files in os.walk(folder):
        for fname in files:
            yield Path(root_dir) / fname


def count_files(folder):
    total = 0
    for _, _, files in os.walk(folder):
        total += len(files)
    return total


def clean_folder(folder, app=None, unlock=True):
    results = []
    deleted_count = 0
    deleted_mb = 0.0
    protected_count = 0

    total_files = count_files(folder)
    batch = []

    for i, path in enumerate(iter_files(folder), start=1):
        try:
            stat = path.stat()
            size = stat.st_size

            if time.time() - stat.st_mtime < NEW_FILE_PROTECTION_SECONDS:
                status = "Protected: Recently modified"
                protected_count += 1

            elif file_in_use(path):
                status = "Used by another program"

            else:
                try:
                    path.unlink()
                    deleted_count += 1
                    deleted_mb += size / (1024**2)
                    status = "Deleted"

                except PermissionError:
                    protected_count += 1
                    status = "Needs Administrator Permission"

            row = (path.name, format_size(size), status)
            results.append(row)
            batch.append(row)

            if app and len(batch) >= UI_BATCH_SIZE:
                try:
                    rows = batch[:]
                    batch.clear()
                    app.root.after(0, lambda r=rows: app.add_rows_batch(r))
                except Exception:
                    pass

            if app and total_files and (
                i % PROGRESS_UPDATE_INTERVAL == 0 or i == total_files
            ):
                try:
                    progress = i / total_files
                    app.root.after(0, lambda p=progress: app.set_progress(p))
                except Exception:
                    pass

        except Exception:
            continue

    if app and batch:
        try:
            rows = batch[:]
            app.root.after(0, lambda r=rows: app.add_rows_batch(r))
        except Exception:
            pass

    if app:
        try:
            app.last_cleaned += deleted_count
            app.last_size_mb += deleted_mb
            app.protected_count += protected_count
            app.root.after(0, app.update_stats)

            if unlock:
                app.root.after(0, lambda: app.set_busy(False))
        except Exception:
            pass

    return {
        "rows": results,
        "deleted_count": deleted_count,
        "deleted_mb": deleted_mb,
        "protected_count": protected_count,
    }


def clean_browser_cache(app=None):
    browser_paths = [
        Path(
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache")
        ),
        Path(
            os.path.expandvars(
                r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Code Cache"
            )
        ),
        Path(
            os.path.expandvars(
                r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\GPUCache"
            )
        ),
        Path(
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache")
        ),
        Path(
            os.path.expandvars(
                r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Code Cache"
            )
        ),
        Path(
            os.path.expandvars(
                r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\GPUCache"
            )
        ),
    ]

    combined = {
        "rows": [],
        "deleted_count": 0,
        "deleted_mb": 0.0,
        "protected_count": 0,
    }

    for folder in browser_paths:
        if folder.exists():
            result = clean_folder(folder, app=app, unlock=False)

            combined["rows"].extend(result["rows"])
            combined["deleted_count"] += result["deleted_count"]
            combined["deleted_mb"] += result["deleted_mb"]
            combined["protected_count"] += result["protected_count"]

    if app:
        try:
            app.root.after(0, app.update_stats)
            app.root.after(0, lambda: app.set_busy(False))
        except Exception:
            pass

    return combined


def clean_junk_files(app=None):
    junk_paths = [
        Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Temp",
        Path(os.path.expandvars(r"%temp%")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\\Temp")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\\CrashDumps")),
        Path(os.path.expandvars(r"%PROGRAMDATA%\\Microsoft\\Windows\\WER\\ReportQueue")),
        Path(os.path.expandvars(r"%PROGRAMDATA%\\Microsoft\\Windows\\WER\\ReportArchive")),
        Path(os.path.expandvars(r"%APPDATA%\\Microsoft\\Windows\\Recent")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer")),
    ]

    combined = {
        "rows": [],
        "deleted_count": 0,
        "deleted_mb": 0.0,
        "protected_count": 0,
    }

    for folder in junk_paths:
        try:
            if folder.exists():
                result = clean_folder(folder, app=app, unlock=False)
                combined["rows"].extend(result["rows"])
                combined["deleted_count"] += result["deleted_count"]
                combined["deleted_mb"] += result["deleted_mb"]
                combined["protected_count"] += result["protected_count"]
        except Exception:
            continue

    if app:
        try:
            app.root.after(0, app.update_stats)
            app.root.after(0, lambda: app.set_busy(False))
        except Exception:
            pass

    return combined
