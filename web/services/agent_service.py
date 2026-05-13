"""Agent Service
Prompt-based agentic loop — compatible with models that don't support native
Ollama function-calling (gemma3, llama3, etc.).

The LLM is instructed to emit a special JSON block when it wants a tool:

    <tool_call>{"name": "resolve_ticker", "args": {"company_name": "apple"}}</tool_call>

The loop parses this, executes the tool, injects the result, and repeats.
A plain-text response (no <tool_call>) terminates the loop.

Response shape returned to the route:
  {
    "tool_updates": ["🔍 Resolving ticker...", "📊 Running analysis..."],
    "reply": "Final answer text",
    "analysis_html": "<div ...>...</div>"   # only set after run_full_analysis
  }
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List

from services.llm_service import LLMService
from services.agent_prompts import build_chat_prompt, load_system_prompt
from services.agent_tools import ToolExecutor
from services.tool_schemas import TOOL_SCHEMAS
from services.formatting_service import FormattingService
from src.tools.web_search import normalize_result_url

MAX_TOOL_ITERATIONS = 5
_SYSTEM_PROMPT = load_system_prompt(TOOL_SCHEMAS)
_TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
_COMPARISON_SIGNAL_RE = re.compile(
    r'\b(compare|vs\.?|versus|against|better than|worse than|compared to|between|'
    r'should i buy|which is better|which one|or)\b',
    re.IGNORECASE,
)

# Words that are never ticker symbols
_SKIP_WORDS = {
    'a', 'an', 'the', 'is', 'it', 'to', 'do', 'me', 'my', 'of', 'in', 'at', 'i',
    'be', 'or', 'and', 'for', 'on', 'if', 'as', 'by', 'up', 'so', 'us', 'we',
    'buy', 'sell', 'hold', 'good', 'bad', 'what', 'how', 'why', 'when', 'who',
    'this', 'that', 'are', 'was', 'has', 'had', 'not', 'can', 'now', 'its',
    'any', 'all', 'out', 'get', 'use', 'run', 'new', 'old', 'long', 'term',
    'stock', 'share', 'price', 'about', 'with', 'from', 'into', 'than', 'more',
    'yes', 'y', 'yeah', 'yep', 'sure', 'ok', 'okay', 'please', 'full', 'analysis',
    # Common question/sentence words that could be mistaken for tickers
    'next', 'last', 'first', 'show', 'will', 'tell', 'give', 'does', 'then',
    'even', 'just', 'also', 'date', 'time', 'soon', 'they', 'them', 'their',
    'have', 'been', 'were', 'said', 'each', 'much', 'very', 'over', 'some',
    'down', 'only', 'most', 'after', 'where', 'there', 'going', 'would', 'could',
    'should', 'might', 'which', 'while', 'since', 'until', 'below', 'above',
    'between', 'before', 'during', 'recent', 'latest', 'current',
    'quarter', 'report', 'look', 'like', 'mean', 'know', 'think', 'want',
    'earn', 'earnings', 'revenue', 'profit', 'loss', 'market', 'trade', 'day',
    'high', 'low', 'open', 'close', 'volume', 'news', 'update', 'trend', 'analysis',
}
_TICKER_NOISE = {
    'P', 'E', 'PE', 'EPS', 'RSI', 'MACD', 'ADX', 'MFI', 'SMA', 'EMA', 'BB',
    'ATR', 'OBV', 'ROI', 'ROE', 'ROA', 'PCT', 'USD', 'N/A', 'PEG', 'IPO',
}
_TICKER_TOKEN_RE = re.compile(r'\b([A-Za-z]{2,6})\b')

# Indicators whose names in a question should trigger live tech-data injection
_INDICATOR_RE = re.compile(
    r'\b(macd|rsi|adx|peg|bollinger|stochastic|stoch|sma|ema|obv|mfi|atr|moving average|'
    r'golden cross|death cross|crossover|histogram|divergence|overbought|oversold|'
    r'momentum|trend strength|signal line|support|resistance)\b',
    re.IGNORECASE,
)
_HORIZON_DETAIL_RE = re.compile(
    r'\b((short|medium|long)[-\s]?term|next few months|next quarter|6[-\s]?12 months|'
    r'long[-\s]?run|outlook|thesis|deeper|more details|expand|walk me through|go over|explain more)\b',
    re.IGNORECASE,
)


class AgentService:
    """Orchestrates the prompt-based agentic loop."""

    def __init__(
        self,
        llm_service: LLMService,
        tool_executor: ToolExecutor,
        formatting_service: FormattingService,
    ):
        self.llm = llm_service
        self.executor = tool_executor
        self.formatter = formatting_service

    def run(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        model_key: str = "gemma3",
        last_analyzed_ticker: str = "",
    ) -> Dict[str, Any]:
        current_context_ticker = (last_analyzed_ticker or "").upper().strip()

        # Explicit comparison requests are easier to answer deterministically than
        # through the single-stock tool loop, so handle them up front.
        if self._looks_like_comparison_request(user_message):
            forced = self._force_stock_comparison(
                user_message,
                conversation_history,
                preferred_ticker=current_context_ticker,
            )
            if forced:
                return forced

        # Inject a hint listing the exact tokens the user typed so the LLM
        # can't mangle ticker symbols like CMCSA → CMSA.
        # Also pins the context ticker when the message has no explicit ticker.
        ticker_hint = self._build_ticker_hint(user_message, context_ticker=current_context_ticker)
        prompt = build_chat_prompt(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            conversation_history=conversation_history,
            ticker_hint=ticker_hint,
        )
        tool_updates: List[str] = []
        analysis_html: str = ""
        tool_context: List[str] = []
        citations: List[Dict[str, str]] = []

        # Pre-seed with live indicator data when the question targets a specific
        # technical concept so the LLM answers with real numbers, not a textbook recap.
        if current_context_ticker and self._looks_like_horizon_detail_question(user_message):
            horizon_ctx = self._build_horizon_detail_context(user_message, current_context_ticker)
            if horizon_ctx:
                tool_context.append(horizon_ctx)

        if current_context_ticker and self._looks_like_indicator_question(user_message):
            indicator_ctx = self._build_indicator_context(user_message, current_context_ticker)
            if indicator_ctx:
                tool_context.append(indicator_ctx)

        for iteration in range(MAX_TOOL_ITERATIONS):
            full_prompt = prompt
            if tool_context:
                full_prompt += "\n" + "\n".join(tool_context) + "\n[Assistant]"

            raw = self.llm.generate_raw(full_prompt, model_key)
            # Normalise markdown code-fence tool calls (```tool_call ... ```)
            # emitted by some models into the XML form the regex expects.
            raw = re.sub(r"```tool_call\s*(.*?)\s*```", r"<tool_call>\1</tool_call>", raw, flags=re.DOTALL)
            print(f"[Agent iter={iteration}] response: {raw[:300]!r}")

            match = _TOOL_CALL_RE.search(raw)
            plain_call = self._parse_plain_tool_call(raw) if not match else None

            if not match and not plain_call:
                reply = _TOOL_CALL_RE.sub("", raw).strip()
                # Guardrail: if the model skipped tools for an analysis request,
                # force the rich analysis flow so UI cards (chart + heatmap) render.
                if not analysis_html and (
                    self._looks_like_full_analysis_request(user_message)
                    or self._looks_like_symbol_only_request(user_message)
                ):
                    forced = self._force_full_analysis(
                        user_message,
                        conversation_history,
                        preferred_ticker=current_context_ticker,
                    )
                    if forced:
                        tool_updates.extend(forced.get("tool_updates", []))
                        analysis_html = forced.get("analysis_html", "")
                        current_context_ticker = (
                            forced.get("last_analyzed_ticker", "") or current_context_ticker
                        )
                        if forced.get("reply"):
                            reply = forced["reply"]
                if not analysis_html:
                    parsed = self._parse_json_analysis_reply(reply)
                    if parsed:
                        rendered = self.formatter.ensure_analysis_markup(
                            parsed,
                            parsed.get("ticker", ""),
                            parsed.get("analysis_html", ""),
                        )
                        if rendered:
                            tool_updates.append("📊 Rendering analysis card...")
                            analysis_html = rendered
                            parsed_ticker = (parsed.get("ticker") or "").upper().strip()
                            if parsed_ticker:
                                current_context_ticker = parsed_ticker
                            reply = (
                                f"I ran a full analysis for {parsed.get('ticker', '')}. "
                                "See the detailed recommendation card below."
                            )
                if not analysis_html:
                    reply = self._rewrite_generic_followup(
                        reply,
                        user_message,
                        conversation_history,
                        preferred_ticker=current_context_ticker,
                    )
                if self._looks_like_deal_news_query(user_message) and not citations:
                    fallback_citations = self._fetch_fallback_web_citations(
                        user_message,
                        conversation_history,
                        preferred_ticker=current_context_ticker,
                    )
                    if fallback_citations:
                        citations.extend(fallback_citations)
                        tool_updates.append("🌐 Added source links...")
                reply = self._compact_reply_text(reply, has_analysis_html=bool(analysis_html))
                reply = self.formatter.append_citations_html(reply, citations)
                return {
                    "tool_updates": tool_updates,
                    "reply": reply,
                    "analysis_html": analysis_html,
                    "last_analyzed_ticker": current_context_ticker,
                }

            if match:
                json_str = match.group(1).strip()
                try:
                    call = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"[Agent] Bad tool call JSON: {json_str!r} - {e}")
                    reply = _TOOL_CALL_RE.sub("", raw).strip() or "I ran into an issue. Please rephrase."
                    reply = self._compact_reply_text(reply, has_analysis_html=bool(analysis_html))
                    return {
                        "tool_updates": tool_updates,
                        "reply": reply,
                        "analysis_html": analysis_html,
                        "last_analyzed_ticker": current_context_ticker,
                    }
            else:
                call = plain_call

            tool_name = call.get("name", "")
            args = call.get("args", {})
            has_explicit_ticker_tokens = self._has_explicit_ticker_tokens(user_message)

            is_horizon_followup = bool(
                current_context_ticker and self._looks_like_horizon_detail_question(user_message)
            )

            if (
                tool_name == "resolve_ticker"
                and current_context_ticker
                and not has_explicit_ticker_tokens
            ):
                tool_updates.append(f"🔎 Using previous ticker {current_context_ticker}...")
                tool_context.append(
                    f"[Tool result for resolve_ticker]\n"
                    f"{{\"ticker\": \"{current_context_ticker}\", \"company_name\": \"{current_context_ticker}\"}}\n"
                )
                continue

            if is_horizon_followup and tool_name == "resolve_ticker":
                tool_updates.append(f"🔎 Using previous ticker {current_context_ticker}...")
                tool_context.append(
                    f"[Tool result for resolve_ticker]\n"
                    f"{{\"ticker\": \"{current_context_ticker}\", \"company_name\": \"{current_context_ticker}\"}}\n"
                )
                continue

            if is_horizon_followup and tool_name == "run_full_analysis":
                tool_updates.append("🧭 Reusing prior full-analysis context...")
                tool_context.append(
                    "[Tool result for run_full_analysis]\n"
                    "{\"info\": \"Skipped because the user asked for a deeper explanation of the existing horizon outlook. Reuse the prior analysis context instead of rerunning the full card.\"}\n"
                )
                continue

            explicit_ticker = self._extract_explicit_ticker(user_message)
            if explicit_ticker:
                if tool_name == "resolve_ticker":
                    args = {**args, "company_name": explicit_ticker}
                elif tool_name == "run_full_analysis":
                    args = {**args, "ticker": explicit_ticker}

            # Safety net: if the LLM mangled the ticker in resolve_ticker,
            # replace it with the best matching token from the original message.
            if tool_name == "resolve_ticker":
                args = self._correct_ticker_arg(args, user_message)

            print(f"[Agent] Calling tool: {tool_name}({args})")
            if tool_name == "run_full_analysis" and not self._looks_like_full_analysis_request(user_message):
                result_str = json.dumps({
                    "error": (
                        "run_full_analysis is reserved for explicit recommendation requests. "
                        "Use get_stock_snapshot, get_news, or web_search for general questions."
                    )
                })
                label = "⚠️ Skipping full analysis for general question..."
            else:
                result_str, label = self.executor.execute(tool_name, args)
            tool_updates.append(label)
            citations.extend(self._extract_citations(tool_name, result_str))

            if tool_name == "get_earnings":
                if self._should_short_circuit_earnings_reply(user_message):
                    earnings_reply = self._build_earnings_reply(args, result_str)
                    if earnings_reply:
                        reply = self._compact_reply_text(earnings_reply, has_analysis_html=bool(analysis_html))
                        reply = self.formatter.append_citations_html(reply, citations)
                        return {
                            "tool_updates": tool_updates,
                            "reply": reply,
                            "analysis_html": analysis_html,
                            "last_analyzed_ticker": current_context_ticker,
                        }
                elif self._looks_like_past_earnings_request(user_message):
                    tool_context.append(
                        "[SYSTEM NOTE: The user asked about a previous earnings call. "
                        "Use get_earnings output for date anchors only, then call web_search for recap/transcript sources.]"
                    )

            if tool_name == "run_full_analysis":
                try:
                    result_data = json.loads(result_str)
                    ticker = result_data.get("ticker", "")
                    if ticker and not result_data.get("error"):
                        current_context_ticker = ticker.upper()
                        analysis_html = self.formatter.ensure_analysis_markup(
                            result_data,
                            ticker,
                            result_data.get("analysis_html", ""),
                        )
                        compact = {
                            k: v for k, v in result_data.items()
                            if k not in ("analysis_html", "recent_news_headlines")
                        }
                        result_str = json.dumps(compact)
                except Exception:
                    pass

            tool_context.append(f"[Tool result for {tool_name}]\n{result_str}\n")
            assistant_text = _TOOL_CALL_RE.sub("", raw).strip()
            if plain_call and not match:
                assistant_text = ""
            if assistant_text:
                prompt = prompt + "\n" + assistant_text

        final_prompt = (
            prompt + "\n" + "\n".join(tool_context)
            + "\n[Assistant]\nPlease summarize the above data in a helpful response."
        )
        reply = self.llm.generate_raw(final_prompt, model_key)
        if not analysis_html and (
            self._looks_like_full_analysis_request(user_message)
            or self._looks_like_symbol_only_request(user_message)
        ):
            forced = self._force_full_analysis(
                user_message,
                conversation_history,
                preferred_ticker=current_context_ticker,
            )
            if forced:
                tool_updates.extend(forced.get("tool_updates", []))
                analysis_html = forced.get("analysis_html", "")
                current_context_ticker = (
                    forced.get("last_analyzed_ticker", "") or current_context_ticker
                )
                if forced.get("reply"):
                    reply = forced["reply"]
        if not analysis_html:
            parsed = self._parse_json_analysis_reply(reply)
            if parsed:
                rendered = self.formatter.ensure_analysis_markup(
                    parsed,
                    parsed.get("ticker", ""),
                    parsed.get("analysis_html", ""),
                )
                if rendered:
                    tool_updates.append("📊 Rendering analysis card...")
                    analysis_html = rendered
                    parsed_ticker = (parsed.get("ticker") or "").upper().strip()
                    if parsed_ticker:
                        current_context_ticker = parsed_ticker
                    reply = (
                        f"I ran a full analysis for {parsed.get('ticker', '')}. "
                        "See the detailed recommendation card below."
                    )
        if not analysis_html:
            reply = self._rewrite_generic_followup(
                reply,
                user_message,
                conversation_history,
                preferred_ticker=current_context_ticker,
            )
        if self._looks_like_deal_news_query(user_message) and not citations:
            fallback_citations = self._fetch_fallback_web_citations(
                user_message,
                conversation_history,
                preferred_ticker=current_context_ticker,
            )
            if fallback_citations:
                citations.extend(fallback_citations)
                tool_updates.append("🌐 Added source links...")
        reply = self._compact_reply_text(reply, has_analysis_html=bool(analysis_html))
        reply = self.formatter.append_citations_html(reply, citations)
        return {
            "tool_updates": tool_updates,
            "reply": _TOOL_CALL_RE.sub("", reply).strip(),
            "analysis_html": analysis_html,
            "last_analyzed_ticker": current_context_ticker,
        }

    def _parse_plain_tool_call(self, raw: str) -> Dict[str, Any] | None:
        """Parse unwrapped JSON tool calls returned as plain text/code-fenced JSON."""
        text = (raw or "").strip()
        if not text:
            return None

        # Support generic JSON fences: ```json { ... } ```
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

        candidates = [text]
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
            candidates.append(text[first_brace:last_brace + 1])

        data = None
        for candidate in candidates:
            candidate = candidate.strip()
            if not (candidate.startswith("{") and candidate.endswith("}")):
                continue
            try:
                data = json.loads(candidate)
                break
            except Exception:
                continue

        if data is None:
            return None

        if not isinstance(data, dict):
            return None

        if not isinstance(data.get("name"), str):
            return None

        args = data.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return None

        return {"name": data["name"], "args": args}

    def _looks_like_symbol_only_request(self, user_message: str) -> bool:
        """Treat bare ticker-style prompts (e.g. AAPL) as direct analysis requests."""
        text = (user_message or "").strip()
        if not text or " " in text:
            return False

        upper = text.upper()
        if upper in _TICKER_NOISE or upper.lower() in _SKIP_WORDS:
            return False

        return bool(re.fullmatch(r"\^?[A-Z0-9\.-]{1,10}", upper))

    def _looks_like_full_analysis_request(self, user_message: str) -> bool:
        """Detect explicit recommendation-style requests for the full analysis card."""
        text = (user_message or "").lower()
        if self._looks_like_horizon_detail_question(text):
            return False

        explicit_analysis_terms = (
            "full analysis", "analy", "analysis", "recommend", "recommendation",
            "should i buy", "should i sell", "buy or sell", "entry point",
            "target price", "price target", "short term", "medium term",
            "long term", "horizon", "rating", "bullish", "bearish",
            "investment thesis", "is it a buy", "is this a buy",
        )
        general_info_terms = (
            "what is", "who is", "tell me about", "company", "business",
            "ceo", "founded", "headquarters", "products", "services",
            "history", "overview",
        )

        has_explicit_analysis_intent = any(term in text for term in explicit_analysis_terms)
        has_general_info_intent = any(term in text for term in general_info_terms)

        # Keep full-analysis for explicit recommendation asks, not generic company Q&A.
        return has_explicit_analysis_intent and not (has_general_info_intent and "should i" not in text)

    def _looks_like_comparison_request(self, user_message: str) -> bool:
        """Detect explicit two-stock comparison requests."""
        return bool(_COMPARISON_SIGNAL_RE.search(user_message or ""))

    def _force_stock_comparison(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        preferred_ticker: str = "",
    ) -> Dict[str, Any] | None:
        """Resolve two tickers and render a side-by-side comparison card."""
        tickers = self._extract_comparison_tickers(
            user_message,
            conversation_history,
            preferred_ticker=preferred_ticker,
        )
        if len(tickers) < 2:
            return None

        analyses = []
        tool_updates: List[str] = []

        for ticker in tickers[:2]:
            try:
                result = self.executor.stock_service.get_analysis(ticker, ticker)
                analyses.append(result)
                tool_updates.append(f"📊 Running analysis for {ticker}...")
            except Exception as exc:
                print(f"[Agent] Comparison analysis failed for {ticker}: {exc}")

        if len(analyses) < 2:
            return None

        comparison_html = self.formatter.format_stock_comparison(analyses)

        return {
            "tool_updates": tool_updates,
            "reply": f"I compared {analyses[0].ticker} and {analyses[1].ticker}. See the comparison card below.",
            "analysis_html": comparison_html,
            "last_analyzed_ticker": analyses[0].ticker,
        }

    def _force_full_analysis(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        preferred_ticker: str = "",
    ) -> Dict[str, Any] | None:
        """Run resolve_ticker + run_full_analysis when LLM skipped tool usage."""
        ticker = ""
        tool_updates: List[str] = []

        # 1) Prioritize explicit ticker-like token in the current user message.
        tokens = _TICKER_TOKEN_RE.findall(user_message or "")
        for token in tokens:
            token_u = token.upper()
            if token.lower() in _SKIP_WORDS or token_u in _TICKER_NOISE:
                continue
            if len(token_u) >= 2 and len(token_u) <= 6:
                ticker = token_u
                break

        # 2) If no explicit ticker token found, resolve from full message text.
        if not ticker:
            resolve_str, resolve_label = self.executor.execute(
                "resolve_ticker", {"company_name": user_message}
            )
            tool_updates.append(resolve_label)

            try:
                resolved = json.loads(resolve_str)
                ticker = (resolved.get("ticker") or "").upper()
            except Exception:
                ticker = ""

        # 3) Final fallback: reuse history ticker only when user did not specify one.
        if not ticker:
            ticker = self._extract_ticker_from_history(
                conversation_history,
                preferred_ticker=preferred_ticker,
            )
            if ticker:
                tool_updates.append(f"🔎 Reusing last discussed ticker {ticker}...")

        if not ticker:
            return None

        analysis_str, analysis_label = self.executor.execute(
            "run_full_analysis", {"ticker": ticker}
        )
        tool_updates.append(analysis_label)

        try:
            result_data = json.loads(analysis_str)
            if result_data.get("error"):
                return None
            analysis_html = self.formatter.ensure_analysis_markup(
                result_data,
                ticker,
                result_data.get("analysis_html", ""),
            )
            if not analysis_html:
                return None
            return {
                "tool_updates": tool_updates,
                "analysis_html": analysis_html,
                "reply": f"I ran a full analysis for {ticker}. See the detailed recommendation card below.",
                "last_analyzed_ticker": ticker,
            }
        except Exception:
            return None

    def _parse_json_analysis_reply(self, reply: str) -> Dict[str, Any] | None:
        """Parse a model reply that is actually the tool JSON payload."""
        text = (reply or "").strip()
        if not text:
            return None

        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

        if not (text.startswith("{") and text.endswith("}")):
            return None

        try:
            data = json.loads(text)
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        if not data.get("ticker") or not data.get("recommendations"):
            return None

        return data

    def _extract_ticker_from_history(
        self,
        conversation_history: List[Dict[str, str]],
        preferred_ticker: str = "",
    ) -> str:
        """Extract the most recent plausible ticker from prior chat messages."""
        preferred = (preferred_ticker or "").upper().strip()
        if preferred and preferred.lower() not in _SKIP_WORDS and preferred not in _TICKER_NOISE:
            return preferred

        for msg in reversed(conversation_history or []):
            content = (msg.get("content") or "").strip()
            if not content:
                continue

            # Prefer explicit ticker markers from rendered analysis cards.
            match = re.search(r'data-ticker="([^"]+)"', content)
            if match:
                return match.group(1).upper()

            # Prefer a parenthesized ticker after a company name, e.g. MRVL.
            match = re.search(r'\(([A-Z0-9\.\^]{1,10})\)', content)
            if match:
                candidate = match.group(1).upper()
                if candidate.lower() not in _SKIP_WORDS:
                    return candidate

            # Fallback to the last uppercase ticker-like token in the message.
            tokens = re.findall(r'\b([A-Z0-9\.\^]{1,10})\b', content)
            for token in reversed(tokens):
                if token[0].isdigit() or token.isdigit() or token.lower() in _SKIP_WORDS or token.upper() in _TICKER_NOISE:
                    continue
                if (len(token) >= 2 and len(token) <= 6) or token.startswith('^'):
                    return token.upper()

        return ""

    def _extract_comparison_tickers(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        preferred_ticker: str = "",
    ) -> List[str]:
        """Extract up to two comparison tickers from the query and chat history."""
        resolved: List[str] = []
        seen = set()

        def add_symbol(symbol: str):
            clean = (symbol or "").upper().strip()
            if not clean or clean in seen:
                return
            if clean.lower() in _SKIP_WORDS:
                return
            if len(clean) == 1 and clean.isalpha():
                return
            if re.fullmatch(r'[A-Z0-9\.^]{1,10}', clean):
                resolved.append(clean)
                seen.add(clean)

        # Current context ticker should be part of the comparison when present.
        current_ticker = self._extract_ticker_from_history(
            conversation_history,
            preferred_ticker=preferred_ticker,
        )
        if current_ticker:
            add_symbol(current_ticker)

        # Extract explicit ticker-like tokens from the message.
        for token in re.findall(r'\b[A-Z0-9\.\^]{1,10}\b', user_message or ""):
            token_u = token.upper().strip()
            if token_u[0].isdigit() or token_u.isdigit() or token_u.lower() in _SKIP_WORDS or token_u in _TICKER_NOISE:
                continue
            if len(token_u) == 1 and token_u.isalpha():
                continue
            if re.fullmatch(r'[A-Z0-9]{1,6}(?:\.[A-Z]{1,2})?|\^[A-Z0-9]+', token_u):
                add_symbol(token_u)

        # Resolve phrase chunks around comparison connectors (supports lowercase names).
        lowered = (user_message or "").lower()
        if any(keyword in lowered for keyword in (" vs ", " versus ", " against ", " and ", " or ", "compare ", "between ")):
            chunks = re.split(r'\b(?:vs\.?|versus|against|and|or|compare|between|to)\b', user_message or "", flags=re.IGNORECASE)
            for chunk in chunks:
                phrase = chunk.strip(" ,.?;:!()[]{}\"'")
                if not phrase:
                    continue
                if len(phrase) <= 1 or phrase.lower() in _SKIP_WORDS:
                    continue
                try:
                    result_str, _ = self.executor.execute("resolve_ticker", {"company_name": phrase})
                    result_data = json.loads(result_str)
                    add_symbol(result_data.get("ticker", ""))
                except Exception:
                    continue

        # Resolve title-case company names from the query through the ticker tool.
        phrases = re.findall(r'\b(?:[A-Z][a-z0-9&]+(?:\s+[A-Z][a-z0-9&]+){0,2})\b', user_message or "")
        for phrase in phrases:
            phrase_l = phrase.lower().strip()
            if phrase_l in _SKIP_WORDS:
                continue
            try:
                result_str, _ = self.executor.execute("resolve_ticker", {"company_name": phrase})
                result_data = json.loads(result_str)
                add_symbol(result_data.get("ticker", ""))
            except Exception:
                continue

        # Also scan recent assistant/user messages for a second explicit ticker.
        for msg in reversed(conversation_history or []):
            content = msg.get("content") or ""
            for token in re.findall(r'\b[A-Z]{1,5}(?:\.[A-Z]{1,2})?\b', content):
                if token.upper() in _TICKER_NOISE:
                    continue
                add_symbol(token)

        return resolved[:2]

    def _rewrite_generic_followup(
        self,
        reply: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        preferred_ticker: str = "",
    ) -> str:
        """Replace repetitive generic follow-up prompts with intent-aware options."""
        text = (reply or "").strip()
        if not text:
            return text

        generic_pattern = re.compile(
            r"Would you like me to run a full analysis for\s+"
            r"([A-Z0-9\.^]{1,10})"
            r",?\s*or\s*would\s*you\s*like\s*to\s*compare\s*it\s*to\s*another\s*stock\??",
            re.IGNORECASE,
        )
        if not generic_pattern.search(text):
            return text

        match = generic_pattern.search(text)
        ticker = (match.group(1).upper() if match else "") or self._extract_ticker_from_history(
            conversation_history,
            preferred_ticker=preferred_ticker,
        )
        if not ticker:
            ticker = "this stock"

        question = (user_message or "").lower()
        replacement = (
            f"Would you like a quick snapshot for {ticker} "
            f"(price, valuation, and 52-week range), or latest news headlines?"
        )

        if any(k in question for k in ("news", "headline", "article", "press", "announcement")):
            replacement = (
                f"Want me to pull the latest 5 headlines for {ticker}, "
                f"or compare today's sentiment vs price move?"
            )
        elif any(k in question for k in ("price", "up", "down", "today", "performance", "trend", "chart", "volume")):
            replacement = (
                f"Want a quick performance snapshot for {ticker} "
                f"(price, day move, and range), or a side-by-side comparison with a peer?"
            )
        elif any(k in question for k in ("valuation", "pe", "p/e", "cheap", "expensive", "multiple")):
            replacement = (
                f"Want me to break down {ticker}'s valuation metrics, "
                f"or compare valuation against a competitor?"
            )
        elif any(k in question for k in ("company", "business", "ceo", "founded", "overview", "what is", "tell me about")):
            replacement = (
                f"Would you like a company snapshot for {ticker} "
                f"(business, key metrics, and recent headlines), or should I focus on one area?"
            )

        return generic_pattern.sub(replacement, text)

    def _build_ticker_hint(self, user_message: str, context_ticker: str = "") -> str:
        """Return a prompt hint pinning the ticker the LLM should operate on.
        When the user message contains an explicit ticker token, that takes priority.
        When it doesn't, the session context ticker is injected so the LLM never
        guesses a random word (e.g. 'NEXT' from 'when are the next earnings?')."""
        tokens = _TICKER_TOKEN_RE.findall(user_message)
        candidates = [
            t.upper() for t in tokens
            if t.lower() not in _SKIP_WORDS and t.upper() not in _TICKER_NOISE
        ]
        unique = list(dict.fromkeys(candidates))  # deduplicate, preserve order

        if unique:
            items = ", ".join(f'"{c}"' for c in unique)
            return (
                f"[SYSTEM NOTE: The user message contains these exact strings: {items}. "
                f"When calling resolve_ticker, use the EXACT string as written above — "
                f"do NOT abbreviate, truncate, or alter it in any way.]"
            )

        # No ticker token in the message — pin the session context ticker.
        ctx = (context_ticker or "").upper().strip()
        if ctx and ctx.lower() not in _SKIP_WORDS and ctx not in _TICKER_NOISE:
            return (
                f"[SYSTEM NOTE: The user did not mention a specific ticker. "
                f"The current session context is {ctx}. "
                f"Use {ctx} as the ticker for any tool calls unless the user explicitly names a different company.]"
            )

        return ""

    def _extract_citations(self, tool_name: str, result_str: str) -> List[Dict[str, str]]:
        """Extract citation candidates from tool outputs."""
        try:
            data = json.loads(result_str or "{}")
        except Exception:
            return []

        citations: List[Dict[str, str]] = []

        if tool_name == "get_news":
            for item in data.get("articles", [])[:5]:
                if not isinstance(item, dict):
                    continue
                url = normalize_result_url((item.get("url") or "").strip())
                title = (item.get("headline") or "Source").strip()
                source = (item.get("source") or "Finnhub").strip()
                if url:
                    citations.append({"title": title, "url": url, "source": source})

        elif tool_name == "web_search":
            for item in data.get("results", [])[:5]:
                if not isinstance(item, dict):
                    continue
                url = normalize_result_url((item.get("url") or "").strip())
                title = (item.get("title") or "Source").strip()
                if url:
                    citations.append({"title": title, "url": url, "source": "Web"})

        return citations

    def _looks_like_deal_news_query(self, user_message: str) -> bool:
        """Detect acquisition/deal/news intents that should include source links."""
        text = (user_message or "").lower()
        terms = (
            "acquisition", "acquire", "merger", "m&a", "deal", "agreement",
            "headline", "headlines", "news", "article", "articles", "report",
            "source", "sources",
        )
        return any(term in text for term in terms)

    def _looks_like_past_earnings_request(self, user_message: str) -> bool:
        """Detect questions about previous earnings calls/results, not the next scheduled date."""
        text = (user_message or "").lower()
        if "earn" not in text:
            return False

        markers = (
            "previous", "prev", "last", "prior", "recent earnings", "past earnings",
            "what happened", "what was said", "highlights", "recap", "summary",
            "transcript", "q&a", "qa", "guidance", "beat", "miss", "results",
            "on the call", "during the call",
        )
        return any(marker in text for marker in markers)

    def _looks_like_next_earnings_request(self, user_message: str) -> bool:
        """Detect direct scheduling questions about the next/upcoming earnings call."""
        text = (user_message or "").lower()
        if "earn" not in text:
            return False

        markers = (
            "next", "upcoming", "when is", "when's", "when will", "scheduled",
            "date", "time", "calendar", "up next",
        )
        return any(marker in text for marker in markers)

    def _should_short_circuit_earnings_reply(self, user_message: str) -> bool:
        """Only auto-return get_earnings when user intent is clearly about next-call schedule."""
        if self._looks_like_past_earnings_request(user_message):
            return False
        return self._looks_like_next_earnings_request(user_message)

    def _build_earnings_reply(self, args: Dict[str, Any], result_str: str) -> str:
        """Build a concise deterministic reply for get_earnings tool output."""
        ticker = (args.get("ticker") or "").upper().strip()
        try:
            payload = json.loads(result_str or "{}")
        except Exception:
            payload = {}

        if not isinstance(payload, dict):
            return ""

        ticker = (payload.get("ticker") or ticker or "this company").upper()
        next_available = bool(payload.get("next_earnings_available"))
        next_earnings = payload.get("next_earnings") if isinstance(payload.get("next_earnings"), dict) else {}
        latest_known = (payload.get("latest_known_earnings_date") or "").strip()
        err = (payload.get("error") or "").strip()

        def _humanize_date(raw: Any) -> str:
            text = str(raw or "").strip()
            if not text:
                return ""

            # Parse legacy string form like "[datetime.date(2026, 7, 16)]".
            m = re.search(r"datetime\.date\((\d{4}),\s*(\d{1,2}),\s*(\d{1,2})\)", text)
            if m:
                try:
                    from datetime import date as _date
                    dt = _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    return dt.strftime("%b %d, %Y")
                except Exception:
                    pass

            # Handle plain ISO date-like strings.
            iso = text.replace("Z", "+00:00")
            for parser in (
                lambda s: __import__("datetime").datetime.strptime(s[:10], "%Y-%m-%d"),
                lambda s: __import__("datetime").datetime.fromisoformat(s),
            ):
                try:
                    dt = parser(iso)
                    return dt.strftime("%b %d, %Y")
                except Exception:
                    continue

            # Strip list wrappers if present.
            text = re.sub(r"^\[|\]$", "", text)
            return text

        def _market_session_text(details: Dict[str, Any]) -> str:
            if not details:
                return ""
            for key in (
                "Earnings Call Time", "earnings_call_time", "earningsTime", "time", "session"
            ):
                value = details.get(key)
                if not value:
                    continue
                raw = str(value).strip()
                low = raw.lower()
                if any(term in low for term in ("before market", "pre-market", "premarket", "bmo")):
                    return "pre-market"
                if any(term in low for term in ("after market", "post-market", "after hours", "amc")):
                    return "post-market"
                return raw
            return ""

        def _format_timestamp_et(raw: Any) -> str:
            if raw in (None, ""):
                return ""

            try:
                ts = float(raw)
            except (TypeError, ValueError):
                return ""

            # Handle millisecond timestamps if provided.
            if ts > 10_000_000_000:
                ts = ts / 1000.0

            try:
                from datetime import datetime, timezone
                from zoneinfo import ZoneInfo

                dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
                dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
                return dt_et.strftime("%b %d, %Y %I:%M %p ET")
            except Exception:
                return ""

        next_date = ""
        if next_earnings:
            for key in (
                "Earnings Date", "earningsDate", "date", "earnings_date",
                "startdatetime", "startdatetimetz", "startdatetimeutc",
            ):
                value = next_earnings.get(key)
                if value:
                    next_date = _humanize_date(value)
                    break

        timestamp_fields = (
            "earningsCallTimestampStart",
            "earningsCallTimestampEnd",
            "earningsTimestamp",
        )
        timestamp_parts: List[str] = []
        for key in timestamp_fields:
            if key not in next_earnings:
                continue
            formatted = _format_timestamp_et(next_earnings.get(key))
            if not formatted:
                continue
            if key == "earningsCallTimestampStart":
                timestamp_parts.append(f"call start: {formatted}")
            elif key == "earningsCallTimestampEnd":
                timestamp_parts.append(f"call end: {formatted}")
            else:
                timestamp_parts.append(f"event timestamp: {formatted}")

        timestamps_text = ""
        if timestamp_parts:
            timestamps_text = " Timestamp details: " + "; ".join(timestamp_parts) + "."

        session_text = _market_session_text(next_earnings)

        if next_available and next_date:
            if session_text:
                return (
                    f"The next earnings call for {ticker} is scheduled for {next_date} ({session_text})."
                    f"{timestamps_text}"
                )
            return (
                f"The next earnings call for {ticker} is scheduled for {next_date}. "
                f"The pre/post-market session is not provided in the current feed."
                f"{timestamps_text}"
            )

        if next_available:
            return f"I found an upcoming earnings event for {ticker}, but the exact date field is not available in the current feed."

        if latest_known:
            return (
                f"I don't have a confirmed next earnings call date for {ticker} yet. "
                f"The latest known earnings record in the feed is dated {latest_known}."
            )

        if err:
            return f"I couldn't fetch the next earnings call date for {ticker} right now ({err})."

        return f"I don't have a confirmed next earnings call date for {ticker} yet."

    def _fetch_fallback_web_citations(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        preferred_ticker: str = "",
    ) -> List[Dict[str, str]]:
        """Fetch web_search citations when the model answers without source tools."""
        anchor = self._extract_ticker_from_history(
            conversation_history,
            preferred_ticker=preferred_ticker,
        )
        query = f"{anchor} {user_message}".strip() if anchor else user_message
        try:
            result_str, _ = self.executor.execute("web_search", {"query": query})
            return self._extract_citations("web_search", result_str)
        except Exception:
            return []

    def _looks_like_indicator_question(self, user_message: str) -> bool:
        """Return True when the question is about a specific technical indicator."""
        return bool(_INDICATOR_RE.search(user_message or ""))

    def _looks_like_horizon_detail_question(self, user_message: str) -> bool:
        """Return True for follow-ups asking to expand on a prior horizon outlook."""
        text = (user_message or "")
        if not _HORIZON_DETAIL_RE.search(text):
            return False
        lowered = text.lower()
        return any(term in lowered for term in (
            'short term', 'short-term', 'medium term', 'medium-term', 'long term', 'long-term',
            'next few months', 'next quarter', '6-12 months', 'long run', 'long-term outlook',
            'long term outlook', 'medium-term outlook', 'short-term outlook', 'outlook', 'thesis'
        ))

    def _requested_horizon(self, user_message: str) -> str:
        """Map the user's wording to short/medium/long horizon buckets."""
        text = (user_message or "").lower()
        if any(term in text for term in ('short term', 'short-term', 'next week', 'near term', 'near-term')):
            return 'short'
        if any(term in text for term in ('medium term', 'medium-term', 'next few months', 'next quarter', '3 months')):
            return 'medium'
        if any(term in text for term in ('long term', 'long-term', '6-12 months', 'long run', 'long-run', 'long horizon')):
            return 'long'
        # If the user asks for more detail on the outlook/thesis without naming a
        # horizon, default to long-term because that is the most natural reading.
        return 'long'

    def _build_horizon_detail_context(self, user_message: str, ticker: str) -> str:
        """Fetch the last analyzed stock's recommendation data and inject horizon-specific follow-up context."""
        horizon = self._requested_horizon(user_message)
        if not horizon:
            return ''

        try:
            analysis = self.executor.stock_service.get_analysis(ticker, ticker)
            recs = getattr(analysis, 'recommendations', {}) or {}
            horizon_key = f'{horizon}_term'
            horizon_rec = recs.get(horizon_key) or {}
            if not horizon_rec:
                return ''

            horizon_labels = {
                'short': 'Short-term (1 week)',
                'medium': 'Medium-term (3 months)',
                'long': 'Long-term (6-12 months)',
            }
            lines = [
                f"[FOLLOW-UP CONTEXT for {ticker}]",
                f"The user is asking for more detail on the previous {horizon_labels.get(horizon, horizon)} outlook.",
                f"Previous rating: {horizon_rec.get('label', 'N/A')} | Score: {horizon_rec.get('score', 'N/A')}",
            ]

            if horizon_rec.get('summary'):
                lines.append(f"Prior horizon rationale: {horizon_rec.get('summary')}")

            if horizon == 'short':
                tech = (recs.get('technical') or {}).get('summary')
                sent = (recs.get('sentiment') or {}).get('summary')
                if tech:
                    lines.append(f"Technical support: {tech}")
                if sent:
                    lines.append(f"Sentiment support: {sent}")
            elif horizon == 'medium':
                fund = (recs.get('fundamental') or {}).get('summary')
                tech = (recs.get('technical') or {}).get('summary')
                sent = (recs.get('sentiment') or {}).get('summary')
                if fund:
                    lines.append(f"Fundamental support: {fund}")
                if tech:
                    lines.append(f"Technical support: {tech}")
                if sent:
                    lines.append(f"Sentiment support: {sent}")
            else:
                fund = (recs.get('fundamental') or {}).get('summary')
                tech = (recs.get('technical') or {}).get('summary')
                if fund:
                    lines.append(f"Long-term fundamental support: {fund}")
                if tech:
                    lines.append(f"Structural trend support: {tech}")

            lines.append(
                "[Expand specifically on this horizon only. Reference the prior conclusion, explain what drives it, "
                "and add nuance about what could improve or weaken the outlook. Do NOT rerun or restate the entire full analysis card. "
                "Answer in 2-4 short paragraphs.]"
            )
            return "\n".join(lines)
        except Exception as exc:
            print(f"[Agent] Horizon detail context fetch failed for {ticker}: {exc}")
            return ''

    def _build_indicator_context(self, user_message: str, ticker: str) -> str:
        """Fetch live technical values for *ticker* and return a context note
        scoped to the indicators mentioned in the question."""
        try:
            from src.tools.technical_analysis import TechnicalAnalysis
            result = TechnicalAnalysis().analyze(ticker)
            if not result or not result.data:
                return ""
            d = result.data

            # Always include price + MACD block since it's the most common follow-up.
            lines = [
                f"[TECHNICAL DATA for {ticker}]",
                f"Price: ${d.get('current_price', 'N/A'):.2f}  |  Day change: {d.get('price_change', 0):.2f}%",
            ]

            q = (user_message or "").lower()

            if any(k in q for k in ("macd", "crossover", "signal line", "histogram", "divergence")):
                macd = d.get("macd")
                sig  = d.get("macd_signal")
                hist = d.get("macd_hist")
                cross = "bearish" if (macd is not None and sig is not None and macd < sig) else \
                        "bullish" if (macd is not None and sig is not None and macd > sig) else "neutral"
                lines.append(
                    f"MACD: {macd:.4f}  |  Signal: {sig:.4f}  |  Histogram: {hist:.4f}  |  Status: {cross} crossover"
                )

            if any(k in q for k in ("rsi", "overbought", "oversold")):
                rsi = d.get("rsi")
                state = "overbought" if rsi and rsi > 70 else "oversold" if rsi and rsi < 30 else "neutral"
                lines.append(f"RSI: {rsi:.2f} ({state})")

            if any(k in q for k in ("stoch", "stochastic")):
                lines.append(f"Stoch %K: {d.get('stoch_k', 'N/A'):.2f}  |  %D: {d.get('stoch_d', 'N/A'):.2f}")

            if any(k in q for k in ("adx", "trend strength", "directional")):
                adx = d.get("adx")
                strength = "strong" if adx and adx > 25 else "weak"
                lines.append(
                    f"ADX: {adx:.2f} ({strength} trend)  |  +DI: {d.get('adx_positive', 'N/A'):.2f}  |  -DI: {d.get('adx_negative', 'N/A'):.2f}"
                )

            if any(k in q for k in ("bollinger", "bb", "band")):
                lines.append(
                    f"Bollinger Bands — Upper: {d.get('bb_upper', 'N/A'):.2f}  |  Mid: {d.get('bb_middle', 'N/A'):.2f}  |  Lower: {d.get('bb_lower', 'N/A'):.2f}"
                )

            if any(k in q for k in ("sma", "ema", "moving average", "golden cross", "death cross")):
                lines.append(
                    f"SMA20: {d.get('sma_20', 'N/A'):.2f}  |  SMA50: {d.get('sma_50', 'N/A'):.2f}  |  SMA200: {d.get('sma_200', 'N/A'):.2f}  |  EMA20: {d.get('ema_20', 'N/A'):.2f}"
                )

            if any(k in q for k in ("obv", "on-balance", "on balance")):
                lines.append(f"OBV: {d.get('obv', 'N/A'):.0f}")

            if any(k in q for k in ("mfi", "money flow")):
                mfi = d.get("mfi")
                lines.append(f"MFI: {mfi:.2f}" if mfi else "MFI: N/A")

            # Always append SMA position flags for context.
            flags = []
            if d.get("above_sma_20") is not None:
                flags.append(f"{'above' if d['above_sma_20'] else 'below'} SMA20")
            if d.get("above_sma_50") is not None:
                flags.append(f"{'above' if d['above_sma_50'] else 'below'} SMA50")
            if d.get("above_sma_200") is not None:
                flags.append(f"{'above' if d['above_sma_200'] else 'below'} SMA200")
            if flags:
                lines.append("Price is " + ", ".join(flags))

            lines.append(
                "[Use these exact values in your explanation. Do NOT repeat the full analysis card. "
                "Answer in 2-3 short paragraphs: first explain what the indicator means, "
                "then what the current values show for this stock specifically.]"
            )
            return "\n".join(lines)
        except Exception as exc:
            print(f"[Agent] Indicator context fetch failed for {ticker}: {exc}")
            return ""

    def _compact_reply_text(self, reply: str, has_analysis_html: bool = False) -> str:
        """Reduce repetitive text and hide internal tool narration in final replies."""
        text = (reply or "").strip()
        if not text:
            return text

        # Remove tool-execution narration that leaks implementation details.
        # Covers: "I ran/called/used/performed ... using/with <tool> ...",
        #         "I ran a quick analysis using get_stock_snapshot ..."
        text = re.sub(
            r"(?:Additionally,\s*)?(?:For your question[^,]*?,\s*)?"
            r"I (?:ran(?: a [^.]+?)? using|called|used|performed(?: a [^.]+?)? (?:using|with)) "
            r"[a-z_A-Z][a-zA-Z_]+"            # tool name token
            r"[^.]*?\.\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"I(?:'ve| have) called (?:the )?[a-z_A-Z][a-zA-Z_]+(?: tool)?\.?(?:\s*Here's what I got:)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        # Also strip mid-sentence "using <snake_case_tool>" references.
        text = re.sub(
            r"\s+using\s+[a-z][a-z_]{2,}(?=\s|[,.]|$)",
            "",
            text,
            flags=re.IGNORECASE,
        )
        # Strip standalone JSON dumps that occasionally leak through after tool calls.
        text = re.sub(
            r"(?:^|\n)\s*\{\s*\"status\"\s*:\s*.*?\}\s*(?=\n|$)",
            "",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # Remove filler transition phrases.
        text = re.sub(
            r"Based on (?:the snapshot of [A-Z]{1,6}'s current stock data|the above data),?\s*(?:I can help you better understand[^.]*\.)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"to provide (?:a snapshot of [^.]+?stock data|an? overview of [^.]+?)\.\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"This information should help you better understand[^.]*\.\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        if has_analysis_html:
            # Strip verbatim analysis-card section dumps already shown in the card.
            section_patterns = [
                r"Recommendations:\s.*?(?=(Fundamental Analysis:|Technical Analysis:|Sentiment Analysis:|\n\n|$))",
                r"Fundamental Analysis:\s.*?(?=(Technical Analysis:|Sentiment Analysis:|\n\n|$))",
                r"Technical Analysis:\s.*?(?=(Sentiment Analysis:|\n\n|$))",
                r"Sentiment Analysis:\s.*?(?=(\n\n|$))",
            ]
            for pattern in section_patterns:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

        # Deduplicate near-identical sentences while preserving paragraph structure.
        seen: set = set()

        def _dedup_paragraph(para: str) -> str:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            out: List[str] = []
            for sentence in sentences:
                clean = sentence.strip()
                if not clean:
                    continue
                norm = re.sub(r"\W+", "", clean).lower()
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                out.append(clean)
            result = " ".join(out).strip()
            return re.sub(r"\s{2,}", " ", result)

        # Split on blank lines to preserve natural paragraph boundaries.
        raw_paras = re.split(r"\n{2,}", text)
        deduped_paras = [_dedup_paragraph(p) for p in raw_paras]
        deduped_paras = [p for p in deduped_paras if p]

        # When an analysis card is already rendered, cap to 3 paragraphs.
        if has_analysis_html and len(deduped_paras) > 3:
            deduped_paras = deduped_paras[:3]

        compact = "\n\n".join(deduped_paras)
        return compact or text

    def _correct_ticker_arg(self, args: Dict, user_message: str) -> Dict:
        """If the LLM's company_name looks mangled vs the original user message,
        replace it with the closest matching token from the user's input."""
        llm_name = args.get("company_name", "").upper()
        tokens = _TICKER_TOKEN_RE.findall(user_message)
        candidates = [t.upper() for t in tokens if t.lower() not in _SKIP_WORDS]
        if not candidates:
            return args
        # If user provided exactly one clear ticker-like token, trust it.
        if len(candidates) == 1 and llm_name != candidates[0]:
            forced = candidates[0]
            print(f"[Agent] Corrected ticker arg (explicit): {llm_name!r} -> {forced!r}")
            return {**args, "company_name": forced}
        # Exact match — LLM got it right
        if llm_name in candidates:
            return args
        # 1. Substring match: candidate contains the LLM's guess
        #    e.g. LLM says "CMSA", user typed "CMCSA" → "CMCSA" contains "CMSA"
        substr_matches = [c for c in candidates if llm_name in c]
        if substr_matches:
            best = max(substr_matches, key=len)
            print(f"[Agent] Corrected ticker arg (substr): {llm_name!r} -> {best!r}")
            return {**args, "company_name": best}
        # 2. Prefix match using first 3 chars
        prefix = llm_name[:3]
        prefix_matches = [c for c in candidates if c.startswith(prefix)]
        if prefix_matches:
            best = max(prefix_matches, key=len)
            print(f"[Agent] Corrected ticker arg (prefix): {llm_name!r} -> {best!r}")
            return {**args, "company_name": best}
        # 3. No match found — keep original
        return args

    def _extract_explicit_ticker(self, user_message: str) -> str:
        """Extract a single explicit ticker token from user input, if present."""
        tokens = _TICKER_TOKEN_RE.findall(user_message or "")
        candidates = [t.upper() for t in tokens if t.lower() not in _SKIP_WORDS and t.upper() not in _TICKER_NOISE]
        if not candidates:
            return ""
        # If multiple are present, avoid forcing to prevent harming comparison flows.
        if len(candidates) == 1:
            return candidates[0]
        return ""

    def _has_explicit_ticker_tokens(self, user_message: str) -> bool:
        """Return True when the user message contains at least one explicit ticker-like token."""
        # Use strict uppercase ticker pattern to avoid false positives from
        # natural-language words in follow-up questions (e.g., "may").
        tokens = re.findall(r'\b[A-Z]{2,6}(?:\.[A-Z]{1,2})?\b', user_message or "")
        candidates = [
            t
            for t in tokens
            if t.lower() not in _SKIP_WORDS and t.upper() not in _TICKER_NOISE
        ]
        return bool(candidates)

