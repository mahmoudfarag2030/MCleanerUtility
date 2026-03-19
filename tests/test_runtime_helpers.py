import sys
import winreg
from pathlib import Path

import build_info
from helpers import get_system_drive_root
from startup_apps import toggle_startup_app, toggle_registry_startup
from ui.constants import get_app_version, get_build_version, resource_path


def test_get_system_drive_root_defaults(monkeypatch):
    monkeypatch.delenv("SystemDrive", raising=False)
    monkeypatch.setenv("WINDIR", r"D:\Windows")
    assert get_system_drive_root() == "D:\\"


def test_get_system_drive_root_from_env(monkeypatch):
    monkeypatch.setenv("SystemDrive", "E:")
    assert get_system_drive_root() == "E:\\"


def test_resource_path_uses_project_root_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    result = Path(resource_path("MCleaner.png"))
    assert result.name == "MCleaner.png"
    assert result.parent == Path(__file__).resolve().parents[1]


def test_get_app_version_strips_tag_prefix(monkeypatch):
    monkeypatch.setattr(
        "ui.constants.subprocess.check_output",
        lambda *args, **kwargs: b"v1.2.3\n",
    )
    assert get_app_version() == "1.2.3"


def test_get_app_version_falls_back_to_build_info(monkeypatch):
    def raise_git_error(*args, **kwargs):
        raise RuntimeError("git unavailable")

    monkeypatch.setattr("ui.constants.subprocess.check_output", raise_git_error)
    monkeypatch.setattr(build_info, "APP_VERSION", "v9.9.9", raising=False)
    assert get_app_version() == "9.9.9"


def test_get_build_version_falls_back_to_build_info(monkeypatch):
    def raise_git_error(*args, **kwargs):
        raise RuntimeError("git unavailable")

    monkeypatch.setattr("ui.constants.subprocess.check_output", raise_git_error)
    monkeypatch.setattr(build_info, "BUILD_VERSION", "abc1234", raising=False)
    assert get_build_version() == "abc1234"


def test_get_app_version_prefers_embedded_build_info_when_frozen(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("git should not run in packaged mode")

    monkeypatch.setattr("ui.constants._is_frozen_app", lambda: True)
    monkeypatch.setattr("ui.constants.subprocess.check_output", fail_if_called)
    monkeypatch.setattr(build_info, "APP_VERSION", "v2.0.0", raising=False)
    assert get_app_version() == "2.0.0"


def test_get_build_version_prefers_embedded_build_info_when_frozen(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("git should not run in packaged mode")

    monkeypatch.setattr("ui.constants._is_frozen_app", lambda: True)
    monkeypatch.setattr("ui.constants.subprocess.check_output", fail_if_called)
    monkeypatch.setattr(build_info, "BUILD_VERSION", "frozen123", raising=False)
    assert get_build_version() == "frozen123"


def test_toggle_startup_app_uses_source_to_route_folder_entries(monkeypatch):
    captured = {}

    def fake_toggle_folder(app_name, enable=True):
        captured["call"] = (app_name, enable)
        return True, "folder"

    monkeypatch.setattr("startup_apps.toggle_startup_folder_item", fake_toggle_folder)

    ok, msg = toggle_startup_app("Demo.lnk", False, source="Startup Folder")
    assert (ok, msg) == (True, "folder")
    assert captured["call"] == ("Demo.lnk", False)


def test_toggle_registry_startup_targets_requested_hive(monkeypatch):
    calls = []

    class DummyKey:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_open(root, path, reserved=0, access=0):
        calls.append(("open", root, path, access))
        return DummyKey()

    def fake_set_value(key, name, reserved, value_type, value):
        calls.append(("set", name, value_type, value))

    monkeypatch.setattr("startup_apps.winreg.OpenKey", fake_open)
    monkeypatch.setattr("startup_apps.winreg.SetValueEx", fake_set_value)

    ok, msg = toggle_registry_startup("DemoApp", enable=False, registry_root=winreg.HKEY_CURRENT_USER)
    assert (ok, msg) == (True, "Registry updated")
    assert calls[0][1] == winreg.HKEY_CURRENT_USER
    assert all(call[1] != winreg.HKEY_LOCAL_MACHINE for call in calls if call[0] == "open")
