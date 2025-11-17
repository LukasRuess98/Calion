"""Run a minimal regression check against the bundled fixtures.

This helper mirrors the CI smoke test and keeps the command referenced in the
README functional.  It only executes the lightweight regression suite to avoid
requiring a full solver stack.
"""
from __future__ import annotations

import sys

import pytest


def main() -> int:
    return pytest.main(["tests/test_regression.py", "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
