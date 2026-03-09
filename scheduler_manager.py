import subprocess

TASK_NAME = "MCleanerAutoCleanup"


def create_task(exe_path, mode):
    schedules = {
        "Daily": "DAILY",
        "Weekly": "WEEKLY",
        "Monthly": "MONTHLY"
    }

    if mode not in schedules:
        return False, "Invalid schedule"

    cmd = [
        "schtasks",
        "/Create",
        "/SC", schedules[mode],
        "/TN", TASK_NAME,
        "/TR", f'"{exe_path}" --run-silent',
        "/F"
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            shell=True
        )
        return True, f"{mode} schedule created successfully"
    except Exception as e:
        return False, str(e)


def delete_task():
    cmd = [
        "schtasks",
        "/Delete",
        "/TN", TASK_NAME,
        "/F"
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            shell=True
        )
        return True, "Schedule removed successfully"
    except Exception as e:
        return False, str(e)


def task_exists():
    cmd = [
        "schtasks",
        "/Query",
        "/TN", TASK_NAME
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            shell=True
        )
        return True
    except Exception:
        return False