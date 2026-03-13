import os
import time

from cleaners import clean_folder


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
