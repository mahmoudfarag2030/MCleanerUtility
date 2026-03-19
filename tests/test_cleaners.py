import os
import time

from cleaners import clean_folder, try_delete_file


def test_clean_folder_removes_files(tmp_path):
    # Create some files and set their mtime older than the protection window
    file_paths = []
    for i in range(3):
        p = tmp_path / f"file_{i}.txt"
        p.write_text("hello")
        file_paths.append(p)

    # Ensure files are old enough to avoid protection logic
    old_time = time.time() - 1000
    for p in file_paths:
        os.utime(p, (old_time, old_time))

    result = clean_folder(tmp_path, app=None)

    assert result["deleted_count"] == len(file_paths)
    assert all(not p.exists() for p in file_paths)
    assert not any(tmp_path.iterdir())


def test_try_delete_file_reports_generic_permission_when_already_admin(
    monkeypatch, tmp_path
):
    target = tmp_path / "locked.tmp"
    target.write_text("hello")

    monkeypatch.setattr("cleaners.is_admin", lambda: True)
    monkeypatch.setattr(
        "pathlib.Path.unlink", lambda self: (_ for _ in ()).throw(PermissionError())
    )

    deleted, status = try_delete_file(target)

    assert deleted is False
    assert status == "Permission denied"


def test_try_delete_file_reports_admin_needed_when_not_elevated(monkeypatch, tmp_path):
    target = tmp_path / "locked.tmp"
    target.write_text("hello")

    monkeypatch.setattr("cleaners.is_admin", lambda: False)
    monkeypatch.setattr(
        "pathlib.Path.unlink", lambda self: (_ for _ in ()).throw(PermissionError())
    )

    deleted, status = try_delete_file(target)

    assert deleted is False
    assert status == "Needs Administrator Permission"
