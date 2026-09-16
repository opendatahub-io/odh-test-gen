"""
Unit tests for the ensure-gitlab-checkout subcommand in repo.py.

Tests sparse clone, pull refresh, sparse-checkout widening, directory search,
configurable clone_root, token scrubbing, and timeouts.
"""

import json
import os
import sys
from io import StringIO
from unittest.mock import MagicMock, patch


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

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, result = ensure_gitlab_checkout("RHAISTRAT-1868", clone_root=clone_path)
            assert code == 0
            assert result["source_type"] == "gitlab-clone"
            assert "RHAISTRAT-1868" in result["gitlab_url"]

    @patch("subprocess.run")
    def test_scrubs_token_after_clone(self, mock_run, tmp_path):
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

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            ensure_gitlab_checkout("RHAISTRAT-1868", clone_root=clone_path)

        set_url_calls = [
            c for c in mock_run.call_args_list
            if c[0][0] and "set-url" in c[0][0]
        ]
        assert len(set_url_calls) >= 1
        # The final set-url call (in the finally block) must use the credential-free URL
        url_arg = set_url_calls[-1][0][0][-1]
        assert "test-token" not in url_arg

    @patch("subprocess.run")
    def test_clone_has_timeout(self, mock_run, tmp_path):
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

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            ensure_gitlab_checkout("RHAISTRAT-1868", clone_root=clone_path)

        clone_call = [
            c for c in mock_run.call_args_list
            if c[0][0] and "clone" in c[0][0]
        ]
        assert len(clone_call) == 1
        assert clone_call[0][1].get("timeout") == 120


class TestEnsureGitlabCheckoutExistingClone:
    @patch("subprocess.run")
    def test_existing_clone_pulls(self, mock_run, tmp_path):
        clone_path = str(tmp_path / "test-plans-data")
        os.makedirs(os.path.join(clone_path, ".git"))

        ts_dir = tmp_path / "test-plans-data" / "RHAISTRAT" / "20260617-220856-RHAISTRAT-1868" / "feature"
        ts_dir.mkdir(parents=True)
        (ts_dir / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\n---\n")

        mock_run.return_value = MagicMock(returncode=0, stdout="RHAISTRAT\n", stderr="")

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, _result = ensure_gitlab_checkout("RHAISTRAT-1868", clone_root=clone_path)
            assert code == 0

            git_calls = [c[0][0] for c in mock_run.call_args_list]
            pull_called = any("pull" in cmd for cmd in git_calls if isinstance(cmd, list))
            assert pull_called

    @patch("subprocess.run")
    def test_pull_failure_warns(self, mock_run, tmp_path, capsys):
        clone_path = str(tmp_path / "test-plans-data")
        os.makedirs(os.path.join(clone_path, ".git"))

        ts_dir = tmp_path / "test-plans-data" / "RHAISTRAT" / "20260617-220856-RHAISTRAT-1868" / "feature"
        ts_dir.mkdir(parents=True)
        (ts_dir / "TestPlan.md").write_text("---\nsource_key: RHAISTRAT-1868\n---\n")

        import subprocess as sp

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if cmd and isinstance(cmd, list) and "pull" in cmd:
                raise sp.CalledProcessError(1, "git pull")
            return MagicMock(returncode=0, stdout="RHAISTRAT\n", stderr="")

        mock_run.side_effect = side_effect

        with patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}):
            code, _result = ensure_gitlab_checkout("RHAISTRAT-1868", clone_root=clone_path)
            assert code == 0

        captured = capsys.readouterr()
        assert "Warning: git pull failed" in captured.err


class TestEnsureGitlabCheckoutNoDir:
    def test_no_timestamped_dir(self, tmp_path):
        clone_path = str(tmp_path / "test-plans-data")
        os.makedirs(os.path.join(clone_path, ".git"))
        os.makedirs(os.path.join(clone_path, "RHAISTRAT"))

        with (
            patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="RHAISTRAT\n", stderr="")),
            patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}),
        ):
            code, result = ensure_gitlab_checkout("RHAISTRAT-1868", clone_root=clone_path)
            assert code == 1
            assert "No timestamped directory" in result["error"]


class TestEnsureGitlabCheckoutEndswith:
    def test_endswith_prevents_false_positive(self, tmp_path):
        clone_path = str(tmp_path / "test-plans-data")
        os.makedirs(os.path.join(clone_path, ".git"))

        rha_dir = tmp_path / "test-plans-data" / "RHAISTRAT"
        rha_dir.mkdir()
        false_match = rha_dir / "20260617-220856-RHAISTRAT-18"
        false_match.mkdir()
        (false_match / "feat").mkdir()
        (false_match / "feat" / "TestPlan.md").write_text("test")

        with (
            patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="RHAISTRAT\n", stderr="")),
            patch.dict(os.environ, {"GITLAB_TOKEN": "test-token"}),
        ):
            code, _result = ensure_gitlab_checkout("RHAISTRAT-1868", clone_root=clone_path)
            assert code == 1


class TestEnsureGitlabCheckoutConfigurable:
    def test_clone_root_from_env(self, tmp_path):
        clone_path = str(tmp_path / "custom-dir")
        os.makedirs(os.path.join(clone_path, ".git"))
        rha_dir = tmp_path / "custom-dir" / "RHAISTRAT" / "20260617-RHAISTRAT-1868" / "feat"
        rha_dir.mkdir(parents=True)
        (rha_dir / "TestPlan.md").write_text("test")

        with (
            patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="RHAISTRAT\n", stderr="")),
            patch.dict(os.environ, {"GITLAB_TOKEN": "test-token", "TEST_PLANS_DATA_DIR": clone_path}),
        ):
            code, result = ensure_gitlab_checkout("RHAISTRAT-1868")
            assert code == 0
            assert clone_path in result["feature_dir"]

    def test_clone_root_param_overrides_env(self, tmp_path):
        clone_path = str(tmp_path / "param-dir")
        os.makedirs(os.path.join(clone_path, ".git"))
        rha_dir = tmp_path / "param-dir" / "RHAISTRAT" / "20260617-RHAISTRAT-1868" / "feat"
        rha_dir.mkdir(parents=True)
        (rha_dir / "TestPlan.md").write_text("test")

        env_path = str(tmp_path / "env-dir")

        with (
            patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="RHAISTRAT\n", stderr="")),
            patch.dict(os.environ, {"GITLAB_TOKEN": "test-token", "TEST_PLANS_DATA_DIR": env_path}),
        ):
            code, result = ensure_gitlab_checkout("RHAISTRAT-1868", clone_root=clone_path)
            assert code == 0
            assert clone_path in result["feature_dir"]


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

    def test_cli_clone_root_flag(self):
        old_argv = sys.argv
        old_stdout = sys.stdout

        try:
            sys.argv = ["repo.py", "ensure-gitlab-checkout", "RHAISTRAT-1868", "--clone-root", "/tmp/custom"]
            sys.stdout = StringIO()

            with patch("scripts.repo.ensure_gitlab_checkout") as mock_fn:
                mock_fn.return_value = (0, {"feature_dir": "/tmp/custom/test", "source_type": "gitlab-clone"})

                from scripts.repo import main

                try:
                    exit_code = main()
                except SystemExit as e:
                    exit_code = e.code

                assert exit_code == 0
                mock_fn.assert_called_once_with("RHAISTRAT-1868", clone_root="/tmp/custom")
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
