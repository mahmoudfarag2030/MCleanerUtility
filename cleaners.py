import os
import time
from pathlib import Path
from helpers import file_in_use, format_size

NEW_FILE_PROTECTION_SECONDS = 300


def clean_folder(folder, app, unlock=True):
    files = [Path(r) / f for r, _, fs in os.walk(folder) for f in fs]

    for i, path in enumerate(files):
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
                    lambda r=(path.name, format_size(size), status): app.add_rows_batch([r])
                )

        except Exception:
            pass

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


# =========================================================
# INSTALLED APPS FEATURE
# =========================================================

def get_installed_apps():
    import winreg

    apps = []

    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for root, path in locations:
        try:
            key = winreg.OpenKey(root, path)

            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)

                    try:
                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                    except Exception:
                        continue

                    try:
                        version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                    except Exception:
                        version = "-"

                    try:
                        publisher = winreg.QueryValueEx(subkey, "Publisher")[0]
                    except Exception:
                        publisher = "-"

                    apps.append((name, version, publisher))

                except Exception:
                    continue

        except Exception:
            continue

    apps.sort(key=lambda x: x[0].lower())

    return apps