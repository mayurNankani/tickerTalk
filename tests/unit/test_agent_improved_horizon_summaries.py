"""Tests for horizon-specific recommendation reason summaries."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.agent_improved import StockAnalysisAgentImproved


class TestHorizonSpecificReasonSummaries:
    def test_horizon_summaries_are_distinct(self):
        # Build agent without running heavyweight __init__ dependencies.
        agent = StockAnalysisAgentImproved.__new__(StockAnalysisAgentImproved)

        agent.analyze_stock = lambda ticker: {
            "fundamental_analysis": {"ok": True},
            "technical_analysis": {"ok": True},
        }
        agent.get_fundamental_recommendation = lambda data: {
            "label": "BUY",
            "summary": "valuation is reasonable, margins are stable",
            "score": 62,
            "confidence": 70,
        }
        agent.get_technical_recommendation = lambda data: {
            "label": "BUY",
            "summary": "macd is positive, price is above sma50",
            "score": 68,
            "confidence": 66,
        }
        agent._get_sentiment_recommendation = lambda ticker: {
            "label": "POSITIVE",
            "summary": "headline tone is improving",
            "score": 60,
            "confidence": 50,
        }

        recs = agent.get_recommendation("AMD")

        short_summary = recs["short_term"]["summary"]
        medium_summary = recs["medium_term"]["summary"]
        long_summary = recs["long_term"]["summary"]

        # Same component data should still produce distinct horizon framing.
        assert short_summary != medium_summary
        assert medium_summary != long_summary

        assert "Near-term momentum setup:" in short_summary
        assert "Fundamental setup for the next quarter:" in medium_summary
        assert "Long-horizon business quality and valuation:" in long_summary

    def test_long_term_technical_suppresses_short_term_indicators(self):
        agent = StockAnalysisAgentImproved.__new__(StockAnalysisAgentImproved)

        agent.analyze_stock = lambda ticker: {
            "fundamental_analysis": {"ok": True},
            "technical_analysis": {"ok": True},
        }
        agent.get_fundamental_recommendation = lambda data: {
            "label": "BUY",
            "summary": "margins are stable, debt is low",
            "score": 62,
            "confidence": 70,
        }
        agent.get_technical_recommendation = lambda data: {
            "label": "BUY",
            "summary": "rsi is neutral, macd is positive, mfi is improving",
            "score": 68,
            "confidence": 66,
        }
        agent._get_sentiment_recommendation = lambda ticker: {
            "label": "POSITIVE",
            "summary": "headline tone is improving",
            "score": 60,
            "confidence": 50,
        }

        recs = agent.get_recommendation("AMD")
        long_summary = recs["long_term"]["summary"].lower()

        assert "primary trend structure for 6-12 months:" not in long_summary
        assert "rsi" not in long_summary
        assert "macd" not in long_summary
        assert "mfi" not in long_summary
