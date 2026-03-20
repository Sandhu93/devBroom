"""Thin entry point for running DevBroom as a script."""

import sys

from devbroom.app import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
