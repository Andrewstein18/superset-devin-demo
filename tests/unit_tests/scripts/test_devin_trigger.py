# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import json  # noqa: TID251
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from devin_trigger import (  # noqa: E402
    build_devin_prompt,
    create_devin_session,
    create_github_issue,
    github_api_request,
)

FAKE_TOKEN = "gh_test_token"  # noqa: S105
FAKE_DEVIN_TOKEN = "dv_test_token"  # noqa: S105


def _mock_urlopen(
    response_data: dict[str, Any],
) -> MagicMock:
    """Create a mock for urllib.request.urlopen."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


def test_github_api_request_get() -> None:
    response_data: dict[str, Any] = {"id": 1, "name": "test"}
    mock_response = _mock_urlopen(response_data)

    with patch(
        "devin_trigger.urllib.request.urlopen",
        return_value=mock_response,
    ):
        result = github_api_request("/repos/org/repo", token=FAKE_TOKEN)

    assert result == response_data


def test_github_api_request_post() -> None:
    response_data: dict[str, Any] = {
        "number": 42,
        "html_url": "https://github.com/org/repo/issues/42",
    }
    mock_response = _mock_urlopen(response_data)

    with patch(
        "devin_trigger.urllib.request.urlopen",
        return_value=mock_response,
    ):
        result = github_api_request(
            "/repos/org/repo/issues",
            method="POST",
            token=FAKE_TOKEN,
            data={"title": "Test Issue"},
        )

    assert result["number"] == 42
    assert "issues/42" in result["html_url"]


def test_create_github_issue() -> None:
    response_data: dict[str, Any] = {
        "number": 7,
        "html_url": "https://github.com/org/repo/issues/7",
        "title": "Bug report",
    }
    mock_response = _mock_urlopen(response_data)

    with patch(
        "devin_trigger.urllib.request.urlopen",
        return_value=mock_response,
    ):
        result = create_github_issue(
            repo="org/repo",
            title="Bug report",
            body="Something is broken",
            labels=["bug", "automated"],
            token=FAKE_TOKEN,
        )

    assert result["number"] == 7
    assert result["title"] == "Bug report"


def test_create_github_issue_no_labels() -> None:
    response_data: dict[str, Any] = {
        "number": 8,
        "html_url": "https://github.com/org/repo/issues/8",
    }
    mock_response = _mock_urlopen(response_data)

    with patch(
        "devin_trigger.urllib.request.urlopen",
        return_value=mock_response,
    ):
        result = create_github_issue(
            repo="org/repo",
            title="No labels",
            body="Test body",
            labels=[],
            token=FAKE_TOKEN,
        )

    assert result["number"] == 8


def test_create_devin_session() -> None:
    response_data: dict[str, Any] = {
        "session_id": "ses_abc123",
        "url": "https://app.devin.ai/sessions/abc123",
    }
    mock_response = _mock_urlopen(response_data)

    with patch(
        "devin_trigger.urllib.request.urlopen",
        return_value=mock_response,
    ):
        result = create_devin_session(
            prompt="Fix the bug in utils.py",
            api_token=FAKE_DEVIN_TOKEN,
        )

    assert result["session_id"] == "ses_abc123"
    assert "devin.ai" in result["url"]


def test_create_devin_session_error() -> None:
    with patch(
        "devin_trigger.urllib.request.urlopen",
        side_effect=Exception("API error"),
    ):
        with pytest.raises(Exception, match="API error"):
            create_devin_session(
                prompt="Fix something",
                api_token=FAKE_DEVIN_TOKEN,
            )


def test_build_devin_prompt() -> None:
    prompt = build_devin_prompt(
        repo="org/repo",
        issue_url="https://github.com/org/repo/issues/42",
        issue_title="Fix broken import",
        issue_body="The import in utils.py is broken",
    )

    assert "org/repo" in prompt
    assert "https://github.com/org/repo/issues/42" in prompt
    assert "Fix broken import" in prompt
    assert "The import in utils.py is broken" in prompt
    assert "Fixes #42" in prompt


def test_build_devin_prompt_contains_steps() -> None:
    prompt = build_devin_prompt(
        repo="org/repo",
        issue_url="https://github.com/org/repo/issues/1",
        issue_title="Test",
        issue_body="Test body",
    )

    assert "Search the codebase" in prompt
    assert "Create a PR" in prompt
    assert "Run tests" in prompt
