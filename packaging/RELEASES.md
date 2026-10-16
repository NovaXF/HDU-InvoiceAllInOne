# Windows releases

The current version is defined in `app_version.py`. Settings and the help page
read the same value. The settings page accepts a public GitHub repository URL.
Public releases can be checked without asking end users to sign in.

Push a tag such as `v1.0.1` to run `.github/workflows/release.yml`. The workflow
tests the code, builds a standalone Windows portable executable, verifies it in
an isolated directory without Python sources, and uploads it to the Release.
The packaged version and GitHub repository are configured automatically.
The workflow can also run manually for the version in `app_version.py`.

## Portable builds

Run `python packaging/build_portable.py` with the application dependencies and
PyInstaller installed. The output is one file:
`dist/HDU-InvoiceAllInOne-v<VERSION>-Portable.exe`.
It includes Python, UI resources and OCR models. Users download it and double-click;
no installer or adjacent dependency folders are needed. PyInstaller expands its
runtime into a temporary folder at launch, which can take a few seconds.

Run `python packaging/verify_portable.py` to exercise the executable in isolation,
including UI resources, persistent settings, data migration, PDF parsing and OCR.
Personal settings, invoice files and screenshots are never bundled.

## Local data

Packaged builds initially save preferences to
`%LOCALAPPDATA%\HDU-InvoiceAllInOne\settings.json`.
The settings page can open this folder or choose a different location. Relocation
copies the current preferences, refuses to overwrite different existing settings,
and keeps the original as a backup. A small pointer in the default data folder
remembers the chosen location across launches and application updates.
Invoice source files and exported workspaces use their independently chosen paths.
Source checkouts initially use project-local `settings.json`; their custom-location
pointer is ignored by Git. Legacy settings beside an executable are read as a
migration fallback.

## Updates

The updater reads the latest non-draft, non-prerelease GitHub Release. Tags use
three numeric version parts. It accepts only an asset ending in `-Portable.exe`
from the configured repository with a GitHub SHA-256 digest. Downloaded bytes
must match both the published size and digest before execution.

Users save their workspace, then choose one-click update. A separate instance of
the downloaded executable waits for the current executable to exit, atomically
replaces it at its existing path, and restarts it. The executable may have been
renamed by the user. Before replacement, the old executable is copied into the
local data folder under `updates/update-*/previous.exe`; preferences are preserved.
If the new process cannot be launched, replacement is rolled back. A result report
is kept alongside the backup. Updating requires write access to the executable's
folder. Source checkouts download the portable executable and open its folder
instead of replacing their Python sources.
