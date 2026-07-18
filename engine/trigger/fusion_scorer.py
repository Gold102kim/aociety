from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.config import FusionConfig


class FusionScorer:
    def __init__(self, config: FusionConfig) -> None:
        self.config = config

    def score(self, v: float, a: float, t: Optional[float]) -> float:
        """Original score: linear weighted fusion without personality or trend."""
        if t is None:
            denom = self.config.wV + self.config.wA
            if denom <= 0:
                return 0.0
            return (self.config.wV * v + self.config.wA * a) / denom
        return (
            self.config.wV * v
            + self.config.wA * a
            + self.config.wT * t
        )

    def score_with_context(
        self,
        v: float,
        a: float,
        t: Optional[float],
        *,
        personality: Optional[Dict[str, float]] = None,
        arousal_trend: float = 0.0,
        emotion_stability: float = 1.0,
        trend_label: str = "stable",
    ) -> float:
        """Enhanced fusion score with personality modulation and arousal trend.

        Personality modulation:
          - Fe (extraverted feeling) high => more receptive to care => boost score
          - Fi (introverted feeling) high => more self-contained => dampen score
          - If both are 0 (no assessment yet), no modulation applied

        Arousal trend:
          - arousal_trend > 0 => arousal rising => situation is escalating => boost
          - arousal_trend < 0 => arousal falling => situation de-escalating => slight dampen

        Emotion stability:
          - low stability (< 0.3) => emotion fluctuating => boost by small margin
        """
        base = self.score(v, a, t)

        # Personality modulation: scale base by receptivity factor
        if personality:
            fe = float(personality.get("Fe", 0.0))
            fi = float(personality.get("Fi", 0.0))
            if fe > 0 or fi > 0:
                # receptivity = 0.6 + 0.4*Fe when Fe>Fi; lower when Fi dominant
                if fe >= fi:
                    receptivity = 0.6 + 0.4 * min(fe, 1.0)
                else:
                    receptivity = 0.6 - 0.3 * min(fi - fe, 0.5)
                receptivity = max(0.3, min(1.2, receptivity))
                base = base * receptivity

        # Arousal trend: rising arousal => urgency boost
        if arousal_trend > 0.08:
            boost = 0.15 * min(arousal_trend, 0.5)
            base = base + boost

        # Low emotion stability => fluctuating state => slight urgency
        if emotion_stability < 0.3:
            base = base + 0.10 * (1.0 - emotion_stability)

        return max(0.0, min(1.0, base))
