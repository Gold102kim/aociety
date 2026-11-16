from __future__ import annotations

from backend import assessment_engine as ae


def test_parse_json_dict_handles_plain_wrapped_and_invalid_text() -> None:
    assert ae.parse_json_dict('{"a": 1}') == {"a": 1}
    assert ae.parse_json_dict('模型输出：{"a": 2} 以上') == {"a": 2}
    assert ae.parse_json_dict("[1, 2]") == {}
    assert ae.parse_json_dict("not json") == {}
    assert ae.parse_json_dict("") == {}


def test_normalize_scores_and_confidence_fill_all_keys_and_clamp() -> None:
    scores = ae.normalize_scores({"Se": "0.123456", "Ni": "bad"})
    assert set(scores) == set(ae.SCORE_KEYS)
    assert scores["Se"] == 0.1235
    assert scores["Ni"] == 0.0

    confidence = ae.normalize_confidence({"Te": 5, "Fi": -1})
    assert confidence["Te"] == 1.0
    assert confidence["Fi"] == 0.0


def test_select_next_question_walks_bank_then_repeats_last() -> None:
    bank_ids = [str(item["id"]) for item in ae.FALLBACK_QUESTION_BANK]

    first = ae.select_next_question({}, [], {})
    assert first["id"] == bank_ids[0]
    assert first["rationale"] == "fallback_sequence"

    second = ae.select_next_question({}, [bank_ids[0]], {})
    assert second["id"] == bank_ids[1]

    exhausted = ae.select_next_question({}, bank_ids, {})
    assert exhausted["id"] == bank_ids[-1]
    assert exhausted["rationale"] == "fallback_repeat"


def test_score_answer_heuristic_maps_focus_to_profile_updates() -> None:
    question = {"focus": "decision_style", "prompt": "你怎么做决定？"}
    result = ae.score_answer_heuristic(question, "  先想清楚再行动  ")
    assert result["effective"] is True
    assert result["profile_updates"]["decision_style"] == "先想清楚再行动"
    assert result["confidence"] > 0

    empty = ae.score_answer_heuristic(question, "   ")
    assert empty["effective"] is False
    assert empty["profile_updates"] == {}
    assert empty["confidence"] == 0.0


def test_should_finish_respects_min_turns_and_confidence() -> None:
    session = ae.build_initial_session(1_000)
    assert ae.should_finish(session) == (False, "min_turns")

    session["effective_turn_count"] = 4
    assert ae.should_finish(session) == (False, "need_more_signal")

    session["confidence"] = 0.9
    assert ae.should_finish(session) == (True, "stable_enough")

    session["confidence"] = 0.0
    session["effective_turn_count"] = 12
    assert ae.should_finish(session) == (False, "needs_follow_up")


def test_merge_scoring_accumulates_turns_and_profile() -> None:
    session = ae.build_initial_session(1_000)
    question = ae.select_next_question({}, [], {})
    scoring = ae.score_answer_heuristic(question, "温柔一点地问我")

    merged = ae.merge_scoring(session, question, "温柔一点地问我", scoring, 2_000)

    assert merged["turn_count"] == 1
    assert merged["effective_turn_count"] == 1
    assert merged["updated_at_ms"] == 2_000
    assert merged["interaction_preferences"] == ["温柔一点地问我"]
    assert merged["question_history"][-1]["question_id"] == question["id"]
    assert [turn["role"] for turn in merged["dialogue_turns"]] == ["assistant", "user"]
    assert merged["assessment_ready"] is False
    # The input session must not be mutated.
    assert session["turn_count"] == 0


def test_build_final_profile_reports_readiness() -> None:
    session = ae.build_initial_session(1_000)
    session["effective_turn_count"] = 5
    session["confidence"] = 0.9
    session["decision_style"] = "先想后做"

    profile = ae.build_final_profile(session)

    assert profile["assessment_ready"] is True
    assert profile["decision_style"] == "先想后做"
    assert profile["conversation_count"] == 5
    assert profile["completion_reason"] == "stable_enough"
