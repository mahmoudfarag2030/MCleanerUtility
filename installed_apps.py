import winreg


def read_apps_from_key(root, path):
    apps = []

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
        pass

    return apps


def get_installed_apps():
    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    all_apps = []

    for root, path in locations:
        all_apps.extend(read_apps_from_key(root, path))

    all_apps.sort(key=lambda x: x[0].lower())

    return all_apps