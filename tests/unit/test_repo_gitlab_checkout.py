"""
Unit tests for the ensure-gitlab-checkout subcommand in repo.py.

Tests sparse clone, pull refresh, sparse-checkout widening, and directory search.
"""

import json
import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.repo import ensure_gitlab_checkout


class TestEnsureGitlabCheckoutMissingToken:
    def test_missing_token(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITLAB_TOKEN", None)
            code, result = ensure_gitlab_checkout("RHAISTRAT-1868")
            assert code == 1
            assert "GITLAB_TOKEN" in result["error"]


class TestEnsureGitlabCheckoutInvalidKey:
    def test_invalid_key(self):
        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, result = ensure_gitlab_checkout("lowercase-123")
            assert code == 1
            assert "Invalid" in result["error"]


class TestEnsureGitlabCheckoutFreshClone:
    @patch("subprocess.run")
    def test_fresh_clone(self, mock_run, tmp_path):
        clone_path = str(tmp_path / "test-plans-data")
        ts_dir = tmp_path / "test-plans-data" / "RHAISTRAT" / "20260617-220856-RHAISTRAT-1868" / "gpu_runtimes"

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if cmd and cmd[0] == "git" and "clone" in cmd:
                os.makedirs(os.path.join(clone_path, ".git"), exist_ok=True)
                ts_dir.mkdir(parents=True, exist_ok=True)
                (ts_dir / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\n---\n")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        with (
            patch("scripts.repo.GITLAB_CLONE_ROOT", clone_path),
            patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}),
        ):
            code, result = ensure_gitlab_checkout("RHAISTRAT-1868")
            assert code == 0
            assert result["source_type"] == "gitlab-clone"
            assert "RHAISTRAT-1868" in result["gitlab_url"]


class TestEnsureGitlabCheckoutExistingClone:
    @patch("subprocess.run")
    def test_existing_clone_pulls(self, mock_run, tmp_path):
        clone_path = str(tmp_path / "test-plans-data")
        os.makedirs(os.path.join(clone_path, ".git"))

        ts_dir = tmp_path / "test-plans-data" / "RHAISTRAT" / "20260617-220856-RHAISTRAT-1868" / "feature"
        ts_dir.mkdir(parents=True)
        (ts_dir / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\n---\n")

        mock_run.return_value = MagicMock(returncode=0, stdout="RHAISTRAT\n", stderr="")

        with (
            patch("scripts.repo.GITLAB_CLONE_ROOT", clone_path),
            patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}),
        ):
            code, result = ensure_gitlab_checkout("RHAISTRAT-1868")
            assert code == 0

            git_calls = [c[0][0] for c in mock_run.call_args_list]
            pull_called = any("pull" in cmd for cmd in git_calls if isinstance(cmd, list))
            assert pull_called


class TestEnsureGitlabCheckoutNoDir:
    def test_no_timestamped_dir(self, tmp_path):
        clone_path = str(tmp_path / "test-plans-data")
        os.makedirs(os.path.join(clone_path, ".git"))
        os.makedirs(os.path.join(clone_path, "RHAISTRAT"))

        with (
            patch("scripts.repo.GITLAB_CLONE_ROOT", clone_path),
            patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="RHAISTRAT\n", stderr="")),
            patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}),
        ):
            code, result = ensure_gitlab_checkout("RHAISTRAT-1868")
            assert code == 1
            assert "No timestamped directory" in result["error"]


class TestEnsureGitlabCheckoutCLI:
    def test_cli_invocation(self):
        old_argv = sys.argv
        old_stdout = sys.stdout

        try:
            sys.argv = ["repo.py", "ensure-gitlab-checkout", "RHAISTRAT-1868"]
            sys.stdout = StringIO()

            with patch("scripts.repo.ensure_gitlab_checkout") as mock_fn:
                mock_fn.return_value = (0, {"feature_dir": "/tmp/test", "source_type": "gitlab-clone"})

                from scripts.repo import main

                try:
                    exit_code = main()
                except SystemExit as e:
                    exit_code = e.code

                assert exit_code == 0
                output = json.loads(sys.stdout.getvalue())
                assert output["source_type"] == "gitlab-clone"
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
