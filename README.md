# MCleanerUtility

MCleanerUtility is a Windows cleanup utility built with Python and CustomTkinter. It includes tools for:

- cleaning Windows and user temp folders
- cleaning junk files, caches, crash dumps, and leftovers
- emptying the Recycle Bin
- viewing installed apps and managing startup items
- running scheduled cleanup through Task Scheduler
- monitoring CPU, memory, and disk usage
- analyzing disk usage by category and large files
- checking basic Windows runtime components

The current build focuses on safer startup behavior, better cross-PC compatibility, and more stable Windows-specific operations.

## Direct Download

For non-technical users, download the ready-to-use Windows app here:

[Download MCleaner.exe](https://github.com/mahmoudfarag2030/MCleanerUtility/raw/refs/heads/master/dist/MCleaner.exe)

---

## Quick Start

### Requirements

- Windows 10/11
- Python 3.13 recommended

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Run in Development

```powershell
python main.py
```

---

## Build

Build the standalone executable with:

```powershell
python build.py
```

This cleans previous build artifacts and produces:

```text
dist/MCleaner.exe
```

You can also run PyInstaller manually:

```powershell
pyinstaller --onefile --windowed --icon=MCleaner.ico --add-data "MCleaner.png;." --add-data "build_info.py;." --collect-all customtkinter --name MCleaner --clean --noconfirm main.py
```

---

## Tests

Run the test suite with:

```powershell
python -m pytest
```

The repo is configured to use a local pytest temp directory so test runs stay stable on Windows systems where the global temp folder may be locked or restricted.

---

## Stability Notes

- Scheduled cleanup now builds the correct command for both source runs and packaged `.exe` runs.
- Resource loading no longer depends on the current working directory.
- Disk usage monitoring uses the actual Windows system drive instead of assuming `C:\`.
- Temp and junk cleanup batch UI updates to reduce lag on large folders.
- Startup toggle handling is more reliable across `HKCU`, `HKLM`, and Startup Folder entries.
- Disk Analyzer now waits for an explicit `Analyze` click instead of auto-starting.
- `pywin32` is included to improve Windows integration support in packaged builds.

---

## Notes

- This project is Windows-only and uses Win32 APIs, Task Scheduler, and registry access.
- The repo keeps `dist/MCleaner.exe` checked in while other generated build artifacts remain ignored.
- This project is open source under the [MIT License](LICENSE.txt).

---

## Contributing

Contributions are welcome through issues and pull requests.
