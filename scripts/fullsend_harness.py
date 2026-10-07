"""Trusted host helpers for the Fullsend test-planner harness.

The agent may write a result and a repository checkout. This module treats both
as untrusted data; it never executes a file from the returned checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath

import yaml

from scripts.utils.schemas import compute_verdict_and_pass
from scripts.utils.schemas import validate as validate_frontmatter

KEY_PATTERN = re.compile(r"^(?:RHAISTRAT|RHOAIENG)-[0-9]+$")
TASKS = {"create", "create-cases"}
REQUIRED_PLAN_FILES = (
    "TestPlan.md",
    "TestPlanGaps.md",
    "TestPlanReview.md",
    "README.md",
    ".source-strategy.md",
    ".test-plan-output-dir.json",
)


class HarnessError(ValueError):
    """An input or agent result cannot safely be accepted."""


def _relative_path(value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise HarnessError("path must be a nonempty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")) or "\\" in value:
        raise HarnessError("path must be relative and contain no traversal")
    return Path(*path.parts)


def validate_input(task: str, key: str, run_dir: str, feature_dir: str = "") -> None:
    if task not in TASKS:
        raise HarnessError("task must be create or create-cases")
    if not KEY_PATTERN.fullmatch(key):
        raise HarnessError("invalid Jira strategy key")
    run_path = _relative_path(run_dir)
    if len(run_path.parts) < 2:
        raise HarnessError("run directory must be nested in the target repository")
    if task == "create-cases":
        feature_path = _relative_path(feature_dir)
        if feature_path.parent != run_path:
            raise HarnessError("case source must be one direct child of the run directory")


def prepare_plugin(source: Path, destination: Path) -> None:
    """Make the existing Claude plugin a symlink-free Fullsend resource."""
    source = source.resolve(strict=True)
    destination = destination.absolute()
    if destination == source or destination in source.parents:
        raise HarnessError("plugin destination overlaps source")
    if destination.is_symlink():
        raise HarnessError("plugin destination may not be a symlink")
    if destination.exists():
        if not (destination / ".claude-plugin" / "plugin.json").is_file():
            raise HarnessError("refusing to replace an unrecognized plugin directory")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for directory in (".claude-plugin", "skills", "scripts"):
        subtree = source / directory
        if not subtree.is_dir() or any(path.is_symlink() for path in subtree.rglob("*")):
            raise HarnessError(f"plugin source {directory} is missing or contains symlinks")
        shutil.copytree(subtree, destination / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(source / "pyproject.toml", destination / "pyproject.toml")
    if (source / "uv.lock").is_file():
        shutil.copy2(source / "uv.lock", destination / "uv.lock")


def _frontmatter(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            raise HarnessError(f"{path.name} frontmatter is missing")
        header = content.split("\n---", 1)[0][4:]
        data = yaml.safe_load(header)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise HarnessError(f"{path.name} frontmatter cannot be read") from exc
    if not isinstance(data, dict):
        raise HarnessError(f"{path.name} frontmatter must be a mapping")
    return data


def _validated_frontmatter(path: Path, schema_type: str, key: str) -> dict:
    data = _frontmatter(path)
    errors = validate_frontmatter(data, schema_type)
    if errors or data.get("source_key") != key:
        raise HarnessError(f"{path.name} has invalid frontmatter or source key")
    return data


def validate_result(result_file: Path, repo_dir: Path, task: str, key: str, run_dir: str) -> Path:
    """Return the accepted feature path in an agent-writable checkout."""
    try:
        result = json.loads(result_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError("agent result is missing or invalid JSON") from exc
    if not isinstance(result, dict) or result.get("action") != "completed":
        raise HarnessError("agent did not report completion")
    if result.get("task") != task or result.get("strategy_issue") != key:
        raise HarnessError("agent result identifies the wrong task or strategy")
    if result.get("errors") != []:
        raise HarnessError("agent result contains errors")
    relative = _relative_path(result.get("feature_dir"))
    validate_input(task, key, run_dir, str(relative) if task == "create-cases" else "")
    if relative.parent != _relative_path(run_dir):
        raise HarnessError("feature directory is outside the requested run")
    root = repo_dir.resolve(strict=True)
    feature = root / relative
    for path in (root, *feature.parents, feature):
        if path == root.parent:
            continue
        if path.is_symlink():
            raise HarnessError("agent output contains a symlinked path")
    if not feature.is_dir():
        raise HarnessError("feature directory is missing")
    for path in feature.rglob("*"):
        if path.is_symlink():
            raise HarnessError("agent output contains a symlink")
    for name in REQUIRED_PLAN_FILES:
        if not (feature / name).is_file():
            raise HarnessError(f"required plan artifact is missing: {name}")
    try:
        marker = json.loads((feature / ".test-plan-output-dir.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError("output directory marker is invalid") from exc
    if not isinstance(marker, dict) or not isinstance(marker.get("output_dir"), str):
        raise HarnessError("output directory marker is invalid")
    marker_path = PurePosixPath(marker["output_dir"])
    run_parts = _relative_path(run_dir).parts
    if not marker_path.is_absolute() or marker_path.parts[-len(run_parts) :] != run_parts:
        raise HarnessError("output directory marker names a different run")
    manifest = result.get("manifest")
    if not isinstance(manifest, dict):
        raise HarnessError("agent result is missing the artifact manifest")
    actual = {
        str(path.relative_to(feature)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in feature.rglob("*")
        if path.is_file()
    }
    if manifest != actual:
        raise HarnessError("artifact manifest does not match returned files")
    _validated_frontmatter(feature / "TestPlan.md", "test-plan", key)
    _validated_frontmatter(feature / "TestPlanGaps.md", "test-gaps", key)
    review = _validated_frontmatter(feature / "TestPlanReview.md", "test-plan-review", key)
    scores = review.get("scores")
    if not isinstance(scores, dict):
        raise HarnessError("review is missing criterion scores")
    try:
        verdict, score, passed = compute_verdict_and_pass(scores)
    except (KeyError, TypeError, ValueError) as exc:
        raise HarnessError("review contains invalid criterion scores") from exc
    if (review.get("source_key"), review.get("verdict"), review.get("score")) != (key, verdict, score):
        raise HarnessError("review frontmatter conflicts with its rubric or source")
    if review.get("pass") != passed:
        raise HarnessError("review pass flag conflicts with its rubric")
    if (result.get("verdict"), result.get("score")) != (verdict, score):
        raise HarnessError("agent result conflicts with the review")
    if task == "create-cases":
        if verdict != "Ready" or score < 8:
            raise HarnessError("case generation requires a Ready review with score at least 8")
        cases = feature / "test_cases"
        if not (cases / "INDEX.md").is_file() or not list(cases.glob("TC-*.md")):
            raise HarnessError("case generation did not produce an index and cases")
        for case in cases.glob("TC-*.md"):
            case_data = _validated_frontmatter(case, "test-case", key)
            if case_data.get("test_case_id") != case.stem:
                raise HarnessError(f"{case.name} has a mismatched case ID")
    return feature


def emit_result(output_file: Path, repo_dir: Path, task: str, key: str, run_dir: str, feature_dir: str) -> None:
    """Write a deterministic receipt after the existing skill has finished."""
    validate_input(task, key, run_dir, feature_dir if task == "create-cases" else "")
    relative = _relative_path(feature_dir)
    if relative.parent != _relative_path(run_dir):
        raise HarnessError("feature directory is outside the requested run")
    feature = repo_dir.resolve(strict=True) / relative
    if not feature.is_dir() or not feature.resolve().is_relative_to(repo_dir.resolve(strict=True)):
        raise HarnessError("feature directory is missing")
    if feature.is_symlink() or any(path.is_symlink() for path in feature.rglob("*")):
        raise HarnessError("agent output contains a symlink")
    review = _frontmatter(feature / "TestPlanReview.md")
    manifest = {
        str(path.relative_to(feature)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in feature.rglob("*")
        if path.is_file()
    }
    receipt = {
        "action": "completed",
        "task": task,
        "strategy_issue": key,
        "feature_dir": str(relative),
        "verdict": review.get("verdict"),
        "score": review.get("score"),
        "manifest": manifest,
        "errors": [],
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    validate_result(output_file, repo_dir, task, key, run_dir)


def copy_back(result_file: Path, repo_dir: Path, target_repo: Path, task: str, key: str, run_dir: str) -> Path:
    source = validate_result(result_file, repo_dir, task, key, run_dir)
    relative = source.relative_to(repo_dir.resolve(strict=True))
    target_root = target_repo.resolve(strict=True)
    destination = target_root / relative
    if destination.is_symlink() or any(path.is_symlink() for path in destination.parents if path != target_root.parent):
        raise HarnessError("target feature path contains a symlink")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="test-plan-copy-", dir=destination.parent) as staging:
        staged = Path(staging) / "feature"
        shutil.copytree(source, staged)
        backup = Path(staging) / "previous"
        if destination.exists():
            if task == "create":
                raise HarnessError("create would overwrite an existing feature")
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if backup.exists():
                backup.rename(destination)
            raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("source", type=Path)
    prep.add_argument("destination", type=Path)
    check = sub.add_parser("check-input")
    check.add_argument("task")
    check.add_argument("key")
    check.add_argument("run_dir")
    check.add_argument("feature_dir", nargs="?", default="")
    emit = sub.add_parser("emit-result")
    emit.add_argument("output_file", type=Path)
    emit.add_argument("repo_dir", type=Path)
    emit.add_argument("task")
    emit.add_argument("key")
    emit.add_argument("run_dir")
    emit.add_argument("feature_dir")
    post = sub.add_parser("copy-back")
    post.add_argument("result_file", type=Path)
    post.add_argument("repo_dir", type=Path)
    post.add_argument("target_repo", type=Path)
    post.add_argument("task")
    post.add_argument("key")
    post.add_argument("run_dir")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare_plugin(args.source, args.destination)
        elif args.command == "check-input":
            validate_input(args.task, args.key, args.run_dir, args.feature_dir)
        elif args.command == "emit-result":
            emit_result(args.output_file, args.repo_dir, args.task, args.key, args.run_dir, args.feature_dir)
        else:
            print(copy_back(args.result_file, args.repo_dir, args.target_repo, args.task, args.key, args.run_dir))
    except HarnessError as exc:
        print(f"fullsend harness: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
