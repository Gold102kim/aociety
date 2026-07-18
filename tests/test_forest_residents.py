from __future__ import annotations

import os
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
from services.forest_residents import ForestResidentService


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

        first = service.chat(npc_id="npc_01", live_event="今天天气怎么样？")
        second = service.chat(npc_id="npc_01", live_event="你还记得刚才的话吗？")

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
        )
        service.chat(npc_id="npc_02", live_event="你刚刚听到了什么？")

        self.assertEqual(first["mode"], "ambient")
        self.assertEqual(first["counterpart_id"], "npc_02")
        heard = ark.payloads[1]["recent_dialogue"]
        self.assertEqual(heard[-1]["heard_reply"], "小樱，早上好。")

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
        client._dialogue_executor.shutdown(wait=False)
        client._background_executor.shutdown(wait=False)

    def test_forest_system_prompt_contains_no_legacy_world_terms(self) -> None:
        client = object.__new__(ArkClient)
        client._client = object()
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
