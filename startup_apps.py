import winreg
from pathlib import Path
import os
import shutil


def clean_display_name(name):
    try:
        return os.path.basename(name).replace(".exe", "")
    except Exception:
        return name


def estimate_impact(name):
    heavy = ["steam", "discord", "adobe", "riot", "edge", "onedrive"]
    medium = ["realtek", "audio", "update"]

    n = name.lower()

    if any(x in n for x in heavy):
        return "High"

    if any(x in n for x in medium):
        return "Medium"

    return "Low"


def detect_publisher(name):
    n = name.lower()

    if "adobe" in n:
        return "Adobe"

    if "steam" in n:
        return "Valve"

    if "discord" in n:
        return "Discord"

    if "riot" in n:
        return "Riot Games"

    if "realtek" in n:
        return "Realtek"

    if "microsoft" in n or "edge" in n:
        return "Microsoft"

    if "onedrive" in n:
        return "Microsoft"

    return "Unknown"


def get_disabled_status_map():
    status_map = {}

    locations = [
        (
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        )
    ]

    for root, path in locations:
        try:
            key = winreg.OpenKey(root, path)

            count = winreg.QueryInfoKey(key)[1]

            for i in range(count):
                try:
                    name, value, _ = winreg.EnumValue(key, i)

                    if isinstance(value, bytes) and len(value) > 0:
                        status_map[name] = "Disabled" if value[0] == 3 else "Enabled"

                except Exception:
                    continue

        except Exception:
            continue

    return status_map


def read_registry_apps(root, path, source, status_map):
    apps = []

    try:
        key = winreg.OpenKey(root, path)

        count = winreg.QueryInfoKey(key)[1]

        for i in range(count):
            try:
                name, _, _ = winreg.EnumValue(key, i)

                clean = clean_display_name(name)

                apps.append((
                    clean,
                    status_map.get(name, "Enabled"),
                    source,
                    detect_publisher(clean),
                    estimate_impact(clean)
                ))

            except Exception:
                continue

    except Exception:
        pass

    return apps


def read_startup_folder():
    apps = []

    startup = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
    disabled = startup / "_Disabled"

    skip = {"desktop.ini", "thumbs.db"}

    try:
        if startup.exists():
            for item in startup.iterdir():
                if item.name.lower() in skip:
                    continue

                if item.name == "_Disabled":
                    continue

                apps.append((
                    item.name,
                    "Enabled",
                    "Startup Folder",
                    detect_publisher(item.name),
                    estimate_impact(item.name)
                ))

        if disabled.exists():
            for item in disabled.iterdir():
                if item.name.lower() in skip:
                    continue

                apps.append((
                    item.name,
                    "Disabled",
                    "Startup Folder",
                    detect_publisher(item.name),
                    estimate_impact(item.name)
                ))

    except Exception:
        pass

    return apps


def get_startup_apps():
    apps = []
    status_map = get_disabled_status_map()

    apps.extend(
        read_registry_apps(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            "HKCU Run",
            status_map
        )
    )

    apps.extend(
        read_registry_apps(
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            "HKLM Run",
            status_map
        )
    )

    apps.extend(read_startup_folder())

    apps.sort(key=lambda x: x[0].lower())

    return apps


def toggle_startup_folder_item(app_name, enable=True):
    startup = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
    disabled = startup / "_Disabled"

    source = disabled / app_name if enable else startup / app_name
    target = startup / app_name if enable else disabled / app_name

    try:
        disabled.mkdir(exist_ok=True)

        if source.exists():
            shutil.move(str(source), str(target))
            return True, "Startup Folder updated"

        return False, "File not found"

    except Exception as e:
        return False, str(e)


def toggle_registry_startup(app_name, enable=True):
    locations = [
        (
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        )
    ]

    value = (
        b'\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        if enable else
        b'\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    )

    for root, path in locations:
        try:
            key = winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, app_name, 0, winreg.REG_BINARY, value)
            return True, "Registry updated"

        except PermissionError:
            return False, "Requires Administrator Permission"

        except Exception:
            continue

    return False, "Startup entry not found"


def toggle_startup_app(app_name, enable=True):
    startup = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
    disabled = startup / "_Disabled"

    if (startup / app_name).exists() or (disabled / app_name).exists():
        return toggle_startup_folder_item(app_name, enable)

    return toggle_registry_startup(app_name, enable)
