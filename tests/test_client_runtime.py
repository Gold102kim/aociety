from __future__ import annotations

import os
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from services.ark_client import ArkClient


class TestArkClientRuntime(unittest.TestCase):
    def make_client(self, completion=None, **environment: str) -> ArkClient:
        defaults = {"DEEPSEEK_DIALOGUE_WORKERS": "1", "DEEPSEEK_FAILURE_COOLDOWN_SECONDS": "0"}
        with patch.dict(os.environ, {**defaults, **environment}, clear=True):
            client = ArkClient()
        self.addCleanup(client.close)
        if completion is not None:
            client._client = SimpleNamespace(
                chat=SimpleNamespace(completions=SimpleNamespace(create=completion)),
                close=Mock(),
            )
        return client

    def test_sdk_retries_are_disabled_and_io_timeout_respects_hard_limit(self) -> None:
        with patch.dict(os.environ, {
            "DEEPSEEK_API_KEY": "test-key-not-a-secret",
            "DEEPSEEK_ENABLE_IN_TESTS": "1",
            "DEEPSEEK_TIMEOUT_SECONDS": "20",
            "DEEPSEEK_HARD_TIMEOUT_SECONDS": "3",
        }, clear=True), patch("services.ark_client.OpenAI") as sdk:
            client = ArkClient()
        self.addCleanup(client.close)
        self.assertEqual(sdk.call_args.kwargs["max_retries"], 0)
        self.assertEqual(sdk.call_args.kwargs["timeout"], 3)

    def test_timed_out_request_holds_capacity_until_it_really_finishes(self) -> None:
        started, release, finished = threading.Event(), threading.Event(), threading.Event()

        def completion():
            started.set()
            release.wait(1)
            finished.set()
            return "finished"

        client = self.make_client(completion)
        client.hard_timeout_seconds = 0.01
        try:
            with self.assertRaises(TimeoutError):
                client._create_completion("dialogue_turn")
            self.assertTrue(started.is_set())
            self.assertFalse(finished.is_set())
            with self.assertRaisesRegex(RuntimeError, "busy"):
                client._create_completion("dialogue_turn")
            release.set()
            self.assertTrue(finished.wait(1))
            deadline = time.monotonic() + 1
            while True:
                try:
                    self.assertEqual(client._create_completion("dialogue_turn"), "finished")
                    break
                except RuntimeError:
                    if time.monotonic() >= deadline:
                        self.fail("worker slot was not released")
                    time.sleep(0.001)
        finally:
            release.set()

    def test_close_is_idempotent_and_rejects_new_work(self) -> None:
        client = self.make_client(lambda: "ok")
        close_transport = client._client.close
        client.close()
        client.close()
        close_transport.assert_called_once()
        self.assertFalse(client.enabled)
        self.assertFalse(client.configured)
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            client._create_completion("dialogue_turn")

    def test_parallel_success_does_not_clear_newer_failure_cooldown(self) -> None:
        started, release = threading.Event(), threading.Event()

        def completion(*, request):
            if request == "success":
                started.set()
                release.wait(1)
                return "ok"
            raise ValueError("failed request")

        client = self.make_client(completion, DEEPSEEK_DIALOGUE_WORKERS="2", DEEPSEEK_FAILURE_COOLDOWN_SECONDS="15")
        completed = []
        thread = threading.Thread(target=lambda: completed.append(client._create_completion("dialogue_turn", request="success")))
        thread.start()
        try:
            self.assertTrue(started.wait(1))
            with self.assertRaisesRegex(ValueError, "failed request"):
                client._create_completion("dialogue_turn", request="failure")
            release.set()
            thread.join(1)
            self.assertEqual(completed, ["ok"])
            self.assertFalse(client.enabled)
            self.assertEqual(client._last_error, client._public_error_message(ValueError()))
        finally:
            release.set()
            thread.join(1)

    def test_invalid_settings_fall_back_and_workers_are_bounded(self) -> None:
        client = self.make_client(
            DEEPSEEK_TIMEOUT_SECONDS="NaN",
            DEEPSEEK_HARD_TIMEOUT_SECONDS="not-a-number",
            DEEPSEEK_DIALOGUE_WORKERS="100000",
            DEEPSEEK_BACKGROUND_WORKERS="-1",
        )
        self.assertEqual(client.timeout_seconds, 8)
        self.assertEqual(client.hard_timeout_seconds, 10)
        self.assertEqual(client.dialogue_workers, 8)
        self.assertEqual(client.background_workers, 1)


if __name__ == "__main__":
    unittest.main()
