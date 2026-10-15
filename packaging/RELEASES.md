# Windows releases

The current version is defined in `app_version.py`. Settings and the help page
read the same value. The settings page accepts a public GitHub repository URL.
Public releases can be checked without asking end users to sign in.

After this project is connected to GitHub, push a tag such as `v1.0.1` to run
`.github/workflows/release.yml`. The workflow tests the code, builds the Windows
application and installer, then uploads the installer to that tag's Release.
The packaged application receives its version and GitHub repository automatically.
The workflow can also be run manually for the version in `app_version.py`.

The updater uses the latest non-draft, non-prerelease GitHub Release. Version tags
must use three numeric parts. An update is offered only if the release has a
Windows `.msi` or `Setup`/`Installer` `.exe` asset with a GitHub SHA-256 digest.
Downloads are streamed to a temporary folder and checked against the asset size
and digest before the installer can be launched. An update without a suitable
installer still offers a link to its release notes.

Users save their workspace first, then click “一键更新”. The installer is downloaded
and launched; normal installer prompts complete the upgrade. The app does not
silently overwrite source files or discard an unsaved workspace. Source-code
checkouts continue to use their existing Python environment; the installer creates
or upgrades the installed Windows application.

The generated installer has a fixed application ID and installs for the current
Windows user. It does not package local `settings.json`, invoice files or screenshots.
