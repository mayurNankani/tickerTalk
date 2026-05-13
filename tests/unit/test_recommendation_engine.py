"""Unit tests for the recommendation engine.

Run with: pytest tests/
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.analysis.recommendation_engine import (
    WEIGHTS,
    ComponentScores,
    build_recommendation_detail,
    compute_weighted_score,
    derive_rating,
)


class TestComputeWeightedScore:
    def test_short_term_ignores_fundamental(self):
        scores = ComponentScores(fundamental=100.0, technical=50.0, sentiment=50.0)
        result = compute_weighted_score("short", scores)
        expected = 50.0 * WEIGHTS["short"]["technical"] + 50.0 * WEIGHTS["short"]["sentiment"]
        assert abs(result - expected) < 1e-6

    def test_long_term_ignores_sentiment(self):
        scores = ComponentScores(fundamental=80.0, technical=60.0, sentiment=100.0)
        result = compute_weighted_score("long", scores)
        expected = 80.0 * WEIGHTS["long"]["fundamental"] + 60.0 * WEIGHTS["long"]["technical"]
        assert abs(result - expected) < 1e-6

    def test_weights_sum_to_one(self):
        for horizon, weights in WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 1e-9, f"Weights for '{horizon}' sum to {total}, expected 1.0"

    def test_all_zero_scores(self):
        for horizon in ("short", "medium", "long"):
            assert compute_weighted_score(horizon, ComponentScores(0.0, 0.0, 0.0)) == 0.0

    def test_all_hundred_scores(self):
        for horizon in ("short", "medium", "long"):
            assert abs(compute_weighted_score(horizon, ComponentScores(100.0, 100.0, 100.0)) - 100.0) < 1e-6

    def test_medium_term_all_components_matter(self):
        scores = ComponentScores(fundamental=80.0, technical=60.0, sentiment=40.0)
        result = compute_weighted_score("medium", scores)
        weights = WEIGHTS["medium"]
        expected = 80.0 * weights["fundamental"] + 60.0 * weights["technical"] + 40.0 * weights["sentiment"]
        assert abs(result - expected) < 1e-6


class TestDeriveRating:
    def test_buy_at_70(self):
        assert derive_rating(70.0) == "buy"

    def test_buy_above_70(self):
        assert derive_rating(95.0) == "buy"

    def test_hold_at_40(self):
        assert derive_rating(40.0) == "hold"

    def test_hold_just_below_70(self):
        assert derive_rating(69.9) == "hold"

    def test_sell_below_40(self):
        assert derive_rating(39.9) == "sell"

    def test_sell_at_zero(self):
        assert derive_rating(0.0) == "sell"


class TestBuildRecommendationDetail:
    def test_returns_all_keys(self):
        result = build_recommendation_detail("short", ComponentScores(0, 80, 60), ["Reason A"])
        assert {"horizon", "rating", "score", "reasons"} == set(result.keys())

    def test_horizon_preserved(self):
        result = build_recommendation_detail("long", ComponentScores(75, 75, 75), [])
        assert result["horizon"] == "long"

    def test_score_rounded(self):
        scores = ComponentScores(fundamental=33.333, technical=33.333, sentiment=33.333)
        result = build_recommendation_detail("medium", scores, [])
        assert isinstance(result["score"], float)
        assert result["score"] == round(result["score"], 2)

    def test_strong_buy_scenario(self):
        result = build_recommendation_detail("medium", ComponentScores(90, 90, 90), [])
        assert result["rating"] == "buy"

    def test_sell_scenario(self):
        result = build_recommendation_detail("long", ComponentScores(10, 10, 10), [])
        assert result["rating"] == "sell"
