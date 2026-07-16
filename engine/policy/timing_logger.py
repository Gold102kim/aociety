"""TimingLogger - records every intervention decision for future model training."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class TimingLogger:
    def __init__(self, log_dir: str = "logs/timing") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._buffer: List[Dict[str, Any]] = []
        self._flush_interval = 20

    def log_intervention(
        self,
        *,
        emotion: str = "",
        arousal: float = 0.0,
        valence: float = 0.0,
        support_need: float = 0.0,
        fuse_score: float = 0.0,
        arousal_trend: float = 0.0,
        emotion_stability: float = 1.0,
        trend_label: str = "stable",
        confidence_gap: float = 0.0,
        personality: Optional[Dict[str, float]] = None,
        rule_decision: str = "RECORD_ONLY",
        llm_decision: Optional[str] = None,
        llm_reason: str = "",
        llm_confidence: float = 0.0,
        final_decision: str = "RECORD_ONLY",
        user_response: Optional[str] = None,
    ) -> None:
        entry = {
            "timestamp": time.time(),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "emotion": emotion,
            "arousal": round(arousal, 4),
            "valence": round(valence, 4),
            "support_need": round(support_need, 4),
            "fuse_score": round(fuse_score, 4),
            "arousal_trend": round(arousal_trend, 4),
            "emotion_stability": round(emotion_stability, 4),
            "trend_label": trend_label,
            "confidence_gap": round(confidence_gap, 4),
            "personality": personality or {},
            "rule_decision": rule_decision,
            "llm_decision": llm_decision,
            "llm_reason": llm_reason,
            "llm_confidence": round(llm_confidence, 4),
            "final_decision": final_decision,
            "user_response": user_response,
        }
        self._buffer.append(entry)
        if len(self._buffer) >= self._flush_interval:
            self._flush()

    def update_user_response(self, timestamp: float, response: str) -> None:
        entry = {
            "timestamp": time.time(),
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event": "user_response",
            "original_timestamp": timestamp,
            "user_response": response,
        }
        self._buffer.append(entry)
        if len(self._buffer) >= self._flush_interval:
            self._flush()

    def _flush(self) -> None:
        if not self._buffer:
            return
        today = time.strftime("%Y%m%d")
        filepath = self.log_dir / f"timing_{today}.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            for entry in self._buffer:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._buffer.clear()

    def export_training_csv(self, output_path: Optional[str] = None) -> str:
        import csv
        out = output_path or str(self.log_dir / "timing_training_data.csv")
        rows = []
        for fp in sorted(self.log_dir.glob("timing_*.jsonl")):
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    if entry.get("event") == "user_response":
                        continue
                    if entry.get("user_response") is None:
                        continue
                    personality = entry.get("personality", {})
                    accepted = 1 if entry["user_response"] == "accepted" else 0
                    rows.append({
                        "arousal": entry.get("arousal", 0.0),
                        "support_need": entry.get("support_need", 0.0),
                        "arousal_trend": entry.get("arousal_trend", 0.0),
                        "emotion_stability": entry.get("emotion_stability", 1.0),
                        "Fe": personality.get("Fe", 0.0),
                        "Fi": personality.get("Fi", 0.0),
                        "fuse_score": entry.get("fuse_score", 0.0),
                        "accepted": accepted,
                    })
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "arousal", "support_need", "arousal_trend",
                "emotion_stability", "Fe", "Fi", "fuse_score", "accepted",
            ])
            writer.writeheader()
            writer.writerows(rows)
        return out

    def flush(self) -> None:
        self._flush()
