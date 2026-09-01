"""Regression contracts for Actionability 2/2 documentation guidance."""

import re

import pytest

from tests.constants import REPO_ROOT


_CANONICAL_TBD_RESOLUTION = (
    "TBD — Resolution: {concrete action} from/with/by/before/after/using {named source or timing}"
)

_ACTIONABILITY_GUIDANCE = (
    (
        REPO_ROOT / "skills" / "test-plan-review" / "SKILL.md",
        'Leave TBD as plain "TBD"',
    ),
    (
        REPO_ROOT / "skills" / "test-plan-review" / "calibration" / "core" / "03-amd-mi350p-model-serving.md",
        "TBD-with-reason",
    ),
    (
        REPO_ROOT / "docs" / "human-review-guide.md",
        "marked TBD with rationale",
    ),
)

CREATE_SKILL_PATH = REPO_ROOT / "skills" / "test-plan-create" / "SKILL.md"
_OPTION_1_MARKER = "**If option 1:**"
_OPTION_2_MARKER = "**If option 2:**"
_LABEL_STAMPING_START = "### Step 4.5: Stamp rubric verdict label"
_LABEL_STAMPING_END = "### What this skill does NOT do"
_CREATE_SKILL_MAX_LINES = 450


class TestActionabilityDocumentationContract:
    @pytest.mark.parametrize("path, disallowed_guidance", _ACTIONABILITY_GUIDANCE)
    def test_actionability_two_guidance_requires_canonical_tbd_resolution(self, path, disallowed_guidance):
        guidance = path.read_text()

        assert "actionability == 2" in guidance
        assert _CANONICAL_TBD_RESOLUTION in guidance
        assert disallowed_guidance not in guidance


class TestActionabilityRecomputationContract:
    def test_create_resolution_rerun_recomputes_actionability_after_testplan_edit(self):
        instructions = CREATE_SKILL_PATH.read_text()

        assert instructions.count(_OPTION_1_MARKER) == 1
        assert instructions.count(_OPTION_2_MARKER) == 1
        assert instructions.index(_OPTION_1_MARKER) < instructions.index(_OPTION_2_MARKER)

        resolution_block = instructions.split(_OPTION_1_MARKER, maxsplit=1)[1].split(_OPTION_2_MARKER, maxsplit=1)[0]
        normalized = " ".join(resolution_block.split())

        plan_edit_index = normalized.casefold().find("update the test plan")
        recompute_index = normalized.find("scripts/build_citation_inputs.py")

        assert plan_edit_index >= 0
        assert recompute_index > plan_edit_index
        assert "actionability_result" in normalized[recompute_index:]


class TestCreateSkillLabelStampingContract:
    def test_label_stamping_reads_all_frontmatter_inputs_before_using_them(self):
        instructions = CREATE_SKILL_PATH.read_text()

        assert len(instructions.splitlines()) <= _CREATE_SKILL_MAX_LINES
        assert "### Step 3.6: Stamp Jira label — test plan created" in instructions
        assert "test-plan-auto-created" in instructions

        label_section = instructions.split(_LABEL_STAMPING_START, maxsplit=1)[1].split(_LABEL_STAMPING_END, maxsplit=1)[
            0
        ]
        normalized = " ".join(label_section.split())

        read_positions = {}
        for variable, artifact, field in (
            ("source_key", "TestPlan.md", "source_key"),
            ("verdict", "TestPlanReview.md", "verdict"),
            ("auto_revised", "TestPlanReview.md", "auto_revised"),
        ):
            read = re.search(
                rf"{variable}=\$\(.*?frontmatter\.py read .*?{artifact} {field}\)",
                normalized,
            )
            assert read is not None, f"Step 4.5 must read {field} into ${variable}"
            read_positions[variable] = read.start()

        first_label_use = normalized.index('if [ "$auto_revised" = "true" ]; then')
        assert all(position < first_label_use for position in read_positions.values())
        assert 'uv run python scripts/add_jira_labels.py "$source_key" --verdict "$verdict"' in normalized

        for marker in (
            "test-plan-rubric-pass",
            "test-plan-rubric-revise",
            "test-plan-rubric-fail",
            "test-plan-auto-revised",
            "Label stamping is **non-blocking**",
        ):
            assert marker in label_section
