import os
import time
from pathlib import Path
from helpers import file_in_use, format_size

NEW_FILE_PROTECTION_SECONDS = 300


def clean_folder(folder, app, unlock=True):
    files = [Path(r) / f for r, _, fs in os.walk(folder) for f in fs]

    for path in files:
        try:
            stat = path.stat()
            size = stat.st_size

            if time.time() - stat.st_mtime < NEW_FILE_PROTECTION_SECONDS:
                status = "Protected: Recently modified"

                if app:
                    app.protected_count += 1

            elif file_in_use(path):
                status = "Used by another program"

            else:
                try:
                    path.unlink()

                    if app:
                        app.last_cleaned += 1
                        app.last_size_mb += size / (1024 ** 2)

                    status = "Deleted"

                except PermissionError:
                    if app:
                        app.protected_count += 1

                    status = "Needs Administrator Permission"

            if app:
                app.root.after(
                    0,
                    lambda r=(path.name, format_size(size), status):
                    app.add_rows_batch([r])
                )

        except Exception:
            continue

    if app:
        app.root.after(0, app.update_stats)

        if unlock:
            app.root.after(0, lambda: app.set_busy(False))


def clean_browser_cache(app):
    browser_paths = [
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Code Cache")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\GPUCache")),

        Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Code Cache")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\GPUCache")),
    ]

    for folder in browser_paths:
        if folder.exists():
            clean_folder(folder, app, unlock=False)

    if app:
        app.root.after(0, app.update_stats)
        app.root.after(0, lambda: app.set_busy(False))