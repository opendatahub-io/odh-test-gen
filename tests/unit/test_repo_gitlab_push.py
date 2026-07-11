"""
Unit tests for the push-to-gitlab subcommand in repo.py.

Tests timestamped directory naming, artifact whitelist, commit, and push.
"""

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.repo import push_to_gitlab


class TestPushToGitlabNoClone:
    def test_no_clone(self, tmp_path):
        with patch("scripts.repo.GITLAB_CLONE_ROOT", str(tmp_path / "nonexistent")):
            code, result = push_to_gitlab(str(tmp_path))
            assert code == 1
            assert "No local clone" in result["error"]


class TestPushToGitlabNoTestplan:
    def test_no_testplan(self, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()

        with patch("scripts.repo.GITLAB_CLONE_ROOT", str(clone)):
            code, result = push_to_gitlab(str(feature))
            assert code == 1
            assert "TestPlan.md not found" in result["error"]


class TestPushToGitlabMissingKey:
    def test_missing_source_key(self, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text("---\nversion: 1.0.0\n---\n")

        with patch("scripts.repo.GITLAB_CLONE_ROOT", str(clone)):
            code, result = push_to_gitlab(str(feature))
            assert code == 1
            assert "source_key" in result["error"]


class TestPushToGitlabSuccess:
    @patch("subprocess.run")
    def test_successful_push(self, mock_run, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text(
            "---\nsource_key: RHAISTRAT-1868\nversion: 1.2.0\nfeature: gpu_runtimes\n---\n# Plan\n"
        )
        (feature / "README.md").write_text("# README\n")
        (feature / "TestPlanGaps.md").write_text("# Gaps\n")
        tc = feature / "test_cases"
        tc.mkdir()
        (tc / "TC-001.md").write_text("# TC\n")

        mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n", stderr="")

        with patch("scripts.repo.GITLAB_CLONE_ROOT", str(clone)):
            code, result = push_to_gitlab(str(feature))

        assert code == 0
        assert "RHAISTRAT-1868" in result["gitlab_path"]
        assert "gpu_runtimes" in result["gitlab_path"]
        assert "TestPlan.md" in result["pushed_files"]
        assert "README.md" in result["pushed_files"]
        assert "TestPlanGaps.md" in result["pushed_files"]
        assert "test_cases/TC-001.md" in result["pushed_files"]
        assert result["commit_sha"] == "abc123"


class TestPushToGitlabTimestamp:
    @patch("subprocess.run")
    def test_creates_timestamped_dir(self, mock_run, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text(
            "---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: my_feature\n---\n"
        )

        mock_run.return_value = MagicMock(returncode=0, stdout="def456\n", stderr="")

        with patch("scripts.repo.GITLAB_CLONE_ROOT", str(clone)):
            code, result = push_to_gitlab(str(feature))

        assert code == 0
        assert result["gitlab_path"].startswith("RHAISTRAT/")
        assert "RHAISTRAT-1868" in result["gitlab_path"]
        assert "my_feature" in result["gitlab_path"]


class TestPushToGitlabGitFailure:
    @patch("subprocess.run")
    def test_git_push_failure(self, mock_run, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: f\n---\n")

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if cmd and "push" in cmd:
                raise subprocess.CalledProcessError(1, "git push", stderr="auth failed")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        with (
            patch("scripts.repo.GITLAB_CLONE_ROOT", str(clone)),
            patch.dict(os.environ, {"GITLAB_TOKEN": "secret"}),
        ):
            code, result = push_to_gitlab(str(feature))

        assert code == 1
        assert "push failed" in result["error"].lower()
        assert "secret" not in result["error"]


class TestPushToGitlabCLI:
    def test_cli_invocation(self):
        old_argv = sys.argv
        old_stdout = sys.stdout

        try:
            sys.argv = ["repo.py", "push-to-gitlab", "/tmp/feature"]
            sys.stdout = StringIO()

            with patch("scripts.repo.push_to_gitlab") as mock_fn:
                mock_fn.return_value = (
                    0,
                    {"pushed_files": ["TestPlan.md"], "gitlab_url": "https://example.com"},
                )

                from scripts.repo import main

                try:
                    exit_code = main()
                except SystemExit as e:
                    exit_code = e.code

                assert exit_code == 0
                output = json.loads(sys.stdout.getvalue())
                assert "pushed_files" in output
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
