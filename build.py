"""Build helper script for producing a single-file executable.

This script deletes previous PyInstaller build artifacts (dist/, build/, .spec, __pycache__)
before running PyInstaller, so you always start from a clean state.

Usage:
    python build.py

You can also pass additional pyinstaller args:
    python build.py --onefile --windowed

"""

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CLEAN_PATHS = ["build", "dist", "__pycache__"]
SPEC_FILES = ["MCleaner.spec", "main.spec"]

PYINSTALLER_DEFAULT_ARGS = [
    "--onefile",
    "--windowed",
    "--icon=MCleaner.ico",
    "--add-data",
    "MCleaner.png;.",
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
    args = ["pyinstaller"] + PYINSTALLER_DEFAULT_ARGS
    if extra_args:
        args.extend(extra_args)

    print("Running:", " ".join(args))
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description="Clean build artifacts and run PyInstaller.")
    parser.add_argument(
        "--", dest="extra", nargs=argparse.REMAINDER, help="Extra args to pass to pyinstaller"
    )
    parsed = parser.parse_args()

    clean()
    run_pyinstaller(parsed.extra)


if __name__ == "__main__":
    main()
