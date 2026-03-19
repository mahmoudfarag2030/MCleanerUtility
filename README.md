# MCleanerUtility

MCleanerUtility is a small Windows cleanup app I built in Python with CustomTkinter.

The idea behind it was simple.

I wanted one lightweight desktop tool that could handle the cleanup tasks I actually use on my own PC without feeling bloated or confusing.

<img width="806" height="562" alt="image" src="https://github.com/user-attachments/assets/658bd9a8-0462-40cf-bcac-f7fa6c6f46c5" />


Right now the app can:

- clean Windows and user temp folders
- remove junk files, caches, crash dumps, and leftovers
- empty the Recycle Bin
- show installed apps and manage startup items
- schedule cleanup tasks through Task Scheduler
- monitor CPU, memory, and disk usage
- analyze disk usage by category and large files
- check a few basic Windows runtime components

Most of the recent work has been around making it safer and more reliable across different Windows setups.

If you want a quick summary of what changed between tagged versions, check [CHANGELOG.md](CHANGELOG.md).

## Direct Download

If you just want the app and do not care about the source, you can download the packaged `.exe` here:

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

## Build

To build the standalone executable:

```powershell
python build.py
```

That script clears old build artifacts first, then creates:

```text
dist/MCleaner.exe
```

If you prefer to call PyInstaller yourself:

```powershell
pyinstaller --onefile --windowed --icon=MCleaner.ico --add-data "MCleaner.png;." --add-data "build_info.py;." --collect-all customtkinter --name MCleaner --clean --noconfirm main.py
```

## Tests

To run the tests:

```powershell
python -m pytest
```

The repo uses a local pytest temp directory because the global Windows temp folder can sometimes be locked or flaky.

## A Few Notes

- This project is Windows-only and depends on Win32 APIs, Task Scheduler, and registry access.
- The repo keeps `dist/MCleaner.exe` checked in for convenience, while other generated build files stay ignored.
- The project is open source under the [MIT License](LICENSE.txt).
- The `MCleaner` name, logo, icon, and official branding are covered by the [Trademark Policy](TRADEMARKS.md).
- Some features may need Administrator rights depending on what you are trying to clean or change.

## License And Branding

The source code in this repository is available under the [MIT License](LICENSE.txt).

That means you can use, modify, and redistribute the code, including in your own forks.

However, the `MCleaner` name, logo, icon, and project branding are not granted under the MIT license. If you redistribute a modified version, do not imply that it is the official `MCleaner` project unless you have permission. See [TRADEMARKS.md](TRADEMARKS.md) for the branding rules.

## Contributing

Issues and pull requests are welcome. If you spot a bug, a Windows compatibility issue, or a cleanup target I missed, feel free to open one.
