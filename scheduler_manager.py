import subprocess
from pathlib import Path

TASK_NAME = "MCleanerAutoCleanup"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
TASK_TIMEOUT_SECONDS = 15


def build_silent_cleanup_command(exe_path):
    exe = Path(exe_path)
    if exe.name.lower().startswith("python"):
        script_path = Path(__file__).resolve().parent / "main.py"
        return [str(exe), str(script_path), "--run-silent"]
    return [str(exe), "--run-silent"]


def build_schtasks_create_command(exe_path, mode):
    schedules = {"Daily": "DAILY", "Weekly": "WEEKLY", "Monthly": "MONTHLY"}

    if mode not in schedules:
        raise ValueError("Invalid schedule")

    target_args = build_silent_cleanup_command(exe_path)
    return [
        "schtasks",
        "/Create",
        "/SC",
        schedules[mode],
        "/TN",
        TASK_NAME,
        "/TR",
        subprocess.list2cmdline(target_args),
        "/F",
    ]


def create_task(exe_path, mode):
    try:
        cmd = build_schtasks_create_command(exe_path, mode)
    except ValueError:
        return False, "Invalid schedule"

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=TASK_TIMEOUT_SECONDS,
            creationflags=NO_WINDOW,
        )
        return True, f"{mode} schedule created successfully"
    except Exception as e:
        return False, str(e)


def delete_task():
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=TASK_TIMEOUT_SECONDS,
            creationflags=NO_WINDOW,
        )
        return True, "Schedule removed successfully"
    except Exception as e:
        return False, str(e)


def task_exists():
    cmd = ["schtasks", "/Query", "/TN", TASK_NAME]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=TASK_TIMEOUT_SECONDS,
            creationflags=NO_WINDOW,
        )
        return True
    except Exception:
        return False
