"""Unit tests for AgentService follow-up routing behavior."""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web")))

from services.agent_service import AgentService


def test_long_term_followup_does_not_rerun_full_analysis():
    llm = MagicMock()
    llm.generate_raw.side_effect = [
        '<tool_call>{"name":"run_full_analysis","args":{"ticker":"TSLA"}}</tool_call>',
        "Long-term outlook remains constructive based on durable fundamentals and structural trend context.",
    ]

    formatter = MagicMock()
    formatter.append_citations_html.side_effect = lambda reply, citations: reply
    formatter.ensure_analysis_markup.side_effect = lambda *args, **kwargs: ""

    analysis_obj = SimpleNamespace(
        recommendations={
            "long_term": {"label": "BUY", "score": 66.0, "summary": "Long-horizon business quality and valuation: margins are stable"},
            "fundamental": {"summary": "margins are stable, debt is low"},
            "technical": {"summary": "Price above SMA200 (long-term uptrend), Golden cross (SMA20 > SMA50)"},
            "sentiment": {"summary": "Neutral news backdrop"},
        }
    )

    executor = MagicMock()
    executor.stock_service.get_analysis.return_value = analysis_obj

    svc = AgentService(llm_service=llm, tool_executor=executor, formatting_service=formatter)

    result = svc.run(
        user_message="give me more about the long term outlook",
        conversation_history=[],
        model_key="gemma3",
        last_analyzed_ticker="TSLA",
    )

    # The route should reuse existing context, not execute tools again.
    executor.execute.assert_not_called()

    assert "🧭 Reusing prior full-analysis context..." in result["tool_updates"]
    assert result["analysis_html"] == ""
    assert result["last_analyzed_ticker"] == "TSLA"
    assert "long-term outlook" in result["reply"].lower() or "outlook" in result["reply"].lower()


def test_followup_skips_resolve_ticker_without_explicit_ticker_in_query():
    llm = MagicMock()
    llm.generate_raw.side_effect = [
        '<tool_call>{"name":"resolve_ticker","args":{"company_name":"why did it fall in may 2026"}}</tool_call>',
        "It fell due to a mix of weak guidance, macro pressure, and multiple compression.",
    ]

    formatter = MagicMock()
    formatter.append_citations_html.side_effect = lambda reply, citations: reply
    formatter.ensure_analysis_markup.side_effect = lambda *args, **kwargs: ""

    executor = MagicMock()
    executor.execute.return_value = ("{}", "noop")

    svc = AgentService(llm_service=llm, tool_executor=executor, formatting_service=formatter)

    result = svc.run(
        user_message="why did it fall in may 2026?",
        conversation_history=[],
        model_key="gemma3",
        last_analyzed_ticker="NFLX",
    )

    # resolve_ticker should be bypassed; no tool execution needed.
    executor.execute.assert_not_called()
    assert "🔎 Using previous ticker NFLX..." in result["tool_updates"]
    assert result["last_analyzed_ticker"] == "NFLX"


def test_build_earnings_reply_humanizes_date_and_session():
    svc = AgentService(llm_service=MagicMock(), tool_executor=MagicMock(), formatting_service=MagicMock())
    payload = {
        "ticker": "NFLX",
        "next_earnings_available": True,
        "next_earnings": {
            "Earnings Date": "[datetime.date(2026, 7, 16)]",
            "Earnings Call Time": "After Market Close",
        },
        "latest_known_earnings_date": "",
        "error": None,
    }

    reply = svc._build_earnings_reply({"ticker": "NFLX"}, __import__("json").dumps(payload))
    assert "Jul 16, 2026" in reply
    assert "post-market" in reply.lower()


def test_build_earnings_reply_includes_human_readable_timestamps():
    svc = AgentService(llm_service=MagicMock(), tool_executor=MagicMock(), formatting_service=MagicMock())
    payload = {
        "ticker": "TSLA",
        "next_earnings_available": True,
        "next_earnings": {
            "Earnings Date": "2026-07-22",
            "earningsCallTimestampStart": 1776893400,
            "earningsCallTimestampEnd": 1776897000,
            "earningsTimestamp": 1776888000,
        },
        "latest_known_earnings_date": "",
        "error": None,
    }

    reply = svc._build_earnings_reply({"ticker": "TSLA"}, __import__("json").dumps(payload))
    assert "Timestamp details:" in reply
    assert "ET" in reply
    assert "call start:" in reply


def test_past_earnings_question_does_not_short_circuit_on_get_earnings():
    llm = MagicMock()
    llm.generate_raw.side_effect = [
        '<tool_call>{"name":"get_earnings","args":{"ticker":"AMZN"}}</tool_call>',
        '<tool_call>{"name":"web_search","args":{"query":"AMZN previous earnings call transcript highlights"}}</tool_call>',
        "On the previous AMZN earnings call, management emphasized AWS margin expansion and capex discipline.",
    ]

    formatter = MagicMock()
    formatter.append_citations_html.side_effect = lambda reply, citations: reply
    formatter.ensure_analysis_markup.side_effect = lambda *args, **kwargs: ""

    executor = MagicMock()
    executor.execute.side_effect = [
        (
            __import__("json").dumps(
                {
                    "ticker": "AMZN",
                    "next_earnings_available": True,
                    "next_earnings": {"Earnings Date": "2026-07-30"},
                    "latest_known_earnings_date": "2026-04-29",
                    "error": None,
                }
            ),
            "💰 Fetching earnings data for AMZN...",
        ),
        (
            __import__("json").dumps(
                {
                    "results": [
                        {
                            "title": "AMZN Q1 2026 earnings call transcript",
                            "url": "https://example.com/amzn-q1-2026",
                            "snippet": "Highlights from the call",
                        }
                    ]
                }
            ),
            "🌐 Searching web...",
        ),
    ]

    svc = AgentService(llm_service=llm, tool_executor=executor, formatting_service=formatter)

    result = svc.run(
        user_message="what happened in the previous AMZN earnings call?",
        conversation_history=[],
        model_key="gemma3",
        last_analyzed_ticker="AMZN",
    )

    assert executor.execute.call_count == 2
    assert executor.execute.call_args_list[0].args[0] == "get_earnings"
    assert executor.execute.call_args_list[1].args[0] == "web_search"
    assert "previous amzn earnings call" in result["reply"].lower()
