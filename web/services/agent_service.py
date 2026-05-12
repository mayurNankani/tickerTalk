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
import os
import re
from typing import Any, Dict, List

from services.llm_service import LLMService
from services.agent_tools import TOOL_SCHEMAS, ToolExecutor
from services.formatting_service import FormattingService
from src.tools.web_search import normalize_result_url


def _build_tool_descriptions() -> str:
    lines = []
    for t in TOOL_SCHEMAS:
        fn = t["function"]
        params = fn.get("parameters", {}).get("properties", {})
        param_str = ", ".join(
            f'{k} ({v.get("type", "any")}): {v.get("description", "")}'
            for k, v in params.items()
        )
        lines.append(f'- {fn["name"]}: {fn["description"]}\n  Args: {param_str}')
    return "\n".join(lines)


def _load_system_prompt() -> str:
    """Load agent system prompt from file, substituting tool descriptions."""
    prompt_file = os.path.join(os.path.dirname(__file__), "..", "prompts", "agent_system.txt")
    prompt_file = os.path.normpath(prompt_file)
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            template = f.read()
        return template.replace("{tool_descriptions}", _build_tool_descriptions())
    except FileNotFoundError:
        # Inline fallback — should not happen in a correctly deployed app
        raise RuntimeError(f"Agent system prompt not found at {prompt_file}")

MAX_TOOL_ITERATIONS = 5
_SYSTEM_PROMPT = _load_system_prompt()
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
}
_TICKER_NOISE = {
    'P', 'E', 'PE', 'EPS', 'RSI', 'MACD', 'ADX', 'MFI', 'SMA', 'EMA', 'BB',
    'ATR', 'OBV', 'ROI', 'ROE', 'ROA', 'PCT', 'USD', 'N/A',
}
_TICKER_TOKEN_RE = re.compile(r'\b([A-Za-z]{2,6})\b')


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
    ) -> Dict[str, Any]:
        # Explicit comparison requests are easier to answer deterministically than
        # through the single-stock tool loop, so handle them up front.
        if self._looks_like_comparison_request(user_message):
            forced = self._force_stock_comparison(user_message, conversation_history)
            if forced:
                return forced

        prompt_parts: List[str] = [f"[SYSTEM]\n{_SYSTEM_PROMPT}\n"]
        for msg in conversation_history[-10:]:
            role = msg.get("role", "user").capitalize()
            prompt_parts.append(f"[{role}]\n{msg.get('content', '')}\n")
        prompt_parts.append(f"[User]\n{user_message}\n[Assistant]")

        # Inject a hint listing the exact tokens the user typed so the LLM
        # can't mangle ticker symbols like CMCSA → CMSA.
        ticker_hint = self._build_ticker_hint(user_message)
        if ticker_hint:
            prompt_parts[-1] = f"[User]\n{user_message}\n{ticker_hint}\n[Assistant]"

        prompt = "\n".join(prompt_parts)
        tool_updates: List[str] = []
        analysis_html: str = ""
        tool_context: List[str] = []
        citations: List[Dict[str, str]] = []

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
                    forced = self._force_full_analysis(user_message, conversation_history)
                    if forced:
                        tool_updates.extend(forced.get("tool_updates", []))
                        analysis_html = forced.get("analysis_html", "")
                        if forced.get("reply"):
                            reply = forced["reply"]
                if not analysis_html:
                    parsed = self._parse_json_analysis_reply(reply)
                    if parsed:
                        rendered = self._ensure_analysis_markup(parsed, parsed.get("ticker", ""), parsed.get("analysis_html", ""))
                        if rendered:
                            tool_updates.append("📊 Rendering analysis card...")
                            analysis_html = rendered
                            reply = f"I ran a full analysis for <b>{parsed.get('ticker', '')}</b>. See the detailed recommendation card below."
                if not analysis_html:
                    reply = self._rewrite_generic_followup(reply, user_message, conversation_history)
                if self._looks_like_deal_news_query(user_message) and not citations:
                    fallback_citations = self._fetch_fallback_web_citations(user_message, conversation_history)
                    if fallback_citations:
                        citations.extend(fallback_citations)
                        tool_updates.append("🌐 Added source links...")
                reply = self._append_citations_html(reply, citations)
                return {"tool_updates": tool_updates, "reply": reply, "analysis_html": analysis_html}

            if match:
                json_str = match.group(1).strip()
                try:
                    call = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"[Agent] Bad tool call JSON: {json_str!r} - {e}")
                    reply = _TOOL_CALL_RE.sub("", raw).strip() or "I ran into an issue. Please rephrase."
                    return {"tool_updates": tool_updates, "reply": reply, "analysis_html": analysis_html}
            else:
                call = plain_call

            tool_name = call.get("name", "")
            args = call.get("args", {})

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

            if tool_name == "run_full_analysis":
                try:
                    result_data = json.loads(result_str)
                    ticker = result_data.get("ticker", "")
                    if ticker and not result_data.get("error"):
                        # Use the pre-rendered HTML from FormattingService (includes chart,
                        # heatmap badges, logo, expandable sections). Fall back to the
                        # lightweight builder only if the formatter was unavailable.
                        analysis_html = result_data.get("analysis_html") or self._build_analysis_html(result_data, ticker)
                        analysis_html = self._ensure_analysis_markup(result_data, ticker, analysis_html)
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
            forced = self._force_full_analysis(user_message, conversation_history)
            if forced:
                tool_updates.extend(forced.get("tool_updates", []))
                analysis_html = forced.get("analysis_html", "")
                if forced.get("reply"):
                    reply = forced["reply"]
        if not analysis_html:
            parsed = self._parse_json_analysis_reply(reply)
            if parsed:
                rendered = self._ensure_analysis_markup(parsed, parsed.get("ticker", ""), parsed.get("analysis_html", ""))
                if rendered:
                    tool_updates.append("📊 Rendering analysis card...")
                    analysis_html = rendered
                    reply = f"I ran a full analysis for <b>{parsed.get('ticker', '')}</b>. See the detailed recommendation card below."
        if not analysis_html:
            reply = self._rewrite_generic_followup(reply, user_message, conversation_history)
        if self._looks_like_deal_news_query(user_message) and not citations:
            fallback_citations = self._fetch_fallback_web_citations(user_message, conversation_history)
            if fallback_citations:
                citations.extend(fallback_citations)
                tool_updates.append("🌐 Added source links...")
        reply = self._append_citations_html(reply, citations)
        return {
            "tool_updates": tool_updates,
            "reply": _TOOL_CALL_RE.sub("", reply).strip(),
            "analysis_html": analysis_html,
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
    ) -> Dict[str, Any] | None:
        """Resolve two tickers and render a side-by-side comparison card."""
        tickers = self._extract_comparison_tickers(user_message, conversation_history)
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

        cards = []
        rows = []
        for analysis in analyses:
            comparison_analysis = type("ComparisonAnalysis", (), {})()
            comparison_analysis.ticker = analysis.ticker
            comparison_analysis.company_name = analysis.company_name
            comparison_analysis.quote = analysis.quote
            comparison_analysis.recommendations = analysis.recommendations
            comparison_analysis.news = {"news": []}
            comparison_analysis.price_history = analysis.price_history

            if self.formatter:
                try:
                    card_html = self.formatter.format_analysis_html(comparison_analysis)
                except Exception:
                    card_html = self._build_analysis_html(analysis.to_dict(), analysis.ticker)
            else:
                card_html = self._build_analysis_html(analysis.to_dict(), analysis.ticker)
            cards.append(f"<div class='comparison-card'>{card_html}</div>")

            recs = analysis.recommendations or {}
            short = recs.get('short_term', {}) or {}
            medium = recs.get('medium_term', {}) or {}
            long_ = recs.get('long_term', {}) or {}
            price_text = self._format_comparison_price(getattr(analysis, 'quote', None))
            rows.append(
                "<tr>"
                f"<td><b>{analysis.ticker}</b></td>"
                f"<td>{analysis.company_name}</td>"
                f"<td>{price_text}</td>"
                f"<td>{short.get('label', 'N/A')}</td>"
                f"<td>{medium.get('label', 'N/A')}</td>"
                f"<td>{long_.get('label', 'N/A')}</td>"
                "</tr>"
            )

        comparison_html = (
            "<div class='comparison-section stock-card'>"
            "<div class='stock-card-header'>"
            "<div>"
            "<div class='stock-name'>Stock Comparison</div>"
            "<div class='stock-price-line'>Side-by-side analysis of the requested stocks.</div>"
            "</div>"
            "</div>"
            "<div class='comparison-summary'>"
            "<table class='comparison-table'>"
            "<thead><tr><th>Ticker</th><th>Company</th><th>Price</th><th>Short</th><th>Medium</th><th>Long</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
            "</div>"
            f"<div class='comparison-grid'>{''.join(cards)}</div>"
            "</div>"
        )

        return {
            "tool_updates": tool_updates,
            "reply": f"I compared <b>{analyses[0].ticker}</b> and <b>{analyses[1].ticker}</b>. See the comparison card below.",
            "analysis_html": comparison_html,
        }

    def _force_full_analysis(self, user_message: str, conversation_history: List[Dict[str, str]]) -> Dict[str, Any] | None:
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
            ticker = self._extract_ticker_from_history(conversation_history)
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
            analysis_html = result_data.get("analysis_html") or self._build_analysis_html(result_data, ticker)
            analysis_html = self._ensure_analysis_markup(result_data, ticker, analysis_html)
            if not analysis_html:
                return None
            return {
                "tool_updates": tool_updates,
                "analysis_html": analysis_html,
                "reply": f"I ran a full analysis for <b>{ticker}</b>. See the detailed recommendation card below.",
            }
        except Exception:
            return None

    def _ensure_analysis_markup(self, result_data: Dict, ticker: str, analysis_html: str) -> str:
        """Regenerate analysis HTML if a partial renderer dropped the heatmap/card markup."""
        if analysis_html and "badge-" in analysis_html and "rec-section-title" in analysis_html:
            return analysis_html

        if self.formatter:
            try:
                class _AnalysisFallback:
                    pass

                analysis = _AnalysisFallback()
                analysis.ticker = ticker
                analysis.company_name = result_data.get("company_name", ticker)
                analysis.quote = {
                    "data": {
                        "price": result_data.get("price"),
                        "currency": result_data.get("currency", "USD"),
                        "name": result_data.get("company_name", ticker),
                    }
                }
                analysis.recommendations = result_data.get("recommendations", {}) or {}
                analysis.news = {"news": []}
                analysis.price_history = {"dates": [], "prices": []}

                rendered = self.formatter.format_analysis_html(analysis)
                if rendered and "badge-" in rendered and "rec-section-title" in rendered:
                    return rendered
            except Exception:
                pass

        # Final fallback: synthesize the modern card from available recommendation data.
        try:
            fallback = self._build_analysis_html(result_data, ticker)
            if fallback and "stock-card" in fallback:
                return fallback
        except Exception:
            pass

        return analysis_html

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

    def _extract_ticker_from_history(self, conversation_history: List[Dict[str, str]]) -> str:
        """Extract the most recent plausible ticker from prior chat messages."""
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

    def _extract_comparison_tickers(self, user_message: str, conversation_history: List[Dict[str, str]]) -> List[str]:
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
        current_ticker = self._extract_ticker_from_history(conversation_history)
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

    def _format_comparison_price(self, quote: Any) -> str:
        """Format price text for comparison table, handling multiple quote shapes."""
        if not isinstance(quote, dict):
            return 'N/A'

        qdata = quote.get('data') if isinstance(quote.get('data'), dict) else quote
        if not isinstance(qdata, dict):
            return 'N/A'

        raw_price = qdata.get('price')
        if raw_price is None:
            raw_price = qdata.get('currentPrice')

        currency = qdata.get('currency', '')
        try:
            price_val = float(raw_price)
            if currency:
                return f"${price_val:,.2f} {currency}"
            return f"${price_val:,.2f}"
        except Exception:
            return str(raw_price) if raw_price not in (None, '') else 'N/A'

    def _rewrite_generic_followup(
        self,
        reply: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """Replace repetitive generic follow-up prompts with intent-aware options."""
        text = (reply or "").strip()
        if not text:
            return text

        generic_pattern = re.compile(
            r"Would you like me to run a full analysis for\s+"
            r"(?:<b>)?([A-Z0-9\.^]{1,10})(?:</b>)?"
            r",?\s*or\s*would\s*you\s*like\s*to\s*compare\s*it\s*to\s*another\s*stock\??",
            re.IGNORECASE,
        )
        if not generic_pattern.search(text):
            return text

        match = generic_pattern.search(text)
        ticker = (match.group(1).upper() if match else "") or self._extract_ticker_from_history(conversation_history)
        if not ticker:
            ticker = "this stock"

        question = (user_message or "").lower()
        replacement = (
            f"Would you like a quick snapshot for <b>{ticker}</b> "
            f"(price, valuation, and 52-week range), or latest news headlines?"
        )

        if any(k in question for k in ("news", "headline", "article", "press", "announcement")):
            replacement = (
                f"Want me to pull the latest 5 headlines for <b>{ticker}</b>, "
                f"or compare today's sentiment vs price move?"
            )
        elif any(k in question for k in ("price", "up", "down", "today", "performance", "trend", "chart", "volume")):
            replacement = (
                f"Want a quick performance snapshot for <b>{ticker}</b> "
                f"(price, day move, and range), or a side-by-side comparison with a peer?"
            )
        elif any(k in question for k in ("valuation", "pe", "p/e", "cheap", "expensive", "multiple")):
            replacement = (
                f"Want me to break down <b>{ticker}</b>'s valuation metrics, "
                f"or compare valuation against a competitor?"
            )
        elif any(k in question for k in ("company", "business", "ceo", "founded", "overview", "what is", "tell me about")):
            replacement = (
                f"Would you like a company snapshot for <b>{ticker}</b> "
                f"(business, key metrics, and recent headlines), or should I focus on one area?"
            )

        return generic_pattern.sub(replacement, text)

    def _build_ticker_hint(self, user_message: str) -> str:
        """Return a prompt hint listing exact ticker-like tokens from the user message.
        This prevents the LLM from mangling e.g. 'cmcsa' → 'CMSA'."""
        tokens = _TICKER_TOKEN_RE.findall(user_message)
        candidates = [
            t.upper() for t in tokens
            if t.lower() not in _SKIP_WORDS
        ]
        if not candidates:
            return ""
        unique = list(dict.fromkeys(candidates))  # deduplicate, preserve order
        items = ", ".join(f'"{c}"' for c in unique)
        return (
            f"[SYSTEM NOTE: The user message contains these exact strings: {items}. "
            f"When calling resolve_ticker, use the EXACT string as written above — "
            f"do NOT abbreviate, truncate, or alter it in any way.]"
        )

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

    def _append_citations_html(self, reply: str, citations: List[Dict[str, str]]) -> str:
        """Append unique clickable citations to the reply if available."""
        if not citations:
            return reply

        seen = set()
        unique: List[Dict[str, str]] = []
        for item in citations:
            url = normalize_result_url((item.get("url") or "").strip())
            if not url or url in seen:
                continue
            seen.add(url)
            unique.append({**item, "url": url})

        if not unique:
            return reply

        links = []
        for item in unique[:5]:
            title = item.get("title", "Source")
            source = item.get("source", "Source")
            url = item.get("url", "#")
            links.append(f"<li><a href=\"{url}\" target=\"_blank\" rel=\"noopener\">{title}</a> <span style='color:#94a3b8;'>({source})</span></li>")

        citations_html = "<br><br><b>Sources:</b><ul>" + "".join(links) + "</ul>"
        body = (reply or "").strip()
        if not body:
            return citations_html
        if "<b>Sources:</b>" in body:
            return body
        return body + citations_html

    def _looks_like_deal_news_query(self, user_message: str) -> bool:
        """Detect acquisition/deal/news intents that should include source links."""
        text = (user_message or "").lower()
        terms = (
            "acquisition", "acquire", "merger", "m&a", "deal", "agreement",
            "headline", "headlines", "news", "article", "articles", "report",
            "source", "sources",
        )
        return any(term in text for term in terms)

    def _fetch_fallback_web_citations(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Fetch web_search citations when the model answers without source tools."""
        anchor = self._extract_ticker_from_history(conversation_history)
        query = f"{anchor} {user_message}".strip() if anchor else user_message
        try:
            result_str, _ = self.executor.execute("web_search", {"query": query})
            return self._extract_citations("web_search", result_str)
        except Exception:
            return []

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

    def _build_analysis_html(self, result_data: Dict, ticker: str) -> str:
        recs = result_data.get("recommendations", {}) or {}
        price = result_data.get("price")
        currency = result_data.get("currency", "USD")
        company = result_data.get("company_name", ticker)

        # Preferred fallback: use the same formatter/card classes as run_full_analysis.
        if self.formatter:
            try:
                class _AnalysisFallback:
                    pass

                analysis = _AnalysisFallback()
                analysis.ticker = ticker
                analysis.company_name = company
                analysis.quote = {
                    "data": {
                        "price": price,
                        "currency": currency,
                        "name": company,
                    }
                }
                analysis.recommendations = recs
                analysis.news = {"news": []}
                analysis.price_history = {"dates": [], "prices": []}

                rendered = self.formatter.format_analysis_html(analysis)
                if rendered:
                    return rendered
            except Exception:
                pass

        # Last-resort fallback still emits class-based modern markup.
        def _badge(label: str) -> str:
            label_u = (label or "N/A").upper()
            class_map = {
                "STRONG BUY": "badge-strong-buy",
                "BUY": "badge-buy",
                "HOLD": "badge-hold",
                "SELL": "badge-sell",
            }
            icon_map = {
                "STRONG BUY": "▲▲",
                "BUY": "▲",
                "HOLD": "◆",
                "SELL": "▼",
            }
            css_class = class_map.get(label_u, "badge-na")
            icon = icon_map.get(label_u, "—")
            return f"<span class='badge {css_class}'>{icon} {label_u}</span>"

        def _row(title: str, data: Dict) -> str:
            label = data.get("label") or "N/A"
            summary = data.get("summary") or "No summary available"
            return (
                f"<div class='rec-row'>"
                f"<div>"
                f"<div class='rec-label'>{title}</div>"
                f"<div class='stock-price-line'>{summary}</div>"
                f"</div>"
                f"{_badge(label)}"
                f"</div>"
            )

        price_text = "N/A"
        if isinstance(price, (int, float)):
            price_text = f"${price:,.2f} {currency}"

        return (
            f"<div class='analysis-block stock-card' data-ticker='{ticker}'>"
            f"<div class='stock-card-header'>"
            f"<div>"
            f"<div class='stock-name'>{company}<span class='stock-ticker-badge'>{ticker}</span></div>"
            f"<div class='stock-price-line'>{price_text}</div>"
            f"</div>"
            f"</div>"
            f"<div class='rec-section'>"
            f"<div class='rec-section-title'>Time Horizon Recommendations</div>"
            f"{_row('Short-term (1 week)', recs.get('short_term', {}) or {})}"
            f"{_row('Medium-term (3 months)', recs.get('medium_term', {}) or {})}"
            f"{_row('Long-term (6-12 months)', recs.get('long_term', {}) or {})}"
            f"</div>"
            f"</div>"
        )
