"""Tool schema definitions used by the agentic tool loop."""

from __future__ import annotations

from typing import Any, Dict, List


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "resolve_ticker",
            "description": (
                "Convert a company name or partial name into its stock ticker symbol. "
                "Use this first when the user mentions a company by name rather than ticker."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Company name or partial name, e.g. 'marvell' or 'apple'",
                    }
                },
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_full_analysis",
            "description": (
                "Run a complete technical, fundamental, and sentiment analysis for a stock. "
                "Returns buy/hold/sell recommendations across short, medium, and long-term horizons. "
                "Use when the user asks for a full analysis, recommendation, or 'should I buy/sell'. "
                "This is slow - only call it when a real recommendation is needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol, e.g. 'MRVL' or 'AAPL'",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_snapshot",
            "description": (
                "Get a quick live snapshot of a stock: current price, PE ratio, market cap, "
                "52-week range, volume. Fast - use for comparison questions or quick lookups."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol, e.g. 'NVDA'",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get the latest news headlines and summaries for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": (
                "Get historical price data for a stock. "
                "Use for trend questions, chart data, or period performance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol",
                    },
                    "period": {
                        "type": "string",
                        "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y"],
                        "description": "Time period for price history",
                    },
                },
                "required": ["ticker", "period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_earnings",
            "description": "Get recent earnings data, EPS beats/misses, and revenue figures for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for real-time information about a stock or company. "
                "Use when you need recent news, analyst opinions, or information not in the analysis context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query, should include company name or ticker for relevance",
                    }
                },
                "required": ["query"],
            },
        },
    },
]
