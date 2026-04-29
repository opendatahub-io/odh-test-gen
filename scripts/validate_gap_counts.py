#!/usr/bin/env python3
"""Validate gap count arithmetic after resolve-gaps runs.

Usage:
    uv run python scripts/validate_gap_counts.py <feature_dir> <resolved> <unresolved> <new>

Validates:
    unresolved == original - resolved + new

Exit codes:
    0 - Valid
    1 - Mismatch
    2 - Error
"""

import argparse
import sys
from pathlib import Path

from scripts.utils.frontmatter_utils import read_frontmatter_validated


def validate_gap_counts(feature_dir, resolved, unresolved, new):
    """Validate gap count arithmetic.

    Args:
        feature_dir: Path to feature directory
        resolved: Number of gaps resolved
        unresolved: Number of gaps still unresolved
        new: Number of new gaps identified

    Returns:
        (exit_code, message): 0 if valid, 1 if mismatch, 2 if error
    """
    gaps_file = Path(feature_dir) / "TestPlanGaps.md"
    if not gaps_file.exists():
        return 2, f"ERROR: {gaps_file} not found"

    try:
        frontmatter, _ = read_frontmatter_validated(str(gaps_file), "test-gaps")
        original = frontmatter.get("gap_count", 0)
    except Exception as e:
        return 2, f"ERROR: Failed to read gap count: {e}"

    # Validate: unresolved = original - resolved + new
    expected = original - resolved + new

    if unresolved == expected:
        msg = (f"✓ Gap counts valid:\n"
               f"  Original: {original}\n"
               f"  Resolved: {resolved}\n"
               f"  New: {new}\n"
               f"  Unresolved: {unresolved} (expected: {expected})")
        return 0, msg
    else:
        msg = (f"❌ Gap count mismatch!\n"
               f"  Original: {original}\n"
               f"  Resolved: {resolved}\n"
               f"  New: {new}\n"
               f"  Expected unresolved: {expected}\n"
               f"  Actual unresolved: {unresolved}\n"
               f"  Discrepancy: {unresolved - expected}")
        return 1, msg


def main():
    parser = argparse.ArgumentParser(description="Validate gap count arithmetic")
    parser.add_argument("feature_dir", help="Path to feature directory")
    parser.add_argument("resolved", type=int, help="Gaps resolved")
    parser.add_argument("unresolved", type=int, help="Gaps still unresolved")
    parser.add_argument("new", type=int, help="New gaps identified")
    args = parser.parse_args()

    exit_code, message = validate_gap_counts(
        args.feature_dir, args.resolved, args.unresolved, args.new
    )

    if exit_code == 0:
        print(message)
    else:
        print(message, file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
