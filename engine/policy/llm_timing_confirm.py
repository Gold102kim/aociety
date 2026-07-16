"""LLM Timing Confirm - connects care_policy to the LLM for timing judgment.

This module provides the callable that CarePolicy.set_llm_timing_confirm() expects.
It constructs the timing check prompt, sends it to the configured LLM,
and parses the JSON response.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def make_llm_timing_confirm(
    llm_call_fn: Callable[[str], str],
    max_retries: int = 1,
) -> Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Create an LLM timing confirmation function.

    Args:
        llm_call_fn: takes prompt string, returns LLM text response.
        max_retries: retries on parse failure.

    Returns:
        A function compatible with CarePolicy.set_llm_timing_confirm().
    """

    def confirm(prompt_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        prompt_text = prompt_data.get("timing_check_prompt", "")
        if not prompt_text:
            return None

        for attempt in range(max_retries + 1):
            try:
                raw_response = llm_call_fn(prompt_text)
                result = _parse_llm_json(raw_response)
                if result is not None:
                    if "should_intervene" in result:
                        result["should_intervene"] = bool(result["should_intervene"])
                    if "confidence" in result:
                        result["confidence"] = float(result["confidence"])
                    if "suggested_level" in result:
                        level = str(result["suggested_level"]).strip().lower()
                        if level not in ("nudge", "care", "guard"):
                            level = "nudge"
                        result["suggested_level"] = level
                    return result
            except Exception as e:
                logger.warning(f"LLM timing confirm attempt {attempt} failed: {e}")
                continue
        return None

    return confirm


def _parse_llm_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from LLM response text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    match2 = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match2:
        try:
            return json.loads(match2.group(0))
        except json.JSONDecodeError:
            pass
    return None
