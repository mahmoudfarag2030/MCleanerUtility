import os
import time
from pathlib import Path
from helpers import file_in_use, format_size

NEW_FILE_PROTECTION_SECONDS = 300


def clean_folder(folder, app=None, unlock=True):
    results = []
    deleted_count = 0
    deleted_mb = 0.0
    protected_count = 0

    files = [Path(r) / f for r, _, fs in os.walk(folder) for f in fs]
    total_files = len(files)

    for i, path in enumerate(files, start=1):
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

            if app:
                try:
                    app.root.after(0, lambda r=row: app.add_rows_batch([r]))
                except Exception:
                    pass

            if app and total_files:
                try:
                    progress = i / total_files
                    app.root.after(0, lambda p=progress: app.set_progress(p))
                except Exception:
                    pass

        except Exception:
            continue

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
