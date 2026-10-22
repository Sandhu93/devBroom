# Testing DevBroom

DevBroom is a destructive filesystem utility, so a passing unit suite is only
one part of release confidence. The checks below cover logic, the Tk startup
path, supported runtimes, and the built command-line package.

## Run locally

Run the deterministic test suite with Python 3.10 or newer:

```bash
python -m unittest discover -s tests -v
```

Run the branch coverage gate:

```bash
python -m pip install -e ".[test]"
python -m coverage run -m unittest discover -s tests
python -m coverage report --fail-under=80
```

On a headless Linux machine, run the suite with a virtual display so the Tk
window smoke test can execute:

```bash
xvfb-run -a python -m coverage run -m unittest discover -s tests
```

On Windows, install the package in editable mode and run the end-to-end CLI
smoke test. It creates a uniquely named disposable project under your temp
folder, confirms `--dry-run` leaves both targets in place, then deletes only
those generated targets:

```text
python -m pip install -e .
python scripts/smoke_test.py
```

To keep the disposable project for a GUI pass, run:

```powershell
python scripts/smoke_test.py --keep-fixture
```

Copy the printed fixture path into DevBroom's root field, scan it, check both
rows, open the delete review, cancel once and confirm the folders still exist.
Repeat and confirm permanent deletion, then remove the printed fixture folder
from the temp directory.

The coverage threshold applies to scanner, cleanup, CLI, settings, and startup
logic. `devbroom/ui.py` is excluded from line coverage because widget line
counts are a poor measure of usability and layout correctness. CI runs a Tk
startup smoke test; a release still needs a short manual review of the GUI on
Windows and Linux.

Unreadable paths are covered with simulated permission errors. The scanner
reports an incomplete scan, marks affected size estimates as lower bounds,
shows their age as unknown, and keeps those targets visible when an age filter
is active. Real permission behavior still depends on the account and filesystem.

## CI and release checks

Pull request CI runs the unit and GUI smoke tests on Windows and Ubuntu using
Python 3.10 through 3.13. It enforces the branch coverage threshold. The PyPI
release workflow repeats the checks, builds the wheel and source distribution,
validates their metadata with Twine, then installs the same wheel in clean Linux
and Windows environments and exercises the installed CLI against disposable
projects.

For a corporate repository, configure branch protection to require the stable
`Python Tests / required` check before merging; it fails unless every matrix
combination passes. Protect the `pypi` GitHub
environment and restrict which tags or branches can publish; the workflow uses
PyPI Trusted Publishing, so it does not need a long-lived upload token.

## What these checks do not prove

- The scanner is not tested against a developer's real home directory or drive.
- Filesystem permissions, antivirus locks, network shares, and very large trees
  vary by machine and need targeted checks when changing deletion or traversal
  behavior. Windows junctions and reparse points are covered by a local
  Windows smoke check and scanner/deletion regression tests; CI coverage may
  still differ by Python and filesystem version.
- The UI smoke test proves that the window can be created and populated. It
  does not validate visual layout, keyboard accessibility, or every interaction.
  Use the GUI smoke steps above to check the actual review and cancel/confirm
  flow, then tab through controls and check the layout at the display scaling
  and window size used in your environment.
- A timestamp indicates the latest filesystem modification observed. Tests do
  not establish whether a project or environment is actually unused.

To inspect a real project tree without deleting anything, run a CLI dry-run
against a path you choose, for example:

```powershell
devbroom --cli --path "$env:USERPROFILE\source" --dry-run --no-settings-ignores
```

Check the paths in the output before considering a delete run. Keep
`--dry-run`; do not add `--delete` for this read-only inspection.

This is an operator review of the scan on that machine, not a test against a
known-good inventory of the home directory. Start with a narrow source folder;
do not point a first inspection at the entire drive. For permission, antivirus,
or network-share behavior, use a disposable fixture on the same type of volume
and run as the same account that will use DevBroom. Record inaccessible paths
and compare scan results before and after. Do not try to simulate deletion of
an in-use production dependency folder.

For large-tree checks, generate a disposable tree with many small project
folders and expected targets, run a dry-run, and compare the reported paths and
completion time with a baseline for that machine. Keep timing observations out
of the unit suite because storage and antivirus differences make fixed timing
assertions unreliable.

Age is based on the newest observed modification time in a target tree. It is
not evidence that the project is unused: opening, running, or otherwise using
a project may not update files in the target, and background tools may update
files without a person using it. Inspect project context and keep important
paths ignored; do not use age alone as authorization to delete.

For destructive changes, use disposable directories and inspect the exact
target paths before confirming deletion. Never use a developer's real project
tree as a test fixture.
