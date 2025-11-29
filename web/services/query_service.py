"""
Query Service
Business logic for handling different types of user queries
"""

import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from repositories.stock_repository import IStockRepository
from services.llm_service import LLMService
from services.formatting_service import FormattingService
from src.tools.article_scraper import fetch_article_text
from src.tools.web_search import ddg_search


class QueryService:
    """
    Handles various query types: followups, earnings, news, comparisons
    Implements query parsing and LLM interaction logic
    """
    
    def __init__(
        self,
        repository: IStockRepository,
        llm_service: LLMService,
        formatting_service: FormattingService
    ):
        self.repository = repository
        self.llm = llm_service
        self.formatter = formatting_service
    
    def handle_followup(
        self,
        user_message: str,
        context: str,
        model_key: str
    ) -> str:
        """
        Handle follow-up questions about previous analysis
        Uses parallel LLM + web search with confidence-based selection
        
        Args:
            user_message: User's question
            context: Previous analysis HTML
            model_key: LLM model to use
            
        Returns:
            Response text (may include HTML)
        """
        # Check for contradictions in buy/sell questions
        contradiction_response = self._check_contradictions(user_message, context)
        if contradiction_response:
            return contradiction_response
        
        # Check for additional stock comparisons
        additional_data = self._detect_and_fetch_additional_stocks(user_message, context)
        
        # Build enhanced context
        enhanced_context = context
        instruction_suffix = ""
        
        if additional_data:
            enhanced_context += "\n\n<b>Additional Stock Data (for comparison):</b><br>" + additional_data
            instruction_suffix = (
                "\n\nIMPORTANT: I have fetched REAL DATA for the additional stock mentioned in the question. "
                "This data is shown in the 'Additional Stock Data' section above. "
                "USE THIS DATA DIRECTLY in your answer - do NOT suggest the user look it up elsewhere. "
                "Extract the specific metrics requested (PE ratio, price, market cap, etc.) from the data provided "
                "and present them clearly in your response."
            )
        
        # Run LLM and web search in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            llm_future = executor.submit(
                self._get_llm_response,
                user_message,
                enhanced_context,
                instruction_suffix,
                model_key
            )
            web_future = executor.submit(
                self._get_web_search_response,
                user_message,
                context
            )
            
            llm_response = llm_future.result()
            web_results = web_future.result()
        
        # Determine confidence and choose response
        return self._select_best_response(llm_response, web_results, model_key)
    
    def _get_llm_response(
        self,
        user_message: str,
        context: str,
        instruction_suffix: str,
        model_key: str
    ) -> Dict[str, Any]:
        """Get LLM response with confidence assessment"""
        prompt = (
            f"Here is the stock analysis context for reference (from yfinance and internal agents):\n{context}\n\n"
            f"Now answer the user's question: {user_message}\n\n"
            f"FORMATTING INSTRUCTIONS - Use HTML for proper display:\n"
            f"- Use <b>text</b> for bold important terms\n"
            f"- Use <br> for line breaks between paragraphs\n"
            f"- When listing multiple points, use proper HTML lists:\n"
            f"  * For bullet points: <ul><li>First point</li><li>Second point</li></ul>\n"
            f"  * For numbered lists: <ol><li>First</li><li>Second</li></ol>\n"
            f"- DO NOT use plain text bullets like '•', '-', or '*' - always use HTML <ul><li> tags\n"
            f"- For paragraphs, just use regular text with <br> between them\n"
            f"- Keep your response natural - use lists when appropriate, paragraphs when better\n"
            f"\nIMPORTANT: At the end of your response, add a confidence score on a new line:\n"
            f"CONFIDENCE: [HIGH/MEDIUM/LOW]\n"
            f"- HIGH: You have specific data from the context to answer completely\n"
            f"- MEDIUM: You can partially answer but some info might be missing\n"
            f"- LOW: The context doesn't contain enough information to answer well\n"
            f"{instruction_suffix}"
        )
        
        response = self.llm.generate(prompt, model_key)
        
        # Extract confidence level
        confidence_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)', response, re.IGNORECASE)
        confidence = confidence_match.group(1).upper() if confidence_match else 'MEDIUM'
        
        # Remove confidence marker from response
        clean_response = re.sub(r'\n?CONFIDENCE:\s*(HIGH|MEDIUM|LOW)\n?', '', response, flags=re.IGNORECASE)
        
        return {
            'response': clean_response.strip(),
            'confidence': confidence
        }
    
    def _get_web_search_response(self, user_message: str, context: str) -> Dict[str, Any]:
        """Get web search results for the question"""
        # Extract ticker from context for targeted search
        ticker_match = re.search(r'data-ticker="([^"]+)"', context)
        ticker = ticker_match.group(1) if ticker_match else ''
        
        # Build search query
        search_query = f"{ticker} {user_message}" if ticker else user_message
        
        try:
            results = ddg_search(search_query, max_results=3)
            return {
                'results': results,
                'query': search_query
            }
        except Exception as e:
            print(f"Web search failed: {e}")
            return {'results': [], 'query': search_query}
    
    def _select_best_response(
        self,
        llm_result: Dict[str, Any],
        web_result: Dict[str, Any],
        model_key: str
    ) -> str:
        """
        Select best response based on LLM confidence
        
        Args:
            llm_result: LLM response with confidence
            web_result: Web search results
            model_key: Model key for summarization
            
        Returns:
            Final response to user
        """
        confidence = llm_result.get('confidence', 'MEDIUM')
        llm_response = llm_result.get('response', '')
        web_results = web_result.get('results', [])
        
        # If high confidence, use LLM response
        if confidence == 'HIGH':
            return llm_response
        
        # If medium confidence and no web results, use LLM
        if confidence == 'MEDIUM' and not web_results:
            return llm_response
        
        # If low confidence, provide web links without summarizing
        if confidence == 'LOW' and web_results:
            links_html = self._format_web_links(web_results)
            return (
                f"I don't have enough information in the current analysis to answer this confidently. "
                f"Here are some relevant sources you can check:<br><br>{links_html}"
            )
        
        # If medium confidence with web results, show both
        if confidence == 'MEDIUM' and web_results:
            links_html = self._format_web_links(web_results)
            return (
                f"{llm_response}<br><br>"
                f"<b>Related sources for more information:</b><br>{links_html}"
            )
        
        # Fallback to LLM response
        return llm_response
    
    def _format_web_links(self, results: List[Dict]) -> str:
        """Format web search results as clickable links without summarization"""
        if not results:
            return "No additional sources found."
        
        links = []
        for i, result in enumerate(results[:5], 1):
            title = result.get('title', 'Source')
            url = result.get('url', '#')
            snippet = result.get('snippet', '')
            
            # Show snippet as preview without LLM summarization
            link_html = (
                f'{i}. <a href="{url}" target="_blank" style="color:#3b82f6;text-decoration:underline;">'
                f'<b>{title}</b></a><br>'
                f'<span style="color:#5a6c7d;font-size:0.9em;">{snippet[:150]}...</span>'
            )
            links.append(link_html)
        
        return '<br><br>'.join(links)
    
    def _check_contradictions(self, user_message: str, context: str) -> Optional[str]:
        """Check if user is asking about a contradictory recommendation"""
        try:
            requested_horizon = self._detect_horizon_from_message(user_message)
            stored_label = self._extract_label_for_horizon(context, requested_horizon)
            
            if stored_label:
                wants_sell = bool(re.search(
                    r"\bwhy\b.*\bsell\b|\bwhy is it a sell\b|\bwhy\s+sell\b|\bwhy.*\b(so )?sell\b",
                    user_message,
                    re.IGNORECASE
                ))
                wants_buy = bool(re.search(
                    r"\bwhy\b.*\bbuy\b|\bwhy is it a buy\b|\bwhy\s+buy\b|\bwhy.*\b(so )?buy\b",
                    user_message,
                    re.IGNORECASE
                ))
                
                if wants_sell and 'SELL' not in stored_label:
                    return (
                        f"The previous analysis rated the {requested_horizon} horizon as '<b>{stored_label}</b>'. "
                        f"I can't explain it as a 'sell' because the stored recommendation is {stored_label}. "
                        f"Would you like me to re-evaluate the stock for the {requested_horizon} horizon?"
                    )
                
                if wants_buy and ('BUY' not in stored_label and 'STRONG BUY' not in stored_label):
                    return (
                        f"The previous analysis rated the {requested_horizon} horizon as '<b>{stored_label}</b>'. "
                        f"I can't explain it as a 'buy' because the stored recommendation is {stored_label}. "
                        f"Would you like me to re-evaluate the stock for the {requested_horizon} horizon?"
                    )
        except Exception:
            pass
        
        return None
    
    def _extract_label_for_horizon(self, ctx: str, horizon: str) -> Optional[str]:
        """Extract recommendation label for given time horizon"""
        patterns = {
            'short': r"<b>Short-term.*?:\s*([^<]+)</b>",
            'medium': r"<b>Medium-term.*?:\s*([^<]+)</b>",
            'long': r"<b>Long-term.*?:\s*([^<]+)</b>"
        }
        pat = patterns.get(horizon)
        if not pat:
            return None
        
        m = re.search(pat, ctx, re.IGNORECASE)
        return m.group(1).strip().upper() if m else None
    
    def _detect_horizon_from_message(self, msg: str) -> str:
        """Detect time horizon from message"""
        msg = msg.lower()
        if 'short' in msg or '1 week' in msg or 'week' in msg:
            return 'short'
        if 'medium' in msg or '3 month' in msg or '3 months' in msg:
            return 'medium'
        if 'long' in msg or '6 month' in msg or '12 month' in msg:
            return 'long'
        return 'short'
    
    def _detect_and_fetch_additional_stocks(
        self,
        user_message: str,
        context: str
    ) -> str:
        """Detect and fetch data for additional stocks mentioned in comparison queries"""
        additional_tickers = self._extract_ticker_mentions(user_message, context)
        if not additional_tickers:
            return ''
        
        additional_data_parts = []
        
        for ticker in additional_tickers:
            try:
                # Get quote and info
                quote_result = self.repository.get_quote(ticker)
                if quote_result.get('status') != 'ok':
                    continue
                
                quote_data = quote_result.get('data', {})
                info = self.repository.get_stock_info(ticker)
                
                # Format comparison data
                pe_ratio = info.get('trailingPE', info.get('forwardPE', 'N/A'))
                market_cap = info.get('marketCap', 'N/A')
                
                if market_cap != 'N/A':
                    market_cap = f"${market_cap / 1e9:.2f}B" if market_cap >= 1e9 else f"${market_cap / 1e6:.2f}M"
                
                dividend_yield = info.get('dividendYield', 'N/A')
                if dividend_yield != 'N/A':
                    dividend_yield = f"{dividend_yield * 100:.2f}%"
                
                eps = info.get('trailingEps', 'N/A')
                revenue = info.get('totalRevenue', 'N/A')
                
                if revenue != 'N/A':
                    revenue = f"${revenue / 1e9:.2f}B" if revenue >= 1e9 else f"${revenue / 1e6:.2f}M"
                
                profit_margin = info.get('profitMargins', 'N/A')
                if profit_margin != 'N/A':
                    profit_margin = f"{profit_margin * 100:.2f}%"
                
                pe_display = f"<b style='font-size:1.1em;color:#2563eb;'>{pe_ratio:.2f}</b>" if isinstance(pe_ratio, (int, float)) else pe_ratio
                
                stock_html = f"""
<div style="margin:15px 0;padding:15px;background:#f0f9ff;border-left:4px solid #3b82f6;border-radius:6px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
    <div style="font-size:1.1em;margin-bottom:10px;"><b>{info.get('longName', ticker)} ({ticker})</b></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div><b>Current Price:</b> ${quote_data.get('price', 'N/A')} {quote_data.get('currency', '')}</div>
        <div><b>P/E Ratio:</b> {pe_display}</div>
        <div><b>Market Cap:</b> {market_cap}</div>
        <div><b>EPS:</b> {eps if eps != 'N/A' else 'N/A'}</div>
        <div><b>Revenue:</b> {revenue}</div>
        <div><b>Profit Margin:</b> {profit_margin}</div>
        <div><b>Dividend Yield:</b> {dividend_yield}</div>
    </div>
</div>
"""
                additional_data_parts.append(stock_html)
            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")
                continue
        
        return ''.join(additional_data_parts)
    
    def _extract_ticker_mentions(self, user_message: str, context: str) -> List[str]:
        """Extract ticker symbols mentioned in message (excluding current context ticker)"""
        # Extract current ticker from context
        current_ticker_match = re.search(r'data-ticker="([^"]+)"', context)
        current_ticker = current_ticker_match.group(1) if current_ticker_match else ''
        
        # Find tickers in message (uppercase 1-5 letter words or ^-prefixed)
        mentioned_tickers = re.findall(r'\b([A-Z]{1,5}|\^[A-Z0-9]+)\b', user_message)
        
        # Filter out current ticker and common words
        common_words = {'PE', 'EPS', 'CEO', 'CFO', 'NYSE', 'NASDAQ', 'USD', 'USA', 'AI', 'IT', 'VS'}
        additional_tickers = [
            t for t in mentioned_tickers
            if t != current_ticker and t not in common_words
        ]
        
        return additional_tickers[:3]  # Limit to 3 additional tickers
    
    def handle_earnings_query(self, ticker: str) -> str:
        """Handle earnings-specific queries"""
        earnings_result = self.repository.get_earnings(ticker)
        
        if earnings_result.get('status') != 'ok':
            return f"Could not fetch earnings for {ticker}."
        
        return self.formatter.format_earnings_html(ticker, earnings_result['data'])
    
    def handle_news_article(self, article: Dict[str, Any], model_key: str) -> str:
        """Handle news article summarization"""
        article_url = article.get('url', '')
        article_content = fetch_article_text(article_url) if article_url else ''
        
        article_text = (
            f"Headline: {article.get('headline', '')}\n"
            f"URL: {article_url}\n"
            f"Summary: {article.get('summary', '')}\n"
            f"Content: {article_content}"
        )
        
        prompt = (
            f"Here is a news article about a stock. Please summarize it in 2-3 sentences "
            f"for a general audience.\n{article_text}\n\n"
            f"IMPORTANT: Format your response using HTML:\n"
            f"- Use <b>text</b> for important terms\n"
            f"- Use <br> for line breaks\n"
            f"- Do NOT use markdown or plain text formatting\n"
            f"If you don't have enough information, say so."
        )
        
        return self.llm.generate(prompt, model_key)
    
    @staticmethod
    def extract_ticker_from_context(context: str, history: List) -> Optional[str]:
        """Extract ticker symbol from analysis context or history"""
        # Try to extract from data-ticker attribute in HTML
        match = re.search(r'data-ticker="([^"]+)"', context)
        if match:
            return match.group(1)
        
        # Try to find ticker pattern in history
        for msg in reversed(history):
            content = msg.get('content', '')
            ticker_match = re.search(r'\b([A-Z]{1,5})\b', content)
            if ticker_match:
                return ticker_match.group(1)
        
        return None
    
    @staticmethod
    def find_matching_article(user_message: str, news_articles: List[Dict]) -> Optional[Dict]:
        """Find news article matching user's query"""
        if not news_articles:
            return None
        
        msg_lower = user_message.lower()
        
        # Exclude common business/company questions that shouldn't match news
        business_question_patterns = [
            r'\bwhat (does|do|is)\b.*\b(company|business|they|it)\b.*\bdo\b',
            r'\b(describe|explain|tell me about)\b.*\b(business|company|products|services)\b',
            r'\bwhat (are|is) (their|its)\b.*\b(product|service|business)\b',
            r'\bhow (does|do)\b.*\b(make money|earn|revenue|operate)\b',
        ]
        
        for pattern in business_question_patterns:
            if re.search(pattern, msg_lower):
                return None
        
        # Only match if explicitly asking about news/articles
        explicit_news_patterns = [
            r'\b(first|second|third|fourth|fifth|[0-9]+)\s+(news|article|headline|story)',
            r'\b(summarize|summary of|tell me about|explain)\s+the\s+(first|second|third|article|news|headline)',
            r'\bwhat (does|is)\s+the\s+(first|second|third|latest)\s+(article|news|headline)',
        ]
        
        has_explicit_news = any(re.search(pattern, msg_lower) for pattern in explicit_news_patterns)
        
        if not has_explicit_news:
            return None
        
        # Try index-based matching
        idx_match = re.search(
            r'(first|second|third|fourth|fifth|[0-9]+)[^\w]*(news|article|headline)',
            msg_lower
        )
        
        if idx_match:
            idx_map = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4}
            idx_str = idx_match.group(1).lower()
            idx = idx_map.get(idx_str)
            
            if idx is None:
                try:
                    idx = int(idx_str) - 1
                except ValueError:
                    return None
            
            if 0 <= idx < len(news_articles):
                return news_articles[idx]
        
        return None
