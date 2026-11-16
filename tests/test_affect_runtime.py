from __future__ import annotations

from backend.affect_runtime import AffectRuntime


def test_latest_packet_defaults_to_degraded_unknown() -> None:
    runtime = AffectRuntime(window_ms=10_000)
    packet = runtime.latest_packet()
    assert packet["emotion"] == "unknown"
    assert packet["degraded"] is True
    assert packet["support_need"] == 0.0


def test_update_clamps_values_and_becomes_latest() -> None:
    runtime = AffectRuntime(window_ms=10_000)
    packet = runtime.update(
        timestamp_ms=1_000,
        emotion="sad",
        valence=-3.0,
        arousal=7.0,
        confidence_gap=0.5,
        top_candidates=[],
        source_models={"emotion": "test"},
        degraded=False,
    )
    assert 0.0 <= packet["valence"] <= 1.0
    assert 0.0 <= packet["arousal"] <= 1.0
    assert 0.0 <= packet["support_need"] <= 1.0
    assert packet["status"] == "ok"
    assert runtime.latest_packet()["timestamp_ms"] == 1_000


def test_negative_trend_raises_support_need() -> None:
    runtime = AffectRuntime(window_ms=10_000)
    common = dict(top_candidates=[], source_models={}, degraded=False, confidence_gap=0.8)
    calm = runtime.update(timestamp_ms=1_000, emotion="neutral", valence=0.8, arousal=0.2, **common)
    worse = runtime.update(timestamp_ms=2_000, emotion="neutral", valence=0.2, arousal=0.3, **common)
    assert worse["support_need"] > calm["support_need"]
    assert worse["trend"]["label"] == "downward_negative"
    assert worse["trend"]["valence_delta"] < 0
