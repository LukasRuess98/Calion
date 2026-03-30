#!/usr/bin/env python3
"""Migrate output directories to the new canonical layout.

Old paths                        New canonical paths
-------------------------------- --------------------------
exports/                      -> outputs/runs/
results/                      -> outputs/runs/
notebooks/saved_workflows/    -> outputs/workflows/
saved_workflows/              -> outputs/workflows/

Usage
-----
  # Preview what would be moved (no changes)
  python scripts/migrate_outputs.py --dry-run

  # Move files (default)
  python scripts/migrate_outputs.py

  # Copy instead of move
  python scripts/migrate_outputs.py --copy
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

MAPPINGS = [
    ("exports",                    "outputs/runs"),
    ("results",                    "outputs/runs"),
    ("notebooks/saved_workflows",  "outputs/workflows"),
    ("saved_workflows",            "outputs/workflows"),
]


def migrate(dry_run: bool, copy: bool) -> int:
    """Run the migration. Returns exit code (0 = ok, 1 = errors)."""
    root = Path.cwd()
    # Verify we are in the project root
    if not (root / "calion").is_dir():
        print("ERROR: Run this script from the project root (directory containing calion/).")
        return 1

    action = "copy" if copy else "move"
    verb = "Would " + action if dry_run else action.capitalize()
    found_any = False
    errors = 0

    for src_rel, dst_rel in MAPPINGS:
        src = root / src_rel
        if not src.exists():
            continue

        dst = root / dst_rel
        found_any = True
        print(f"\n{verb}: {src_rel}/ -> {dst_rel}/")

        if dry_run:
            _preview(src, dst)
            continue

        # Create destination directory
        dst.mkdir(parents=True, exist_ok=True)

        for item in src.iterdir():
            target = dst / item.name
            if target.exists():
                print(f"  SKIP (already exists): {item.name}")
                continue
            try:
                if copy:
                    if item.is_dir():
                        shutil.copytree(item, target)
                    else:
                        shutil.copy2(item, target)
                else:
                    shutil.move(str(item), str(target))
                print(f"  OK: {item.name}")
            except Exception as exc:
                print(f"  ERROR: {item.name}: {exc}")
                errors += 1

        # Remove now-empty source dir (move mode only)
        if not copy:
            try:
                remaining = list(src.iterdir())
                if not remaining:
                    src.rmdir()
                    print(f"  Removed empty directory: {src_rel}/")
                else:
                    print(f"  WARNING: {src_rel}/ not empty after move ({len(remaining)} items remain)")
            except Exception as exc:
                print(f"  WARNING: Could not remove {src_rel}/: {exc}")

    if not found_any:
        print("Nothing to migrate — no legacy output directories found.")
    elif not dry_run and not errors:
        print("\nMigration complete.")
        print("You can now update any hardcoded paths in your notebooks to use:")
        print("  outputs/runs/       (was: exports/, results/)")
        print("  outputs/workflows/  (was: notebooks/saved_workflows/, saved_workflows/)")

    return 1 if errors else 0


def _preview(src: Path, dst: Path) -> None:
    for item in src.iterdir():
        target = dst / item.name
        status = " [already exists]" if target.exists() else ""
        print(f"  {item.name}{status}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate legacy output directories to outputs/{runs,workflows}/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--copy", action="store_true", help="Copy files instead of moving them")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN — no files will be changed\n")

    sys.exit(migrate(dry_run=args.dry_run, copy=args.copy))


if __name__ == "__main__":
    main()
