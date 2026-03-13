import subprocess

from scheduler_manager import create_task, delete_task, task_exists


def test_create_task_invalid_mode():
    ok, msg = create_task("python.exe", "Invalid")
    assert not ok
    assert "Invalid" in msg


def test_create_task_success(monkeypatch):
    def fake_run(*args, **kwargs):
        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, msg = create_task("python.exe", "Daily")
    assert ok
    assert "created" in msg.lower()


def test_delete_task_success(monkeypatch):
    def fake_run(*args, **kwargs):
        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    ok, msg = delete_task()
    assert ok
    assert "removed" in msg.lower()


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
