"""Domain-level recommendation engine.

This module performs horizon-based weighted scoring combining fundamental,
technical, and sentiment components. It is pure logic: callers must supply
already-computed sub-scores (0-100) and optional reason lists.
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Weight configuration (could be externalized later)
WEIGHTS: Dict[str, Dict[str, float]] = {
    "short": {"technical": 0.80, "sentiment": 0.20, "fundamental": 0.0},
    "medium": {"fundamental": 0.55, "technical": 0.35, "sentiment": 0.10},
    "long": {"fundamental": 0.80, "technical": 0.20, "sentiment": 0.0},
}

RATING_THRESHOLDS: List[Tuple[float, str]] = [
    (70.0, "buy"),
    (40.0, "hold"),
    (0.0, "sell"),  # fallback
]

@dataclass(slots=True)
class ComponentScores:
    fundamental: float
    technical: float
    sentiment: float


def compute_weighted_score(horizon: str, scores: ComponentScores) -> float:
    """Compute weighted composite score for a horizon.

    Args:
        horizon: one of 'short','medium','long'
        scores: component sub-scores (0-100)
    Returns:
        Weighted composite 0-100
    """
    conf = WEIGHTS[horizon]
    return (
        scores.fundamental * conf.get("fundamental", 0.0)
        + scores.technical * conf.get("technical", 0.0)
        + scores.sentiment * conf.get("sentiment", 0.0)
    )


def derive_rating(composite: float) -> str:
    """Map composite score to rating string using thresholds."""
    for threshold, label in RATING_THRESHOLDS:
        if composite >= threshold:
            return label
    return "sell"


def build_recommendation_detail(
    horizon: str,
    scores: ComponentScores,
    reasons: List[str],
) -> Dict[str, object]:
    """Produce a simple serializable dict for a horizon recommendation."""
    composite = compute_weighted_score(horizon, scores)
    rating = derive_rating(composite)
    return {
        "horizon": horizon,
        "rating": rating,
        "score": round(composite, 2),
        "reasons": reasons,
    }
