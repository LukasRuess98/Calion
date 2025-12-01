"""Run a minimal regression check against the bundled fixtures.

This helper mirrors the CI smoke test and keeps the command referenced in the
README functional. It only executes the lightweight regression suite to avoid
requiring a full solver stack.

Quick validation that the EnerGIS framework is working correctly without
needing Import_Data.xlsx or a commercial solver.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def main() -> int:
    """Run quickstart regression test.

    This test validates:
    - Core optimization workflow (PF→RH)
    - Config loading and merging
    - Model building with synthetic fixtures
    - Result aggregation and export

    Returns:
        0 if tests pass, non-zero otherwise
    """
    print("=" * 70)
    print("🚀 EnerGIS QUICKSTART TEST")
    print("=" * 70)
    print("\n📋 Running regression suite against bundled fixtures...")
    print("   (This validates core optimization without requiring Import_Data.xlsx)\n")

    # Run with verbose output for better feedback
    result = pytest.main([
        "tests/test_regression.py",
        "-v",  # Verbose output
        "--tb=short",  # Short tracebacks
        "--color=yes",  # Colored output
    ])

    if result == 0:
        print("\n" + "=" * 70)
        print("✅ QUICKSTART TEST PASSED")
        print("=" * 70)
        print("\n🎉 Framework is working correctly!")
        print("\n📚 Next steps:")
        print("   - Check notebooks/README.md for interactive examples")
        print("   - Run full test suite: pytest tests/ -v")
        print("   - See README.md for production workflows")
        print("   - Try: jupyter notebook notebooks/synthetic_example.ipynb\n")
    else:
        print("\n" + "=" * 70)
        print("❌ QUICKSTART TEST FAILED")
        print("=" * 70)
        print("\n🔧 Troubleshooting:")
        print("   1. Install dependencies: pip install -e .")
        print("   2. Check solver availability (glpk, gurobi, or highs)")
        print("   3. Ensure Python >= 3.8")
        print("   4. Review errors above for details")
        print("   5. Check pytest installation: pip install pytest\n")

    return result


if __name__ == "__main__":
    raise SystemExit(main())
