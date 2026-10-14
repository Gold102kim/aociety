from __future__ import annotations

import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services.ark_client import ArkClient


class TestArkErrorPrivacy(unittest.TestCase):
    def make_client(self, error: Exception) -> ArkClient:
        with patch.dict(os.environ, {"DEEPSEEK_FAILURE_COOLDOWN_SECONDS": "15"}, clear=True):
            client = ArkClient()
        self.addCleanup(client.close)
        client._client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=Mock(side_effect=error))),
            close=Mock(),
        )
        return client

    def test_probe_and_cooldown_do_not_expose_upstream_body(self) -> None:
        sentinel = "PRIVATE_KEY_AND_PROMPT_SENTINEL"
        error = RuntimeError(sentinel)
        error.status_code = 401
        client = self.make_client(error)
        initial = client.probe()
        cooldown = client.probe()
        for result in (initial, cooldown):
            self.assertFalse(result["ok"])
            self.assertNotIn(sentinel, result["message"])
            self.assertIn("401", result["message"])
        self.assertNotIn(sentinel, client._last_error)

    def test_transport_error_never_echoes_paths_or_payload(self) -> None:
        client = self.make_client(RuntimeError("PRIVATE_PATH_OR_PAYLOAD_SENTINEL"))
        result = client.probe()
        self.assertFalse(result["ok"])
        self.assertNotIn("PRIVATE_PATH_OR_PAYLOAD_SENTINEL", result["message"])
        self.assertIn("DeepSeek", result["message"])

    def test_only_numeric_http_status_is_exposed(self) -> None:
        error = RuntimeError("PRIVATE_SENTINEL")
        for status in ("PRIVATE_SENTINEL", True, 399, 600):
            error.status_code = status
            self.assertNotIn("PRIVATE_SENTINEL", ArkClient._public_error_message(error))
        self.assertIn("超时", ArkClient._public_error_message(TimeoutError("PRIVATE_SENTINEL")))


if __name__ == "__main__":
    unittest.main()
