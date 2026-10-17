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

The settings page provides two independent actions:

- Check for updates: reads the latest non-draft, non-prerelease GitHub Release
  and compares its three-part version tag with the current version. Anonymous API
  requests can be rate limited; failure does not disable the download action.
- GitHub download: immediately opens the configured repository's
  `https://github.com/<owner>/<repo>/releases/latest` page in the default browser.
  No API check, newer version, asset digest, or saved workspace is required to open
  this page. Users choose the portable executable themselves.

Save and close the application before manually replacing its executable. Preferences
remain in the configured local data directory. The UI does not download files,
replace executables, or restart the app. The legacy update-helper command remains
available for compatibility with previously released clients.
