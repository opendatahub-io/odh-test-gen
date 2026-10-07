"""Host-side boundaries for the Fullsend test-planner agent."""

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from scripts.fullsend_harness import HarnessError, copy_back, emit_result, prepare_plugin, validate_result


def test_harness_local_resources_are_present():
    root = Path(__file__).resolve().parents[2] / ".fullsend"
    harness = yaml.safe_load((root / "rhai-test-plan" / "rhai-test-plan.yaml").read_text())
    resources = [
        harness["agent"],
        harness["pre_script"],
        harness["post_script"],
        harness["validation_loop"]["script"],
        harness["validation_loop"]["schema"],
        harness["host_files"][0]["src"],
        harness["openshell"]["profiles"][0],
        harness["openshell"]["profiles"][1],
        harness["providers"][0],
        harness["providers"][1],
    ]
    assert all((root / path).is_file() for path in resources)


def test_python_package_profile_is_attached_to_sandbox():
    root = Path(__file__).resolve().parents[2] / ".fullsend"
    harness = yaml.safe_load((root / "rhai-test-plan" / "rhai-test-plan.yaml").read_text())
    provider = yaml.safe_load((root / harness["providers"][1]).read_text())
    profile = yaml.safe_load((root / harness["openshell"]["profiles"][1]).read_text())

    assert provider["type"] == profile["id"]
    assert {endpoint["host"] for endpoint in profile["endpoints"]} == {
        "pypi.org",
        "files.pythonhosted.org",
    }
    assert {binary["path"] for binary in profile["binaries"]} == {"**/uv"}


def test_claude_agent_name_matches_fullsend_registration():
    root = Path(__file__).resolve().parents[2] / ".fullsend"
    harness = yaml.safe_load((root / "rhai-test-plan" / "rhai-test-plan.yaml").read_text())
    prompt = (root / harness["agent"]).read_text()
    assert prompt.startswith("---\n")
    frontmatter = yaml.safe_load(prompt.split("---\n", 2)[1])
    assert frontmatter["name"] == "rhai-test-plan"
    assert frontmatter["description"]


def _manifest(feature):
    return {
        str(path.relative_to(feature)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in feature.rglob("*")
        if path.is_file()
    }


def _create_result(tmp_path, task="create", score=8, verdict="Ready"):
    repo = tmp_path / "iteration"
    feature = repo / "test-plans" / "RHAISTRAT" / "run" / "feature"
    feature.mkdir(parents=True)
    (feature / "TestPlan.md").write_text(
        "---\nfeature: feature\nsource_key: RHAISTRAT-123\nversion: 1.0.0\n"
        "status: Draft\nlast_updated: 2026-10-06\nauthor: AI-assisted\n---\nplan\n"
    )
    (feature / "TestPlanGaps.md").write_text(
        "---\nfeature: feature\nsource_key: RHAISTRAT-123\nstatus: Open\n"
        "gap_count: 0\nlast_updated: 2026-10-06\n---\ngaps\n"
    )
    (feature / "README.md").write_text("readme\n")
    (feature / ".source-strategy.md").write_text("source\n")
    (feature / ".test-plan-output-dir.json").write_text(
        '{"output_dir": "/sandbox/workspace/workspace/test-plans/RHAISTRAT/run"}\n'
    )
    (feature / "TestPlanReview.md").write_text(
        "---\nfeature: feature\nsource_key: RHAISTRAT-123\nverdict: Ready\nscore: 8\n"
        "pass: true\nauto_revised: false\nlast_updated: 2026-10-06\n"
        "scores: {specificity: 2, grounding: 1, scope_fidelity: 1, actionability: 2, consistency: 2}\n"
        "---\nreview\n"
    )
    if task == "create-cases":
        cases = feature / "test_cases"
        cases.mkdir()
        (cases / "INDEX.md").write_text("index\n")
        (cases / "TC-E2E-001.md").write_text(
            "---\ntest_case_id: TC-E2E-001\nsource_key: RHAISTRAT-123\n"
            "objectives: [1]\npriority: P1\nstatus: Draft\n"
            "last_updated: 2026-10-06\n---\ncase\n"
        )
    result = tmp_path / "agent-result.json"
    result.write_text(
        json.dumps(
            {
                "action": "completed",
                "task": task,
                "strategy_issue": "RHAISTRAT-123",
                "feature_dir": "test-plans/RHAISTRAT/run/feature",
                "verdict": verdict,
                "score": score,
                "errors": [],
                "manifest": _manifest(feature),
            }
        )
    )
    return repo, feature, result


def test_prepare_plugin_keeps_skill_scripts_together_without_symlinks(tmp_path):
    source = Path(__file__).resolve().parents[2]
    destination = tmp_path / "plugin"

    prepare_plugin(source, destination)

    assert (destination / ".claude-plugin" / "plugin.json").is_file()
    assert (destination / "skills" / "test-plan-create" / "SKILL.md").is_file()
    assert (destination / "skills" / "test-plan-create-cases" / "SKILL.md").is_file()
    assert (destination / "scripts" / "bootstrap.sh").is_file()
    assert not any(path.is_symlink() for path in destination.rglob("*"))
    assert not (destination / "tests").exists()


def test_completed_create_requires_artifacts_inside_requested_run(tmp_path):
    repo, feature, result = _create_result(tmp_path)

    assert validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run") == feature


def test_emit_result_uses_noncredential_receipt_field(tmp_path):
    repo, feature, result = _create_result(tmp_path)
    result.unlink()

    emit_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run", str(feature.relative_to(repo)))

    receipt = json.loads(result.read_text())
    assert receipt["strategy_issue"] == "RHAISTRAT-123"
    assert "source_key" not in receipt
    schema = json.loads(
        (Path(__file__).resolve().parents[2] / ".fullsend/rhai-test-plan/result.schema.json").read_text()
    )
    assert "strategy_issue" in schema["required"]
    assert "source_key" not in schema["properties"]
    assert validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run") == feature


def test_result_rejects_receipt_with_redacted_strategy_issue(tmp_path):
    repo, _, result = _create_result(tmp_path)
    receipt = json.loads(result.read_text())
    receipt["strategy_issue"] = "RHAI..."
    result.write_text(json.dumps(receipt))

    with pytest.raises(HarnessError, match="wrong task or strategy"):
        validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")


@pytest.mark.parametrize("bad_path", ["../outside", "/tmp/outside", "test-plans/RHAISTRAT/other/feature"])
def test_result_rejects_escape_or_wrong_run(tmp_path, bad_path):
    repo = tmp_path / "iteration"
    repo.mkdir()
    result = tmp_path / "agent-result.json"
    result.write_text(
        json.dumps(
            {
                "action": "completed",
                "task": "create",
                "strategy_issue": "RHAISTRAT-123",
                "feature_dir": bad_path,
                "verdict": "Ready",
                "score": 8,
                "errors": [],
            }
        )
    )

    with pytest.raises(HarnessError):
        validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")


def test_result_rejects_symlinked_artifact(tmp_path):
    repo = tmp_path / "iteration"
    feature = repo / "test-plans" / "RHAISTRAT" / "run" / "feature"
    feature.mkdir(parents=True)
    (feature / "TestPlan.md").symlink_to(tmp_path / "outside")
    result = tmp_path / "agent-result.json"
    result.write_text(
        json.dumps(
            {
                "action": "completed",
                "task": "create",
                "strategy_issue": "RHAISTRAT-123",
                "feature_dir": "test-plans/RHAISTRAT/run/feature",
                "verdict": "Ready",
                "score": 8,
                "errors": [],
            }
        )
    )

    with pytest.raises(HarnessError):
        validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")


def test_result_rejects_tampered_manifest(tmp_path):
    repo, feature, result = _create_result(tmp_path)
    (feature / "TestPlan.md").write_text("changed after result\n")
    with pytest.raises(HarnessError, match="manifest"):
        validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")


def test_cases_copy_back_replaces_only_validated_feature(tmp_path):
    repo, feature, result = _create_result(tmp_path, task="create-cases")
    target = tmp_path / "host"
    target.mkdir()
    previous = target / feature.relative_to(repo)
    previous.mkdir(parents=True)
    (previous / "old.txt").write_text("old\n")

    copied = copy_back(result, repo, target, "create-cases", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")

    assert copied == previous
    assert (copied / "test_cases" / "TC-E2E-001.md").is_file()
    assert not (copied / "old.txt").exists()


def test_create_refuses_to_replace_existing_feature(tmp_path):
    repo, feature, result = _create_result(tmp_path)
    target = tmp_path / "host"
    previous = target / feature.relative_to(repo)
    previous.mkdir(parents=True)
    (previous / "keep.txt").write_text("keep\n")

    with pytest.raises(HarnessError, match="overwrite"):
        copy_back(result, repo, target, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")
    assert (previous / "keep.txt").is_file()


def test_result_rejects_wrong_rubric_even_with_ready_verdict(tmp_path):
    repo, feature, result = _create_result(tmp_path)
    review = feature / "TestPlanReview.md"
    review.write_text(review.read_text().replace("actionability: 2", "actionability: 1"))
    data = json.loads(result.read_text())
    data["manifest"] = _manifest(feature)
    result.write_text(json.dumps(data))

    with pytest.raises(HarnessError, match="TestPlanReview.md"):
        validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")


def test_result_rejects_malformed_plan_frontmatter(tmp_path):
    repo, feature, result = _create_result(tmp_path)
    (feature / "TestPlan.md").write_text("no frontmatter\n")
    data = json.loads(result.read_text())
    data["manifest"] = _manifest(feature)
    result.write_text(json.dumps(data))

    with pytest.raises(HarnessError, match="TestPlan.md"):
        validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")


def test_cases_reject_non_ready_review(tmp_path):
    repo, feature, result = _create_result(tmp_path, task="create-cases")
    review = feature / "TestPlanReview.md"
    review.write_text(
        review.read_text()
        .replace("verdict: Ready", "verdict: Revise")
        .replace("score: 8", "score: 7")
        .replace("actionability: 2", "actionability: 1")
    )
    data = json.loads(result.read_text())
    data["verdict"] = "Revise"
    data["score"] = 7
    data["manifest"] = _manifest(feature)
    result.write_text(json.dumps(data))

    with pytest.raises(HarnessError, match="Ready"):
        validate_result(result, repo, "create-cases", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")


def test_result_rejects_marker_for_different_run(tmp_path):
    repo, feature, result = _create_result(tmp_path)
    marker = feature / ".test-plan-output-dir.json"
    marker.write_text('{"output_dir": "/sandbox/workspace/workspace/test-plans/RHAISTRAT/other"}')
    data = json.loads(result.read_text())
    data["manifest"] = _manifest(feature)
    result.write_text(json.dumps(data))

    with pytest.raises(HarnessError, match="marker"):
        validate_result(result, repo, "create", "RHAISTRAT-123", "test-plans/RHAISTRAT/run")
