# DevBroom

DevBroom is a small Tkinter desktop utility for finding and deleting dependency folders that commonly consume large amounts of disk space in development environments.

It currently scans for:

- `node_modules`
- Python virtual environments named `venv`, `.venv`, `env`, `.env`, or `virtualenv`

The tool is designed to run on both Windows and Linux.

## What It Does

DevBroom recursively scans a chosen directory, estimates the size of removable dependency folders, and lets you selectively delete them from a GUI.

It is intended for cleaning local development machines where projects accumulate:

- JavaScript package installs
- Python virtual environments

## Requirements

- Python 3.10+
- Tkinter available in your Python installation

### Windows

Tkinter is usually bundled with the standard Python installer from python.org.

Run with:

```powershell
python main.py
```

### Linux

Many Linux distributions do not install Tkinter by default.

Examples:

```bash
# Debian/Ubuntu
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter
```

Run with:

```bash
python3 main.py
```

## Detection Rules

### `node_modules`

- Any directory named exactly `node_modules` is treated as removable.
- The scanner does not descend into a matched `node_modules` directory.

### Python virtual environments

Candidate directory names:

- `venv`
- `.venv`
- `env`
- `.env`
- `virtualenv`

A candidate is only treated as a real virtual environment if it contains one of:

- `pyvenv.cfg`
- `Scripts/activate`
- `bin/activate`

This avoids deleting unrelated folders that merely happen to use a common venv-like name.

### Skipped parents

The scanner intentionally skips candidates found inside these parent directories:

- `site-packages`
- `Lib`
- `lib`
- `node_modules`

This reduces false positives inside package contents and nested dependency trees.

## Safety Notes

- Deletion is permanent. Files are not moved to Trash or Recycle Bin.
- Symlinked directories are ignored during scanning.
- Symlink targets are not deleted.
- Read-only files are handled during deletion where possible.
- Permission errors and locked files are reported but do not stop the entire operation.

## Interface

- Minimal desktop UI with both light mode and dark mode
- Theme toggle built into the header
- Filter controls for `node_modules` and Python virtual environments
- Selective deletion with a summary of reclaimable space

## Known Limitations

- Scans can be slow on very large home directories because folder sizes are calculated recursively.
- Locked files on Windows may still prevent complete deletion.
- Tkinter look-and-feel depends on the local platform and installed themes.
- The app is intentionally small and still does not include packaging metadata.

## Edge Cases Covered

- Permission-denied files during scan
- Read-only files during delete
- Symlinked directories and junction-like targets
- Folders removed externally while scan/delete is running
- Window close during an active scan
- Partial delete failures with accurate reclaimed-space reporting

## Running The App

1. Launch the script.
2. Choose a directory to scan.
3. Wait for results to populate.
4. Select the folders you want to remove.
5. Click `Delete Selected`.

## Project Layout

The code is split into a few small modules to keep maintenance simple:

- `devbroom/app.py`: app startup
- `devbroom/ui.py`: Tkinter UI and interaction flow
- `devbroom/scanner.py`: target discovery and size calculation
- `devbroom/cleanup.py`: safe deletion helpers
- `devbroom/models.py`: shared constants and `ScanTarget`
- `main.py`: thin launcher

## Tests

The project includes a small unit test suite for non-UI logic:

```bash
python -m unittest discover -s tests
```

Covered areas:

- target detection
- virtualenv validation
- nested-folder skip behavior
- safe delete behavior

## Suggested Next Steps

If this tool grows beyond a single script, the next practical production steps would be:

- expand unit tests around scanner and delete safeguards
- add a CLI mode for headless cleanup
- package it with a proper project layout and dependency metadata
