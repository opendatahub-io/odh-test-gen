"""Test gap count validation."""

import tempfile
from pathlib import Path

from scripts.utils.frontmatter_utils import write_frontmatter
from scripts.validate_gap_counts import validate_gap_counts
from tests.constants import VALID_TEST_GAPS_DATA


def test_validate_gap_counts_valid_arithmetic():
    """Test validation passes when counts add up correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        feature_dir = Path(tmpdir)
        gaps_file = feature_dir / "TestPlanGaps.md"

        # Create TestPlanGaps.md with gap_count = 10
        data = VALID_TEST_GAPS_DATA.copy()
        data["gap_count"] = 10
        write_frontmatter(gaps_file, data, "test-gaps")

        # Test valid arithmetic: 10 - 3 + 2 = 9
        exit_code, message = validate_gap_counts(str(feature_dir), 3, 9, 2)

        assert exit_code == 0, f"Should pass validation. message: {message}"
        assert "✓ Gap counts valid" in message


def test_validate_gap_counts_mismatch():
    """Test validation fails when counts don't add up."""
    with tempfile.TemporaryDirectory() as tmpdir:
        feature_dir = Path(tmpdir)
        gaps_file = feature_dir / "TestPlanGaps.md"

        # Create TestPlanGaps.md with gap_count = 10
        data = VALID_TEST_GAPS_DATA.copy()
        data["gap_count"] = 10
        write_frontmatter(gaps_file, data, "test-gaps")

        # Test invalid: 10 - 3 + 2 = 9, but claiming 8
        exit_code, message = validate_gap_counts(str(feature_dir), 3, 8, 2)

        assert exit_code == 1, "Should fail validation"
        assert "Gap count mismatch" in message
        assert "Expected unresolved: 9" in message
        assert "Actual unresolved: 8" in message
        assert "Discrepancy: -1" in message


def test_validate_gap_counts_missing_file():
    """Test fails gracefully when TestPlanGaps.md doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exit_code, message = validate_gap_counts(tmpdir, 0, 0, 0)

        assert exit_code == 2, "Should return error code"
        assert "not found" in message
