# Contributing

Thanks for taking an interest in DevBroom.

The project is intentionally small, so contributions should aim to keep the application practical, readable, and easy to maintain.

## Before You Start

- Check existing issues or open a new one before doing larger work.
- Keep changes focused. Small, isolated improvements are easier to review and merge.
- Avoid overengineering. The project values clarity and practical behavior over adding framework-heavy abstractions.

## Local Setup

Run the application:

```bash
python main.py
```

Run the CLI mode:

```bash
python main.py --cli --path .
```

Run tests:

```bash
python -m unittest discover -s tests
```

## Contribution Guidelines

- Prefer changes that improve correctness, cross-platform behavior, or usability.
- Keep UI changes consistent with the app's minimal design direction.
- Reuse existing scanner, settings, and report helpers instead of duplicating behavior.
- Add or update tests for non-trivial logic changes.
- Do not commit generated files such as `__pycache__`, local settings, or local scratch artifacts.

## Pull Requests

Good pull requests usually include:

- a short explanation of the problem
- a summary of the change
- any user-visible behavior changes
- test coverage or manual verification notes
- screenshots if the GUI changed

## Areas That Are Especially Helpful

- bug fixes around filesystem scanning or deletion
- Linux and Windows edge-case handling
- test coverage improvements
- small usability improvements in GUI or CLI mode
- documentation improvements

## Areas To Be Careful With

- destructive behavior changes around deletion
- broad architectural refactors
- packaging/distribution changes before the feature set stabilizes
- adding new dependencies without a clear need
