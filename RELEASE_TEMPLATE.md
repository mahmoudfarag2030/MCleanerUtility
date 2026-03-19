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

The values should match before running the app.

## What's New

- Summarize the biggest user-facing improvements.
- Mention any Windows compatibility or startup stability fixes.
- Mention any new tools or cleanup areas added.

## Notes for Users

- Windows may show SmartScreen warnings for unsigned apps.
- If prompted, review the publisher and checksum before running.
- Some features may require Administrator rights depending on the action.

## Release Checklist

- Build the app with `python build.py`
- Confirm `dist/MCleaner.exe` exists
- Confirm `dist/MCleaner.exe.sha256` exists
- Run `python -m pytest`
- Smoke-test `dist/MCleaner.exe`
- Upload both files to GitHub Releases
