# Release Template

## Title

`MCleaner vX.Y.Z`

## Download

- `MCleaner.exe`
- `MCleaner.exe.sha256`

## SHA256 Verification

```powershell
Get-FileHash .\MCleaner.exe -Algorithm SHA256
Get-Content .\MCleaner.exe.sha256
```

The two hashes should match before you run the app.

## What's New

- Call out the main fixes or improvements in plain English.
- Mention anything that changes cleanup behavior, startup handling, or Windows compatibility.
- If you added a new tool or screen, say why it matters.

## Notes for Users

- Windows may show SmartScreen warnings for unsigned apps.
- If you are cautious about unsigned apps, verify the checksum before running the EXE.
- Some features may need Administrator rights depending on the action.

## Release Checklist

- Build the app with `python build.py`
- Confirm `dist/MCleaner.exe` exists
- Confirm `dist/MCleaner.exe.sha256` exists
- Run `python -m pytest`
- Smoke-test `dist/MCleaner.exe`
- Upload both files to GitHub Releases
