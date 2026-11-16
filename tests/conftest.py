"""Shared pytest fixtures for backend tests.

All backend tests must run offline and without real API keys. Outbound
network connections are blocked for the whole session; only loopback is
allowed (FastAPI's TestClient does not open sockets, but local helpers may).
"""

from __future__ import annotations

import os
import socket
import unittest  # noqa: F401  # ArkClient disables itself when unittest is loaded.
from pathlib import Path

import pytest

# Make sure no developer key leaks into a test run and that model clients
# stay disabled even if a local .env exists.
for _key in (
    "DEEPSEEK_ENABLE_IN_TESTS",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GLM_API_KEY",
    "DEEPSEEK_API_KEY",
    "ARK_API_KEY",
):
    os.environ.pop(_key, None)

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_real_connect = socket.socket.connect


def _guarded_connect(self: socket.socket, address, *args, **kwargs):  # type: ignore[no-untyped-def]
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, str) and host not in _LOOPBACK:
        raise RuntimeError(f"Network access is blocked in tests (attempted {address!r})")
    return _real_connect(self, address, *args, **kwargs)


socket.socket.connect = _guarded_connect  # type: ignore[method-assign]


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect home-directory writes (e.g. ~/.openclaw/workspace) into tmp."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("OPENCLAW_WORKSPACE_DIR", raising=False)
    return home
