"""
Test data constants for test-plan artifact tests.

Provides valid base data for each artifact type to use in tests.
"""

from pathlib import Path

# Repository root and common paths
REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Skill directory for testing (relative to repo root)
TEST_SKILL_DIR = str(Path.cwd() / ".claude" / "skills" / "test-plan.create")

VALID_TEST_PLAN_DATA = {
    "feature": "Test Feature",
    "source_key": "RHAISTRAT-400",
    "version": "1.0.0",
    "status": "Draft",
    "last_updated": "2026-04-14",
    "author": "QE Team",
}

VALID_TEST_CASE_DATA = {
    "test_case_id": "TC-API-001",
    "source_key": "RHAISTRAT-400",
    "priority": "P0",
    "status": "Draft",
    "last_updated": "2026-04-14",
}

VALID_TEST_GAPS_DATA = {
    "feature": "Test Feature",
    "source_key": "RHAISTRAT-400",
    "status": "Open",
    "gap_count": 3,
    "last_updated": "2026-04-14",
}
