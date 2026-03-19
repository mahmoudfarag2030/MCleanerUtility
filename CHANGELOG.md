# Changelog

## v1.0.3 - 2026-03-20

This release fixes a misleading cleanup status that could claim Administrator rights were needed even when the app was already elevated.

- Retried deletes after clearing the read-only flag on Windows temp files.
- Changed elevated delete failures to report a generic permission error instead of incorrectly asking for admin rights.
- Added regression tests covering elevated and non-elevated permission handling.

## v1.0.2 - 2026-03-20

This release focuses on smoother startup and a more responsive scheduler experience.

- Removed the brief console flash on startup by preferring embedded build metadata in the packaged app.
- Made the Scheduled Cleanup window and Create/Remove actions non-blocking so the UI stays responsive.
- Hid and timed out `schtasks` calls to avoid visible command windows and long hangs.
- Rebuilt and published the `MCleaner.exe` for the release.

## v1.0.1 - 2026-03-19

This was a small follow-up release focused on packaging and download confidence.

- Added automatic SHA256 checksum generation during the build.
- Added a simple release template so release posts stay consistent.
- Updated the packaged download assets for the release.

## v1.0.0 - 2026-03-19

This was the first tagged 1.0 release and the point where the app felt stable enough to share more confidently.

- Tightened up startup behavior across different Windows setups.
- Cleaned up version and build display in the UI.
- Refreshed the docs and packaging around the first public release.
