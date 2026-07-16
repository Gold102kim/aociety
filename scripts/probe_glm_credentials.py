"""Probe project-local GLM credentials without printing credential values."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent


def load_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_handover_candidates() -> dict[str, str]:
    handover_path = ROOT / "HANDOVER.md"
    if not handover_path.exists():
        return {}
    text = handover_path.read_text(encoding="utf-8-sig")
    candidates: dict[str, str] = {}
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "BIGMODEL_API_KEY"):
        matches = re.findall(rf"(?m)^\s*{key}=([^\s#]+)", text)
        for index, value in enumerate(matches, start=1):
            candidates[f"handover_{key}_{index}"] = value
    return candidates


def response_summary(response: httpx.Response) -> dict[str, object]:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = {"text": response.text[:160]}
    if response.status_code == 200:
        return {"status": 200, "ok": True}
    error = payload.get("error", payload) if isinstance(payload, dict) else payload
    if isinstance(error, dict):
        message = str(error.get("message", ""))[:160]
        error_type = str(error.get("type", error.get("code", "")))[:80]
    else:
        message = str(error)[:160]
        error_type = ""
    return {
        "status": response.status_code,
        "ok": False,
        "error_type": error_type,
        "message": message,
    }


def probe_openai(client: httpx.Client, key: str) -> dict[str, object]:
    response = client.post(
        "https://api.tokenhub.market/v1/chat/completions",
        headers={"authorization": f"Bearer {key}"},
        json={
            "model": "glm-5.2",
            "max_tokens": 8,
            "messages": [{"role": "user", "content": "只返回 OK"}],
        },
    )
    return response_summary(response)


def probe_anthropic(client: httpx.Client, key: str) -> dict[str, object]:
    response = client.post(
        "https://api.tokenhub.market/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "glm-5.2",
            "max_tokens": 8,
            "messages": [{"role": "user", "content": "只返回 OK"}],
        },
    )
    return response_summary(response)


def main() -> None:
    env = load_dotenv()
    raw_candidates = {
        "env_ANTHROPIC_API_KEY": env.get("ANTHROPIC_API_KEY", ""),
        "env_OPENAI_API_KEY": env.get("OPENAI_API_KEY", ""),
        "env_GLM_API_KEY": env.get("GLM_API_KEY", ""),
        **load_handover_candidates(),
    }
    grouped: dict[str, list[str]] = {}
    for label, value in raw_candidates.items():
        if value:
            grouped.setdefault(value, []).append(label)

    output: list[dict[str, object]] = []
    with httpx.Client(timeout=20.0) as client:
        for value, labels in grouped.items():
            fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
            item: dict[str, object] = {
                "labels": labels,
                "length": len(value),
                "fingerprint": fingerprint,
            }
            for name, probe in (("openai", probe_openai), ("anthropic", probe_anthropic)):
                try:
                    item[name] = probe(client, value)
                except Exception as exc:
                    item[name] = {"ok": False, "exception": str(exc)[:180]}
            output.append(item)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
