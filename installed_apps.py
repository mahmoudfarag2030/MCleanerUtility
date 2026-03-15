import winreg


def _query_value(subkey, name, default=None):
    try:
        return winreg.QueryValueEx(subkey, name)[0]
    except Exception:
        return default


def _normalize_text(value, fallback="-"):
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def read_apps_from_key(root, path):
    apps = []

    try:
        key = winreg.OpenKey(root, path)

        for i in range(winreg.QueryInfoKey(key)[0]):
            try:
                subkey_name = winreg.EnumKey(key, i)
                subkey = winreg.OpenKey(key, subkey_name)

                name = _query_value(subkey, "DisplayName")
                if not name:
                    continue

                version = _query_value(subkey, "DisplayVersion")
                publisher = _query_value(subkey, "Publisher")
                uninstall = _query_value(subkey, "UninstallString")
                quiet_uninstall = _query_value(subkey, "QuietUninstallString")
                no_remove = _query_value(subkey, "NoRemove", 0)
                system_component = _query_value(subkey, "SystemComponent", 0)

                apps.append(
                    {
                        "name": _normalize_text(name),
                        "version": _normalize_text(version),
                        "publisher": _normalize_text(publisher),
                        "uninstall": _normalize_text(uninstall, fallback=""),
                        "quiet_uninstall": _normalize_text(
                            quiet_uninstall, fallback=""
                        ),
                        "no_remove": int(no_remove) if no_remove is not None else 0,
                        "system_component": int(system_component)
                        if system_component is not None
                        else 0,
                        "registry_root": root,
                        "registry_path": path,
                        "subkey": subkey_name,
                    }
                )

            except Exception:
                continue

    except Exception:
        pass

    return apps


def get_installed_apps(detailed=False):
    locations = [
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
        (
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ),
    ]

    all_apps = []
    seen = set()

    for root, path in locations:
        for app in read_apps_from_key(root, path):
            key = (
                app["name"].lower(),
                app["version"].lower(),
                app["publisher"].lower(),
            )

            if key not in seen:
                seen.add(key)
                all_apps.append(app)

    all_apps.sort(key=lambda x: x["name"].lower())

    if detailed:
        return all_apps

    return [(a["name"], a["version"], a["publisher"]) for a in all_apps]


def get_installed_apps_detailed():
    return get_installed_apps(detailed=True)
