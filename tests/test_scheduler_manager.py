import subprocess
from pathlib import Path

from scheduler_manager import (
    build_schtasks_create_command,
    build_silent_cleanup_command,
    create_task,
    delete_task,
    task_exists,
)


def test_create_task_invalid_mode():
    ok, msg = create_task("python.exe", "Invalid")
    assert not ok
    assert "Invalid" in msg


def test_build_silent_cleanup_command_for_python():
    args = build_silent_cleanup_command("python.exe")
    assert args[0] == "python.exe"
    assert args[-1] == "--run-silent"
    assert Path(args[1]).name == "main.py"


def test_build_silent_cleanup_command_for_frozen_exe():
    args = build_silent_cleanup_command(r"C:\Apps\MCleaner.exe")
    assert args == [r"C:\Apps\MCleaner.exe", "--run-silent"]


def test_build_schtasks_create_command_quotes_target():
    cmd = build_schtasks_create_command(r"C:\Program Files\MCleaner\MCleaner.exe", "Daily")
    assert cmd[:2] == ["schtasks", "/Create"]
    assert cmd[cmd.index("/SC") + 1] == "DAILY"
    assert '"C:\\Program Files\\MCleaner\\MCleaner.exe" --run-silent' in cmd


def test_create_task_success(monkeypatch):
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, msg = create_task("python.exe", "Daily")
    assert ok
    assert "created" in msg.lower()
    assert not captured["kwargs"].get("shell", False)
    assert captured["args"][0][0] == "schtasks"


def test_delete_task_success(monkeypatch):
    captured = {}

    def fake_run(*args, **kwargs):
        captured["kwargs"] = kwargs

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, msg = delete_task()
    assert ok
    assert "removed" in msg.lower()
    assert "shell" not in captured["kwargs"]


def test_task_exists_true(monkeypatch):
    def fake_run(*args, **kwargs):
        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert task_exists() is True


def test_task_exists_false(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=args[0])

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert task_exists() is False
