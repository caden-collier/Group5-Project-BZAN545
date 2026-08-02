"""Compatibility entry point; prefer the installed ``bzan545`` command."""

from bzan545.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
