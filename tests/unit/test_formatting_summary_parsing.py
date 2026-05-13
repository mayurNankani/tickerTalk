"""Tests for resilient recommendation summary parsing in FormattingService."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from web.services.formatting_service import FormattingService


def test_parse_summary_sections_accepts_singular_and_plural():
    fmt = FormattingService()
    plural = "Fundamentals: valuation stable | Technical: trend strong | Sentiment: positive headlines"
    singular = "Fundamental: valuation stable | Technical: trend strong | Sentiment: positive headlines"

    p = fmt._parse_summary_sections(plural)
    s = fmt._parse_summary_sections(singular)

    assert p["fundamental"] == "valuation stable"
    assert s["fundamental"] == "valuation stable"
    assert p["technical"] == "trend strong"
    assert s["technical"] == "trend strong"
    assert p["sentiment"] == "positive headlines"
    assert s["sentiment"] == "positive headlines"
