"""Shared low-level helpers for the energis.io package."""

from __future__ import annotations

import math
from typing import Any


def _is_empty(value: Any) -> bool:
    """Return True if *value* is None, NaN, or an empty/whitespace string."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False
