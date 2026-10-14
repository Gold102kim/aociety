from __future__ import annotations

import os
import importlib
import json
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.ark_client import (
    ArkClient,
    DEEPSEEK_MODEL_ID,
    DEEPSEEK_PROVIDER,
    FOREST_LEGACY_TERMS,
    THINKING_DISABLED_BODY,
)
from services.forest_residents import (
    ForestResidentService,
    MAX_HISTORY_TURNS,
    MAX_HISTORY_TEXT_CHARS,
)

SCOPE_A = "a" * 32
SCOPE_B = "b" * 32


class FakeArk:
    model_id = DEEPSEEK_MODEL_ID

    def __init__(self, replies: list[dict[str, str] | None]) -> None:
        self.replies = list(replies)
        self.payloads: list[dict[str, object]] = []

    def generate_forest_resident_reply(
        self, payload: dict[str, object]
    ) -> dict[str, str] | None:
        self.payloads.append(payload)
        return self.replies.pop(0)


def llm_reply(text: str, mood: str = "平静") -> dict[str, str]:
    return {
        "reply": text,
        "mood": mood,
        "_meta_source": "llm",
        "_meta_model": DEEPSEEK_MODEL_ID,
        "_meta_provider": DEEPSEEK_PROVIDER,
    }


class TestForestResidentService(unittest.TestCase):
    def test_player_turn_uses_verified_llm_and_short_term_memory(self) -> None:
        ark = FakeArk([llm_reply("今天林间的风很轻。"), llm_reply("我记得你刚才问过天气。")])
        service = ForestResidentService(ark)  # type: ignore[arg-type]

        first = service.chat(npc_id="npc_01", live_event="今天天气怎么样？", conversation_scope=SCOPE_A)
        second = service.chat(npc_id="npc_01", live_event="你还记得刚才的话吗？", conversation_scope=SCOPE_A)

        self.assertEqual(first["source"], "llm")
        self.assertEqual(first["provider"], DEEPSEEK_PROVIDER)
        self.assertEqual(first["model"], DEEPSEEK_MODEL_ID)
        self.assertEqual(second["dialogue"]["source"], "llm")
        recent = ark.payloads[1]["recent_dialogue"]
        self.assertEqual(recent[-1]["reply"], "今天林间的风很轻。")

    def test_ambient_turn_is_added_to_counterpart_memory(self) -> None:
        ark = FakeArk([llm_reply("小樱，早上好。"), llm_reply("早上好，我正要去照看花草。")])
        service = ForestResidentService(ark)  # type: ignore[arg-type]

        first = service.chat(
            npc_id="npc_01",
            counterpart_id="npc_02",
            mode="ambient",
            live_event="你在小路上遇到了小樱。",
            conversation_scope=SCOPE_A,
        )
        service.chat(npc_id="npc_02", live_event="你刚刚听到了什么？", conversation_scope=SCOPE_A)

        self.assertEqual(first["mode"], "ambient")
        self.assertEqual(first["counterpart_id"], "npc_02")
        heard = ark.payloads[1]["recent_dialogue"]
        self.assertEqual(heard[-1]["heard_reply"], "小樱，早上好。")

    def test_random_game_scopes_do_not_share_player_context(self) -> None:
        ark = FakeArk([llm_reply("A_PRIVATE_REPLY"), llm_reply("B_REPLY"), llm_reply("A_REPLY")])
        service = ForestResidentService(ark)  # type: ignore[arg-type]
        service.chat(npc_id="npc_01", live_event="ACCOUNT_A_PRIVATE_SENTINEL", conversation_scope=SCOPE_A)
        service.chat(npc_id="npc_01", live_event="Account B starts a new game", conversation_scope=SCOPE_B)
        service.chat(npc_id="npc_01", live_event="Account A continues", conversation_scope=SCOPE_A)
        self.assertEqual(ark.payloads[1]["recent_dialogue"], [])
        self.assertEqual(ark.payloads[1]["counterpart_recent_dialogue"], [])
        self.assertNotIn("ACCOUNT_A_PRIVATE_SENTINEL", json.dumps(ark.payloads[1]))
        self.assertNotIn("A_PRIVATE_REPLY", json.dumps(ark.payloads[1]))
        self.assertEqual(ark.payloads[2]["recent_dialogue"][-1]["event"], "ACCOUNT_A_PRIVATE_SENTINEL")
        self.assertNotIn("B_REPLY", json.dumps(ark.payloads[2]))

    def test_ambient_memory_is_consistent_only_inside_one_game_scope(self) -> None:
        ark = FakeArk([llm_reply("A_AMBIENT_REPLY"), llm_reply("B_REPLY"), llm_reply("A_REPLY")])
        service = ForestResidentService(ark)  # type: ignore[arg-type]
        service.chat(npc_id="npc_01", counterpart_id="npc_02", mode="ambient", live_event="A_AMBIENT_SENTINEL", conversation_scope=SCOPE_A)
        service.chat(npc_id="npc_02", live_event="New game B", conversation_scope=SCOPE_B)
        service.chat(npc_id="npc_02", live_event="Same game A", conversation_scope=SCOPE_A)
        self.assertEqual(ark.payloads[1]["recent_dialogue"], [])
        self.assertNotIn("A_AMBIENT_SENTINEL", json.dumps(ark.payloads[1]))
        self.assertEqual(ark.payloads[2]["recent_dialogue"][-1]["heard_reply"], "A_AMBIENT_REPLY")

    def test_missing_or_invalid_scope_is_stateless_even_after_scoped_chat(self) -> None:
        ark = FakeArk([llm_reply("Scoped reply")] + [llm_reply("Stateless reply")] * 5)
        service = ForestResidentService(ark)  # type: ignore[arg-type]
        service.chat(npc_id="npc_01", live_event="PRIVATE_SCOPED_EVENT", conversation_scope=SCOPE_A)
        for scope in ("", "", "../invalid", "z" * 32, "a" * 1000):
            service.chat(npc_id="npc_01", live_event="UNSCOPED_SENTINEL", conversation_scope=scope)
            self.assertEqual(ark.payloads[-1]["recent_dialogue"], [])
            self.assertEqual(ark.payloads[-1]["counterpart_recent_dialogue"], [])
            self.assertNotIn("PRIVATE_SCOPED_EVENT", json.dumps(ark.payloads[-1]))
        self.assertEqual(len(service._history), 1)
        self.assertNotIn("UNSCOPED_SENTINEL", json.dumps(service._history))

    def test_scope_lru_and_turn_text_limits_bound_memory(self) -> None:
        ark = FakeArk([llm_reply("Reply")] * 4 + [llm_reply("R" * 5000)] * (MAX_HISTORY_TURNS + 3))
        service = ForestResidentService(ark)  # type: ignore[arg-type]
        with patch("services.forest_residents.MAX_CONVERSATION_SCOPES", 2):
            for scope in (SCOPE_A, SCOPE_B, "c" * 32, SCOPE_A):
                service.chat(npc_id="npc_01", live_event="LRU turn", conversation_scope=scope)
                self.assertLessEqual(len(service._history), 2)
            self.assertEqual(ark.payloads[3]["recent_dialogue"], [], "Evicted old context must not be restored.")
            for _ in range(MAX_HISTORY_TURNS + 3):
                service.chat(npc_id="npc_01", live_event="E" * 5000, conversation_scope=SCOPE_A)
        history = service._history[SCOPE_A]["npc_01"]
        self.assertEqual(len(history), MAX_HISTORY_TURNS)
        self.assertTrue(all(len(turn["event"]) <= MAX_HISTORY_TEXT_CHARS and len(turn["reply"]) <= MAX_HISTORY_TEXT_CHARS for turn in history))

    def test_late_reply_cannot_recreate_or_mutate_an_evicted_scope(self) -> None:
        started, release = threading.Event(), threading.Event()

        class BlockingArk:
            model_id = DEEPSEEK_MODEL_ID

            def generate_forest_resident_reply(self, payload):
                if payload["live_event"] == "OLD_INFLIGHT_SENTINEL":
                    started.set()
                    release.wait(2)
                    return llm_reply("OLD_INFLIGHT_REPLY")
                return llm_reply("Fresh reply")

        service = ForestResidentService(BlockingArk())  # type: ignore[arg-type]
        failures = []

        def old_request():
            try:
                service.chat(npc_id="npc_01", live_event="OLD_INFLIGHT_SENTINEL", conversation_scope=SCOPE_A)
            except Exception as error:
                failures.append(error)

        with patch("services.forest_residents.MAX_CONVERSATION_SCOPES", 1):
            worker = threading.Thread(target=old_request)
            worker.start()
            try:
                self.assertTrue(started.wait(1))
                service.chat(npc_id="npc_01", live_event="Evict A with B", conversation_scope=SCOPE_B)
                service.chat(npc_id="npc_01", live_event="FRESH_A_EVENT", conversation_scope=SCOPE_A)
            finally:
                release.set()
                worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(service._history), 1)
        self.assertEqual(service._history[SCOPE_A]["npc_01"][-1]["event"], "FRESH_A_EVENT")
        self.assertNotIn("OLD_INFLIGHT_SENTINEL", json.dumps(service._history))

    def test_failure_is_never_reported_as_llm(self) -> None:
        service = ForestResidentService(FakeArk([None]))  # type: ignore[arg-type]

        result = service.chat(npc_id="npc_01", live_event="你好")

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["error_code"], "llm_unavailable")
        self.assertEqual(result["dialogue"]["source"], "error")

    def test_unverified_generated_text_is_rejected(self) -> None:
        fake_rule_reply = {"reply": "欢迎来到小镇。", "mood": "平静"}
        service = ForestResidentService(FakeArk([fake_rule_reply]))  # type: ignore[arg-type]

        result = service.chat(npc_id="npc_01", live_event="你好")

        self.assertEqual(result["source"], "error")

    def test_wrong_provider_or_model_is_rejected(self) -> None:
        wrong_provider = llm_reply("今天适合散步。")
        wrong_provider["_meta_provider"] = "tokenhub"
        wrong_model = llm_reply("我正准备去看花草。")
        wrong_model["_meta_model"] = "glm-5.2"
        service = ForestResidentService(  # type: ignore[arg-type]
            FakeArk([wrong_provider, wrong_model])
        )

        provider_result = service.chat(npc_id="npc_01", live_event="你好")
        model_result = service.chat(npc_id="npc_02", live_event="早上好")

        self.assertEqual(provider_result["source"], "error")
        self.assertEqual(model_result["source"], "error")

    def test_verified_metadata_cannot_bypass_legacy_story_filter(self) -> None:
        service = ForestResidentService(  # type: ignore[arg-type]
            FakeArk([llm_reply("我刚从海藻重工回来。")])
        )

        result = service.chat(npc_id="npc_01", live_event="你刚才去了哪里？")

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["error_code"], "llm_unavailable")

    def test_scene_context_is_allowlisted(self) -> None:
        ark = FakeArk([llm_reply("我看见你走近了。")])
        service = ForestResidentService(ark)  # type: ignore[arg-type]

        service.chat(
            npc_id="npc_01",
            live_event="你好",
            scene={
                "location": "forest_town",
                "player_position": {"x": 1, "y": 2, "z": 3},
                "district": "legacy_market",
                "market_state": {"price": 99},
            },
        )

        scene = ark.payloads[0]["scene"]
        self.assertEqual(scene["location"], "森林小镇的住宅与林间小路")
        self.assertIn("player_position", scene)
        self.assertNotIn("district", scene)
        self.assertNotIn("market_state", scene)


class TestArkClientRoute(unittest.TestCase):
    def test_legacy_environment_keys_cannot_reroute_residents(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TOKENHUB_API_KEY": "legacy-tokenhub-key",
                "TOKENHUB_BASE_URL": "https://api.tokenhub.market/v1",
                "TOKENHUB_MODEL": "glm-5.2",
                "GLM_API_KEY": "legacy-glm-key",
                "OPENAI_API_KEY": "legacy-openai-key",
                "ANTHROPIC_API_KEY": "legacy-anthropic-key",
                "GLM_BASE_URL": "https://legacy.invalid/v1",
                "GLM_MODEL_ID": "legacy-model",
            },
            clear=True,
        ):
            client = ArkClient()

        self.assertEqual(client.api_key, "")
        self.assertEqual(client.base_url, "https://api.deepseek.com/")
        self.assertEqual(client.model_id, DEEPSEEK_MODEL_ID)
        self.assertEqual(client.provider, DEEPSEEK_PROVIDER)
        self.assertFalse(client.configured)
        client.close()

    def test_forest_system_prompt_contains_no_legacy_world_terms(self) -> None:
        client = object.__new__(ArkClient)
        client._client = object()
        client._closed = False
        client._disabled_until = 0.0
        client.model_id = DEEPSEEK_MODEL_ID
        client.provider = DEEPSEEK_PROVIDER
        captured: dict[str, object] = {}

        def fake_completion(**kwargs: object) -> object:
            captured.update(kwargs)
            message = SimpleNamespace(
                content='{"reply":"今天适合沿着林间小路散步。","mood":"平静"}'
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        client._create_completion = fake_completion
        result = client.generate_forest_resident_reply(
            {
                "resident": {"name": "林汐", "personality": "安静温和"},
                "mode": "player_interaction",
                "live_event": "玩家走近并打了招呼。",
                "scene": {"location": "森林小镇"},
                "recent_dialogue": [],
                "request_nonce": "test-turn",
            }
        )

        system_prompt = captured["messages"][0]["content"]
        for term in FOREST_LEGACY_TERMS:
            self.assertNotIn(term, system_prompt)
        self.assertEqual(result["_meta_source"], "llm")
        self.assertEqual(result["_meta_provider"], DEEPSEEK_PROVIDER)
        self.assertEqual(result["_meta_model"], DEEPSEEK_MODEL_ID)
        self.assertEqual(captured["extra_body"], THINKING_DISABLED_BODY)


if __name__ == "__main__":
    unittest.main()
