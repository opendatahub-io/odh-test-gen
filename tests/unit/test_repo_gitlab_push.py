"""
Unit tests for the push-to-gitlab subcommand in repo.py.

Tests timestamped directory naming, artifact whitelist, MR workflow (branch creation,
push to branch, MR API call, checkout back to main), token scrubbing, and timeouts.
"""

import json
import os
import subprocess
import sys
from io import StringIO
from unittest.mock import MagicMock, patch


from scripts.repo import push_to_gitlab


class TestPushToGitlabMissingToken:
    def test_empty_token(self, tmp_path):
        with patch.dict(os.environ, {"GITLAB_TOKEN": ""}, clear=False):
            code, result = push_to_gitlab(str(tmp_path), clone_root=str(tmp_path / "nonexistent"))
        assert code == 1
        assert "GITLAB_TOKEN" in result["error"]

    def test_unset_token(self, tmp_path):
        env = os.environ.copy()
        env.pop("GITLAB_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            code, result = push_to_gitlab(str(tmp_path), clone_root=str(tmp_path / "nonexistent"))
        assert code == 1
        assert "GITLAB_TOKEN" in result["error"]


class TestPushToGitlabNoClone:
    def test_no_clone(self, tmp_path):
        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, result = push_to_gitlab(str(tmp_path), clone_root=str(tmp_path / "nonexistent"))
        assert code == 1
        assert "No local clone" in result["error"]


class TestPushToGitlabNoTestplan:
    def test_no_testplan(self, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, result = push_to_gitlab(str(feature), clone_root=str(clone))
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

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, result = push_to_gitlab(str(feature), clone_root=str(clone))
        assert code == 1
        assert "source_key" in result["error"]


class TestPushToGitlabSuccess:
    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    def test_successful_push(self, mock_run, mock_urlopen, tmp_path):
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

        mr_response = MagicMock()
        mr_response.read.return_value = b'{"web_url": "https://gitlab.com/mr/1"}'
        mr_response.__enter__ = MagicMock(return_value=mr_response)
        mr_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mr_response

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, result = push_to_gitlab(str(feature), clone_root=str(clone))

        assert code == 0
        assert "RHAISTRAT-1868" in result["gitlab_path"]
        assert "gpu_runtimes" in result["gitlab_path"]
        assert "TestPlan.md" in result["pushed_files"]
        assert "README.md" in result["pushed_files"]
        assert "TestPlanGaps.md" in result["pushed_files"]
        assert "test_cases/TC-001.md" in result["pushed_files"]
        assert result["commit_sha"] == "abc123"
        assert result["mr_url"] == "https://gitlab.com/mr/1"


class TestPushToGitlabMRWorkflow:
    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    def test_creates_branch_and_pushes(self, mock_run, mock_urlopen, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text(
            "---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: my_feature\n---\n"
        )

        mock_run.return_value = MagicMock(returncode=0, stdout="def456\n", stderr="")

        mr_response = MagicMock()
        mr_response.read.return_value = b'{"web_url": "https://gitlab.com/mr/2"}'
        mr_response.__enter__ = MagicMock(return_value=mr_response)
        mr_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mr_response

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, _result = push_to_gitlab(str(feature), clone_root=str(clone))

        assert code == 0

        git_calls = [c[0][0] for c in mock_run.call_args_list if isinstance(c[0][0], list)]

        checkout_b_calls = [c for c in git_calls if "checkout" in c and "-b" in c]
        assert len(checkout_b_calls) == 1
        branch_name = checkout_b_calls[0][-1]
        assert branch_name.startswith("test-plan-update/RHAISTRAT-1868-")

        push_calls = [c for c in git_calls if "push" in c]
        assert len(push_calls) == 1
        assert push_calls[0][-1] == branch_name

        checkout_main_calls = [c for c in git_calls if "checkout" in c and "main" in c and "-b" not in c]
        assert len(checkout_main_calls) == 1

    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    def test_mr_api_called(self, mock_run, mock_urlopen, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: f\n---\n")

        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")

        mr_response = MagicMock()
        mr_response.read.return_value = b'{"web_url": "https://gitlab.com/mr/3"}'
        mr_response.__enter__ = MagicMock(return_value=mr_response)
        mr_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mr_response

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, _result = push_to_gitlab(str(feature), clone_root=str(clone))

        assert code == 0
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert "merge_requests" in req.full_url
        body = json.loads(req.data.decode())
        assert body["target_branch"] == "main"
        assert body["remove_source_branch"] is True


class TestPushToGitlabTokenScrub:
    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    def test_scrubs_token_after_push(self, mock_run, mock_urlopen, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: f\n---\n")

        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")

        mr_response = MagicMock()
        mr_response.read.return_value = b'{"web_url": ""}'
        mr_response.__enter__ = MagicMock(return_value=mr_response)
        mr_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mr_response

        with patch.dict(os.environ, {"GITLAB_TOKEN": "secret-token"}):
            push_to_gitlab(str(feature), clone_root=str(clone))

        set_url_calls = [c for c in mock_run.call_args_list if isinstance(c[0][0], list) and "set-url" in c[0][0]]
        assert len(set_url_calls) >= 2
        last_set_url = set_url_calls[-1][0][0][-1]
        assert "secret-token" not in last_set_url


class TestPushToGitlabTimeouts:
    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    def test_push_has_timeout(self, mock_run, mock_urlopen, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: f\n---\n")

        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")

        mr_response = MagicMock()
        mr_response.read.return_value = b'{"web_url": ""}'
        mr_response.__enter__ = MagicMock(return_value=mr_response)
        mr_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mr_response

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            push_to_gitlab(str(feature), clone_root=str(clone))

        for call in mock_run.call_args_list:
            assert "timeout" in call[1], f"Missing timeout in call: {call[0][0]}"

        push_call = [c for c in mock_run.call_args_list if isinstance(c[0][0], list) and "push" in c[0][0]]
        assert push_call[0][1]["timeout"] == 60


class TestPushToGitlabTimestamp:
    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    def test_creates_timestamped_dir(self, mock_run, mock_urlopen, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text(
            "---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: my_feature\n---\n"
        )

        mock_run.return_value = MagicMock(returncode=0, stdout="def456\n", stderr="")

        mr_response = MagicMock()
        mr_response.read.return_value = b'{"web_url": ""}'
        mr_response.__enter__ = MagicMock(return_value=mr_response)
        mr_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mr_response

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, result = push_to_gitlab(str(feature), clone_root=str(clone))

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
            if cmd and isinstance(cmd, list) and "push" in cmd:
                raise subprocess.CalledProcessError(1, "git push", stderr="auth failed")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        with patch.dict(os.environ, {"GITLAB_TOKEN": "secret"}):
            code, result = push_to_gitlab(str(feature), clone_root=str(clone))

        assert code == 1
        assert "push failed" in result["error"].lower()
        assert "secret" not in result["error"]

    @patch("subprocess.run")
    def test_push_failure_cleans_up_branch(self, mock_run, tmp_path):
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: f\n---\n")

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if cmd and isinstance(cmd, list) and "push" in cmd:
                raise subprocess.CalledProcessError(1, "git push", stderr="denied")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        with patch.dict(os.environ, {"GITLAB_TOKEN": "tok"}):
            code, result = push_to_gitlab(str(feature), clone_root=str(clone))

        assert code == 1
        assert "error" in result
        assert "git push failed" in result["error"]

        git_calls = [c[0][0] for c in mock_run.call_args_list if isinstance(c[0][0], list)]

        checkout_main_calls = [c for c in git_calls if "checkout" in c and "main" in c and "-b" not in c]
        assert len(checkout_main_calls) >= 1, "Expected git checkout main for cleanup"

        branch_delete_calls = [c for c in git_calls if "branch" in c and "-D" in c]
        assert len(branch_delete_calls) == 1, "Expected git branch -D for cleanup"
        deleted_branch = branch_delete_calls[0][-1]
        assert deleted_branch.startswith("test-plan-update/RHAISTRAT-1868-")


class TestPushToGitlabConfigurable:
    @patch("urllib.request.urlopen")
    @patch("subprocess.run")
    def test_clone_root_from_env(self, mock_run, mock_urlopen, tmp_path):
        clone = tmp_path / "env-clone"
        clone.mkdir()
        (clone / ".git").mkdir()

        feature = tmp_path / "feature"
        feature.mkdir()
        (feature / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\nversion: 1.0.0\nfeature: f\n---\n")

        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")

        mr_response = MagicMock()
        mr_response.read.return_value = b'{"web_url": ""}'
        mr_response.__enter__ = MagicMock(return_value=mr_response)
        mr_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mr_response

        with patch.dict(os.environ, {"GITLAB_TOKEN": "t", "TEST_PLANS_DATA_DIR": str(clone)}):
            code, _result = push_to_gitlab(str(feature))

        assert code == 0


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
                    {"pushed_files": ["TestPlan.md"], "gitlab_url": "https://example.com", "mr_url": ""},
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

    def test_cli_clone_root_flag(self):
        old_argv = sys.argv
        old_stdout = sys.stdout

        try:
            sys.argv = ["repo.py", "push-to-gitlab", "/tmp/feature", "--clone-root", "/tmp/custom"]
            sys.stdout = StringIO()

            with patch("scripts.repo.push_to_gitlab") as mock_fn:
                mock_fn.return_value = (0, {"pushed_files": [], "gitlab_url": "", "mr_url": ""})

                from scripts.repo import main

                try:
                    exit_code = main()
                except SystemExit as e:
                    exit_code = e.code

                assert exit_code == 0
                mock_fn.assert_called_once_with("/tmp/feature", clone_root="/tmp/custom")
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
