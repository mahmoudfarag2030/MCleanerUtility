# MCleanerUtility

A lightweight Windows cleanup utility built with Python and CustomTkinter. It provides a simple GUI for cleaning temporary folders, emptying the Recycle Bin, scheduling automatic cleanup, and more.

---

## ✅ Features

- Clean Windows temp folders and user temp folder
- Empty Recycle Bin
- Schedule periodic cleanup via Windows Task Scheduler
- View installed apps and manage startup items
- Built-in performance dashboard (CPU/RAM/Disk)
- Uses a modern CustomTkinter UI

---

## 🚀 Getting Started

### Requirements

- Windows 10/11
- Python 3.13 (recommended)
- Git (optional, for cloning)

### Setup (recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

> If `requirements.txt` is not present, you can install dependencies manually:
>
> ```powershell
> python -m pip install customtkinter pillow psutil openpyxl pyinstaller
> ```

---

## 🧰 Build (Create .exe)

A helper script is provided to clean old build artifacts and run PyInstaller:

```powershell
python build.py
```

This will remove `build/`, `dist/`, `__pycache__/`, and any existing `.spec` file before building.

If you prefer to run PyInstaller manually, use:

```powershell
pyinstaller --onefile --windowed --icon=MCleaner.ico --add-data "MCleaner.png;." --collect-all customtkinter --name MCleaner --clean --noconfirm main.py
```

---

## ▶️ Run (development)

```powershell
python main.py
```

---

## 🧪 Tests

Run the unit test suite:

```powershell
python -m pytest
```

---

## 📦 Notes

- The build process bundles all dependencies and resources into one executable (`dist/MCleaner.exe`).
- The executable is designed for Windows only.

---

## 🧩 Contributing

Contributions are welcome! Feel free to open issues or pull requests for improvements, bug fixes, or new features.

