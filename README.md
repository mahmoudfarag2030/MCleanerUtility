# MCleanerUtility

MCleanerUtility is a lightweight Windows cleanup utility built with Python and CustomTkinter. It provides a simple, modern UI for:

- cleaning temporary folders (system + user temp)
- cleaning junk files (logs, caches, crash dumps, leftovers)
- emptying the Recycle Bin
- registry cleaner with backup/restore options
- scheduling automatic cleanup via Task Scheduler
- viewing installed apps and managing startup items
- monitoring system performance (CPU/RAM/Disk)

---

## 🚀 Quick Start

### Requirements

- Windows 10/11
- Python 3.13 (recommended)

### Setup (recommended)

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Run (development)

```powershell
python main.py
```

---

## 🧰 Build (Create a standalone executable)

A helper script is included to clean previous build outputs and run PyInstaller:

```powershell
python build.py
```

This removes `build/`, `dist/`, `__pycache__/` and any existing `.spec` files before building.

If you prefer to run PyInstaller manually:

```powershell
pyinstaller --onefile --windowed --icon=MCleaner.ico --add-data "MCleaner.png;." --collect-all customtkinter --name MCleaner --clean --noconfirm main.py
```

---

## 🧪 Tests

Run the unit test suite:

```powershell
python -m pytest
```

---

## 📦 Notes

- The build bundles all Python dependencies and assets into a single executable (`dist/MCleaner.exe`).
- This project is Windows-only (uses Win32 APIs and Task Scheduler).

---

## 🤝 Contributing

Contributions are welcome! Open an issue or a pull request for bug fixes, improvements, or new features.
