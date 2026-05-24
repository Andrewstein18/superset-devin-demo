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
"""Integration test for the fixer flow.

Verifies: trigger label applied → Devin session spawned → PR body
contains ``Fixes #N``.
"""

from __future__ import annotations

import json  # noqa: TID251
import sys
from http.client import HTTPResponse
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _make_urlopen_response(body: dict[str, Any]) -> MagicMock:
    """Build a mock suitable for ``urllib.request.urlopen`` context manager."""
    raw = json.dumps(body).encode()
    resp = MagicMock(spec=HTTPResponse)
    resp.read.return_value = raw
    resp.status = 200
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


@pytest.fixture(autouse=True)
def _isolate_module():
    """Remove cached module so each test gets a fresh import."""
    mod = "scripts.tech_debt_scanner.fix_issue"
    sys.modules.pop(mod, None)
    yield
    sys.modules.pop(mod, None)


def test_fixer_spawns_session_with_fixes_reference(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Label applied → session spawned → prompt contains ``Fixes #42``."""
    monkeypatch.setenv("DEVIN_API_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-test-token")
    monkeypatch.setenv("TARGET_REPO", "test-org/test-repo")

    captured_payloads: list[dict[str, Any]] = []

    call_count = 0

    def fake_urlopen(req: Any, **kwargs: Any) -> MagicMock:
        nonlocal call_count
        url = req.full_url if hasattr(req, "full_url") else str(req)
        method = req.get_method()

        if "/sessions/sess-abc123" in url and method == "GET":
            call_count += 1
            return _make_urlopen_response({"status_enum": "finished"})

        if "/sessions" in url and method == "POST":
            data = json.loads(req.data.decode())
            captured_payloads.append(data)
            return _make_urlopen_response({"session_id": "sess-abc123"})

        if "/comments" in url:
            return _make_urlopen_response({})

        if "/issues/42" in url and method == "PATCH":
            return _make_urlopen_response({})

        return _make_urlopen_response({})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        from scripts.tech_debt_scanner.fix_issue import (
            add_comment,
            create_session,
            load_config,
            wait_for_session,
        )

        cfg = load_config()
        assert cfg["target_repo"] == "test-org/test-repo"

        from scripts.tech_debt_scanner.fix_issue import FIXER_PROMPT

        rendered_prompt = FIXER_PROMPT.format(
            repo="test-org/test-repo",
            issue_url="https://github.com/test-org/test-repo/issues/42",
            issue_title="Bug in parser",
            issue_number=42,
        )

        assert "Fixes #42" in rendered_prompt

        session_id = create_session(
            rendered_prompt, "Fixer: Bug in parser", "test-token"
        )
        assert session_id == "sess-abc123"

        assert len(captured_payloads) == 1
        assert "Fixes #42" in captured_payloads[0]["prompt"]
        assert "remediation-engine" in captured_payloads[0]["tags"]

        status = wait_for_session("sess-abc123", "test-token", timeout=1)
        assert status == "finished"

        add_comment(42, "sess-abc123", "test-org/test-repo")


def test_load_config_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """Config falls back to defaults when env vars are unset."""
    monkeypatch.delenv("TARGET_REPO", raising=False)
    monkeypatch.delenv("TRIGGER_LABEL", raising=False)

    from scripts.tech_debt_scanner.fix_issue import load_config

    cfg = load_config()
    assert cfg["target_repo"] == "Andrewstein18/superset-devin-demo"
    assert cfg["trigger_label"] == "devin-fix"


def test_load_config_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env vars override config.yaml values."""
    monkeypatch.setenv("TARGET_REPO", "my-org/my-repo")
    monkeypatch.setenv("TRIGGER_LABEL", "auto-fix")

    from scripts.tech_debt_scanner.fix_issue import load_config

    cfg = load_config()
    assert cfg["target_repo"] == "my-org/my-repo"
    assert cfg["trigger_label"] == "auto-fix"
