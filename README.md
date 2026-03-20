# DevBroom

DevBroom is a small cross-platform desktop utility for reclaiming disk space from development dependencies.

It scans a directory, finds removable dependency folders such as `node_modules` and Python virtual environments, shows their estimated size, and lets you delete selected entries from a Tkinter GUI.

## Features

- Scan a chosen directory recursively
- Detect `node_modules`
- Detect Python virtual environments such as `venv`, `.venv`, `env`, `.env`, and `virtualenv`
- Show estimated folder sizes before deletion
- Selectively delete only the folders you choose
- Light mode and dark mode UI
- Works on Windows and Linux

## Requirements

- Python 3.10+
- Tkinter available in your Python installation

### Windows

Tkinter is usually included with the standard Python installer from python.org.

Run:

```powershell
python main.py
```

### Linux

Some Linux distributions do not include Tkinter by default.

Examples:

```bash
# Debian / Ubuntu
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter
```

Run:

```bash
python3 main.py
```

## How It Works

DevBroom scans for these targets:

- `node_modules`
- `venv`
- `.venv`
- `env`
- `.env`
- `virtualenv`

Virtual environment candidates are only treated as real Python environments if they contain one of:

- `pyvenv.cfg`
- `Scripts/activate`
- `bin/activate`

This prevents deleting unrelated folders that only happen to use a common virtualenv-like name.

The scanner also skips likely nested package locations such as:

- `site-packages`
- `Lib`
- `lib`
- `node_modules`

That reduces false positives inside installed dependencies.

## Safety Notes

- Deletion is permanent. Items are not moved to Trash or Recycle Bin.
- Symlinked directories are skipped during scanning.
- Symlink targets are not deleted.
- Read-only files are handled during deletion where possible.
- Permission errors and locked files are reported without aborting the entire operation.

## Interface

- Minimal card-based desktop UI
- Light and dark theme toggle in the header
- Folder-type filters for `node_modules` and Python virtual environments
- Scan progress and result summary
- Select-all, clear, and selective delete actions

## Running The App

1. Start the application with `python main.py` or `python3 main.py`.
2. Choose the root directory you want to scan.
3. Wait for the scan to populate results.
4. Select the folders you want to remove.
5. Click `Delete Selected`.

## CLI Mode

DevBroom also supports a headless CLI mode for remote sessions and Linux servers.

Basic scan:

```bash
python3 main.py --cli --path /path/to/projects
```

Skip saved ignore paths for one run:

```bash
python3 main.py --cli --path /path/to/projects --no-settings-ignores
```

Export results to JSON:

```bash
python3 main.py --cli --path /path/to/projects --json-out scan-report.json
```

CLI output includes:

- matching folders
- estimated sizes
- total reclaimable size
- optional JSON export

## Tests

The project includes lightweight unit tests for the non-UI logic.

Run the full suite:

```bash
python -m unittest discover -s tests
```

You can also run each file directly:

```bash
python tests/test_scanner.py
python tests/test_cleanup.py
```

Covered areas:

- target detection
- virtualenv validation
- nested-folder skip behavior
- safe delete behavior
- settings persistence
- CLI scan and JSON export behavior

## Project Layout

- `main.py`: thin application launcher
- `devbroom/app.py`: app startup
- `devbroom/cli.py`: headless CLI scan/report mode
- `devbroom/ui.py`: Tkinter UI and theme handling
- `devbroom/scanner.py`: target discovery and size calculation
- `devbroom/cleanup.py`: delete helpers and filesystem cleanup
- `devbroom/models.py`: shared constants and `ScanTarget`
- `devbroom/settings.py`: saved preferences and ignored paths
- `tests/test_scanner.py`: scanner tests
- `tests/test_cleanup.py`: cleanup tests
- `tests/test_settings.py`: settings tests
- `tests/test_cli.py`: CLI tests

## Known Limitations

- Scans can be slow on very large directories because folder sizes are calculated recursively.
- Locked files on Windows may still prevent complete deletion.
- Tkinter styling can vary across platforms and desktop environments.
- CLI mode currently scans and reports only; it does not delete folders yet.

## Good Next Modifications

If you want to improve this app without overengineering it, these are the best next changes:

- Add an option to sort by largest folders first immediately after scan completion.
- Add a confirmation detail panel that lists exactly what will be deleted before removal.
- Add a non-destructive preview mode that exports results to text or JSON.
- Add a few more tests around Windows read-only files and scan interruption behavior.
- Add delete support to CLI mode with an explicit `--delete` confirmation flag.

## What I Would Not Add Yet

These would increase complexity faster than they improve this project:

- a database
- background worker processes
- plugin architecture
- packaging into an installer before the feature set stabilizes
- UI automation tests for Tkinter unless the UI becomes much more complex
