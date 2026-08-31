"""
Unit tests for the add_comment function in jira_utils.py.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from scripts.jira_utils import add_comment


class TestAddComment:
    @patch("scripts.jira_utils.make_request")
    def test_posts_adf_comment(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "12345"}'
        mock_response.json.return_value = {"id": "12345", "body": {}}
        mock_request.return_value = mock_response

        with patch.dict(
            os.environ,
            {
                "JIRA_URL": "https://jira.example.com",
                "JIRA_USER": "user@example.com",
                "JIRA_TOKEN": "test-token",
            },
        ):
            add_comment("RHAISTRAT-1868", "Test plan updated v1.0 -> v1.1")

        mock_request.assert_called_once()
        call_args = mock_request.call_args

        assert call_args[0][0] == "POST"
        assert "/rest/api/3/issue/RHAISTRAT-1868/comment" in call_args[0][1]

        json_body = call_args[1].get("json_data") or call_args[0][2]
        assert json_body["body"]["type"] == "doc"
        assert json_body["body"]["version"] == 1
        assert json_body["body"]["content"][0]["type"] == "paragraph"
        assert json_body["body"]["content"][0]["content"][0]["text"] == "Test plan updated v1.0 -> v1.1"

    @patch("scripts.jira_utils.make_request")
    def test_returns_response(self, mock_request):
        expected = {"id": "99", "self": "https://jira.example.com/rest/api/3/comment/99"}
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "99"}'
        mock_response.json.return_value = expected
        mock_request.return_value = mock_response

        with patch.dict(
            os.environ,
            {
                "JIRA_URL": "https://jira.example.com",
                "JIRA_USER": "user@example.com",
                "JIRA_TOKEN": "test-token",
            },
        ):
            result = add_comment("RHAISTRAT-1868", "hello")

        assert result == expected

    def test_missing_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            for var in ("JIRA_URL", "JIRA_USER", "JIRA_TOKEN"):
                os.environ.pop(var, None)
            with pytest.raises(SystemExit):
                add_comment("RHAISTRAT-1868", "test")
