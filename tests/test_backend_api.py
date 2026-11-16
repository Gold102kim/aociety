"""HTTP/WebSocket contract tests for backend/main.py.

Model clients and TTS are replaced with fakes so the suite runs offline and
without API keys. Known bugs are pinned with strict xfail markers: when a bug
is fixed the xfail turns into a failure, prompting removal of the marker.
"""

from __future__ import annotations

import base64
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.affect_runtime import AffectRuntime


class FakeCareClient:
    def __init__(self, enabled: bool = False, reply: dict[str, Any] | None = None) -> None:
        self.enabled = enabled
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    def generate_care_dialogue(self, **kwargs: Any) -> dict[str, Any] | None:
        self.calls.append(kwargs)
        return self.reply

    def probe(self) -> dict[str, Any]:
        return {"ok": False, "source": "fake"}


class FakeEmotionModel:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.enabled = result is not None
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def analyze_emotion(self, **kwargs: Any) -> dict[str, Any] | None:
        self.calls.append(kwargs)
        return self.result


class FakeTTS:
    voice_name = "xiaoxiao"

    def __init__(self, audio: bytes = b"") -> None:
        self.audio = audio
        self.texts: list[str] = []

    def list_voices(self) -> list[dict[str, Any]]:
        return main.TTSService.list_voices()

    def set_voice(self, voice_name: str) -> bool:
        if voice_name in main.SWEET_VOICES:
            self.voice_name = voice_name
            return True
        return False

    def synthesize(self, text: str) -> bytes:
        self.texts.append(text)
        return self.audio


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    care = FakeCareClient()
    emotion = FakeEmotionModel()
    tts = FakeTTS()
    monkeypatch.setattr(main, "npc_glm", care)
    monkeypatch.setattr(main, "glm_emotion", emotion)
    monkeypatch.setattr(main, "tts_service", tts)
    monkeypatch.setattr(main, "affect_runtime", AffectRuntime(window_ms=10_000))
    monkeypatch.setattr(main, "openclaw", main.SimpleMemoryStore())
    monkeypatch.setattr(main, "_assessment_sessions", {})
    monkeypatch.setattr(main, "ENABLE_EMOTION", True)
    return {"care": care, "emotion": emotion, "tts": tts}


@pytest.fixture
def client(fakes: dict[str, Any]) -> Iterator[TestClient]:
    with TestClient(main.app) as test_client:
        yield test_client


def _push_affect(support_emotion: str, valence: float, arousal: float) -> dict[str, Any]:
    return main.affect_runtime.update(
        timestamp_ms=1_000,
        emotion=support_emotion,
        valence=valence,
        arousal=arousal,
        confidence_gap=0.2,
        top_candidates=[],
        source_models={},
        degraded=False,
    )


# ── health ────────────────────────────────────────────────────────────


def test_health_reports_flags(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["glm_enabled"] is False
    assert body["world_glm_enabled"] is False


# ── emotion ───────────────────────────────────────────────────────────


def test_emotion_state_defaults_to_degraded(client: TestClient) -> None:
    body = client.get("/emotion/state").json()
    assert body["emotion"] == "unknown"
    assert body["degraded"] is True


def test_analyze_uses_model_result_when_available(client: TestClient, fakes: dict[str, Any]) -> None:
    fakes["emotion"].result = {"emotion": "sad", "valence": 0.2, "arousal": 0.6, "confidence": 0.7}

    body = client.post("/emotion/analyze", json={"text_hint": "今天好累", "timestamp_ms": 5_000}).json()

    assert fakes["emotion"].calls[0]["text_hint"] == "今天好累"
    assert body["emotion"] == "sadness"  # AffectRuntime normalizes labels.
    assert body["degraded"] is False
    assert client.get("/emotion/state").json()["timestamp_ms"] == 5_000


def test_analyze_falls_back_to_local_packet_without_model(client: TestClient) -> None:
    response = client.post("/emotion/analyze", json={"text_hint": "你好"})
    assert response.status_code == 200
    body = response.json()
    assert set(main.EmotionOut.model_fields) <= set(body)


def test_analyze_returns_degraded_when_emotion_disabled(
    client: TestClient, fakes: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main, "ENABLE_EMOTION", False)
    body = client.post("/emotion/analyze", json={"text_hint": "x"}).json()
    assert body["degraded"] is True
    assert fakes["emotion"].calls == []


@pytest.mark.xfail(strict=True, reason="BUG: /emotion/reset rebinds a local variable and never clears global state")
def test_emotion_reset_clears_state(client: TestClient) -> None:
    _push_affect("sad", 0.1, 0.8)
    client.post("/emotion/reset")
    assert client.get("/emotion/state").json()["emotion"] == "unknown"


@pytest.mark.parametrize(
    ("support", "action", "level"),
    [
        (0.9, "offer_seat", "guard"),
        (0.7, "speak_kindly", "care"),
        (0.5, "offer_food", "nudge"),
        (0.1, "none", "nudge"),
    ],
)
def test_rule_based_care_thresholds(support: float, action: str, level: str) -> None:
    care = main._rule_based_care({"support_need": support}, {})
    assert care.action == action
    assert care.care_level == level


def test_care_uses_rules_when_model_disabled(client: TestClient, fakes: dict[str, Any]) -> None:
    body = client.post("/emotion/care", json={"npc_id": "nobody"}).json()
    assert body["action"] == "none"
    assert fakes["care"].calls == []


def test_care_prefers_model_reply_and_passes_npc_profile(client: TestClient, fakes: dict[str, Any]) -> None:
    npc = main.world_engine.state["npcs"][0]
    fakes["care"].enabled = True
    fakes["care"].reply = {"npc_line": "要喝点热水吗？", "action": "offer_drink", "care_level": "care"}

    body = client.post("/emotion/care", json={"npc_id": npc["id"]}).json()

    assert body["npc_line"] == "要喝点热水吗？"
    assert fakes["care"].calls[0]["npc_profile"]["id"] == npc["id"]


def test_care_with_voice_attaches_audio(client: TestClient, fakes: dict[str, Any]) -> None:
    fakes["tts"].audio = b"ID3-fake-mp3"
    _push_affect("sad", 0.0, 1.0)

    body = client.post("/emotion/care_with_voice", json={"npc_id": ""}).json()

    assert body["npc_line"]
    assert base64.b64decode(body["audio_base64"]) == b"ID3-fake-mp3"
    assert fakes["tts"].texts == [body["npc_line"]]


def test_care_with_voice_skips_tts_for_empty_line(client: TestClient, fakes: dict[str, Any]) -> None:
    body = client.post("/emotion/care_with_voice", json={"npc_id": ""}).json()
    assert body["npc_line"] == ""
    assert fakes["tts"].texts == []


# ── TTS ───────────────────────────────────────────────────────────────


def test_tts_voice_listing_and_switching(client: TestClient) -> None:
    voices = client.get("/tts/voices").json()
    assert any(v["id"] == "xiaoxiao" for v in voices["voices"])

    assert client.post("/tts/voices/xiaoyi").json() == {"status": "ok", "current": "xiaoyi"}
    assert "error" in client.post("/tts/voices/not-a-voice").json()


def test_tts_synthesize_encodes_audio(client: TestClient, fakes: dict[str, Any]) -> None:
    fakes["tts"].audio = b"\x00\x01mp3"
    body = client.post("/tts/synthesize", json={"text": "你好"}).json()
    assert base64.b64decode(body["audio_base64"]) == b"\x00\x01mp3"
    assert body["voice_name_cn"] == "晓晓"


def test_tts_synthesize_without_engine_returns_estimate(client: TestClient) -> None:
    body = client.post("/tts/synthesize", json={"text": "你好呀"}).json()
    assert body["audio_base64"] == ""
    assert body["duration_estimate"] == pytest.approx(0.45)


# ── assessment ────────────────────────────────────────────────────────


def test_assessment_start_state_and_finish(client: TestClient) -> None:
    session_id = client.post("/assessment/start").json()["session_id"]
    assert session_id

    state = client.get(f"/assessment/state/{session_id}").json()
    assert state["progress"] == 0
    assert state["turns"] == 0

    profile = client.post(f"/assessment/finish/{session_id}").json()["profile"]
    assert profile["assessment_ready"] is False


def test_assessment_unknown_session(client: TestClient) -> None:
    assert client.post("/assessment/turn", params={"session_id": "missing"}).json() == {"error": "session not found"}
    assert client.post("/assessment/finish/missing").json() == {"error": "session not found"}


@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="BUG: /assessment/turn calls merge_scoring/compute_dimension_confidence with outdated signatures",
)
def test_assessment_turn_advances_session(client: TestClient) -> None:
    session_id = client.post("/assessment/start").json()["session_id"]
    body = client.post("/assessment/turn", params={"session_id": session_id, "player_input": "慢慢说就好"}).json()
    assert body["finished"] is False


# ── memory ────────────────────────────────────────────────────────────


def test_memory_store_and_search(client: TestClient) -> None:
    client.post("/memory/store", params={"key": "pref:drink", "value": "喜欢热可可"})
    client.post("/memory/store", params={"key": "pref:color", "value": "蓝色"})

    results = client.get("/memory/search", params={"query": "可可"}).json()["results"]
    assert [r["key"] for r in results] == ["pref:drink"]
    assert len(client.get("/memory/search", params={"query": "pref", "limit": 1}).json()["results"]) == 1


# ── world / NPC ───────────────────────────────────────────────────────


def test_npc_list_and_detail(client: TestClient) -> None:
    npcs = client.get("/npc/list").json()["npcs"]
    assert npcs
    first = npcs[0]
    assert client.get(f"/npc/{first['id']}").json()["npc"]["id"] == first["id"]
    assert client.get("/npc/does-not-exist").json() == {"error": "NPC not found"}


def test_world_state_and_reset(client: TestClient) -> None:
    assert isinstance(client.get("/world/state").json()["world_state"], dict)
    body = client.post("/world/reset").json()
    assert body["message"]
    assert isinstance(body["world_state"], dict)


def test_player_talk_unknown_npc(client: TestClient) -> None:
    body = client.post("/npc/player_talk", json={"npc_id": "does-not-exist"}).json()
    assert body["message"] == "你身边没有这个角色。"


def test_ai_probe_uses_world_client(client: TestClient) -> None:
    assert client.get("/ai/probe").json() == {"ok": False, "source": "fake"}


def test_world_websocket_returns_state(client: TestClient) -> None:
    with client.websocket_connect("/ws/world") as ws:
        ws.send_json({"type": "get_state"})
        message = ws.receive_json()
    assert message["type"] == "world_state"
    assert isinstance(message["data"], dict)


def test_emotion_websocket_returns_packet(client: TestClient) -> None:
    with client.websocket_connect("/ws/emotion") as ws:
        ws.send_json({"text_hint": "嗨", "timestamp_ms": 9_000})
        packet = ws.receive_json()
    assert "emotion" in packet
    assert "support_need" in packet
