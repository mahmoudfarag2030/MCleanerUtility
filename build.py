"""Build helper script for producing a single-file executable.

This script deletes previous PyInstaller build artifacts (dist/, build/, .spec, __pycache__)
before running PyInstaller, so you always start from a clean state.

Usage:
    python build.py

You can also pass additional pyinstaller args:
    python build.py --onefile --windowed

"""

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_APP_VERSION = "1.0.2"

CLEAN_PATHS = ["build", "dist", "__pycache__"]
SPEC_FILES = ["MCleaner.spec", "main.spec", "build_info.py"]
DIST_EXE = ROOT / "dist" / "MCleaner.exe"


def get_build_version() -> str:
    """Return the short hash of the latest commit."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


def get_app_version() -> str:
    """Return the latest tagged app version."""
    try:
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        version = out.decode().strip().removeprefix("v")
        return version or DEFAULT_APP_VERSION
    except Exception:
        return DEFAULT_APP_VERSION


def write_sha256(file_path: Path) -> Path:
    """Write a .sha256 checksum file next to the built executable."""
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)

    checksum_path = file_path.with_suffix(file_path.suffix + ".sha256")
    checksum_path.write_text(f"{digest.hexdigest()}  {file_path.name}\n", encoding="ascii")
    return checksum_path

PYINSTALLER_DEFAULT_ARGS = [
    "--onefile",
    "--windowed",
    "--icon=MCleaner.ico",
    "--add-data",
    "MCleaner.png;.",
    "--add-data",
    "build_info.py;.",
    "--collect-all",
    "customtkinter",
    "--name",
    "MCleaner",
    "--clean",
    "--noconfirm",
    "main.py",
]


def clean():
    """Remove previous build artifacts."""
    for path in CLEAN_PATHS:
        p = ROOT / path
        if p.exists():
            print(f"Removing {p}...")
            shutil.rmtree(p, ignore_errors=True)

    for spec in SPEC_FILES:
        sp = ROOT / spec
        if sp.exists():
            print(f"Removing {sp}...")
            sp.unlink()


def run_pyinstaller(extra_args=None):
    # Create build info file with the latest tagged app version and current build hash.
    app_version = get_app_version()
    build_version = get_build_version()
    build_info_path = ROOT / "build_info.py"
    build_info_path.write_text(
        f'APP_VERSION = "{app_version}"\nBUILD_VERSION = "{build_version}"\n',
        encoding="ascii",
    )

    # Use the current Python interpreter to ensure we run PyInstaller from the active env.
    args = [sys.executable, "-m", "PyInstaller"] + PYINSTALLER_DEFAULT_ARGS
    if extra_args:
        args.extend(extra_args)

    print("Running:", " ".join(args))
    subprocess.run(args, check=True)

    if DIST_EXE.exists():
        checksum_path = write_sha256(DIST_EXE)
        print(f"SHA256 written to: {checksum_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Clean build artifacts and run PyInstaller."
    )
    parser.add_argument(
        "--",
        dest="extra",
        nargs=argparse.REMAINDER,
        help="Extra args to pass to pyinstaller",
    )
    parsed = parser.parse_args()

    clean()
    run_pyinstaller(parsed.extra)


if __name__ == "__main__":
    main()
