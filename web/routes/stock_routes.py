"""
Stock Routes Blueprint
Main page and chat endpoints
"""

import os
import re
from flask import Blueprint, request, jsonify, session, Response
from typing import Dict, Any, List
from services import StockAnalysisService, QueryService


stock_bp = Blueprint('stock', __name__)


def init_stock_routes(
    stock_service: StockAnalysisService,
    query_service: QueryService,
    formatting_service
):
    """
    Initialize stock routes with injected dependencies
    
    Args:
        stock_service: StockAnalysisService instance
        query_service: QueryService instance
        formatting_service: FormattingService instance
    """
    
    @stock_bp.route('/')
    def index():
        """Serve the main HTML page"""
        try:
            # Get the web directory (parent of routes/)
            routes_dir = os.path.dirname(os.path.abspath(__file__))
            web_dir = os.path.dirname(routes_dir)
            html_path = os.path.join(web_dir, 'index.html')
            
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return Response(content, mimetype='text/html')
        except Exception as e:
            print(f"Error serving index.html: {e}")
            print(f"Attempted path: {html_path if 'html_path' in locals() else 'N/A'}")
            return f"Error loading page: {e}", 500
    
    @stock_bp.route('/chat', methods=['POST'])
    def chat():
        """Handle chat messages and stock queries"""
        data = request.get_json()
        history = data.get('history', [])
        model_key = data.get('model', 'llama3')
        
        if not history:
            return jsonify({'reply': 'Please ask about a stock or company.'})
        
        user_message = history[-1]['content']
        
        # Handle earnings queries
        if 'earnings' in user_message.lower():
            return _handle_earnings(user_message, history)
        
        # Handle initial stock query
        if len(history) == 1 or not session.get('analysis_context'):
            return _handle_stock_query(user_message, model_key)
        
        # Handle news article queries
        news_articles = session.get('last_news_articles', [])
        matched_article = query_service.find_matching_article(user_message, news_articles)
        if matched_article:
            return _handle_news_article(matched_article, model_key)
        
        # Handle general follow-up questions
        return _handle_followup(user_message, model_key)
    
    def _handle_stock_query(company_name: str, model_key: str) -> Dict:
        """Handle initial stock analysis query"""
        try:
            print(f"[DEBUG] _handle_stock_query called with: {company_name}")
            
            # Special handling for explicit index requests from the UI
            # Format expected from client: "index:^GSPC|S&P 500" (symbol|friendly name)
            if company_name.lower().startswith('index:'):
                try:
                    payload = company_name.split(':', 1)[1]
                    if '|' in payload:
                        symbol, friendly = payload.split('|', 1)
                    else:
                        symbol, friendly = payload, payload
                    
                    match = {'symbol': symbol.strip(), 'long_name': friendly.strip()}
                    print(f"[DEBUG] Index match: {match}")
                except Exception as e:
                    print(f"[ERROR] Index parsing failed: {e}")
                    return jsonify({'reply': 'Invalid index selection.'})
            else:
                # Try ticker detection and validation first
                print(f"[DEBUG] Calling find_ticker for: {company_name}")
                match = stock_service.find_ticker(company_name)
                print(f"[DEBUG] find_ticker returned: {match}, type: {type(match)}")
                
                if not match:
                    return jsonify({
                        'reply': f"No matching companies found for '{company_name}'."
                    })
            
            # Get analysis - handle both dict (from index) and CompanyMatch object
            if isinstance(match, dict):
                ticker = match['symbol']
                company_full_name = match.get('long_name') or match.get('short_name') or company_name
                print(f"[DEBUG] Dict match - ticker: {ticker}, name: {company_full_name}")
            else:
                ticker = match.symbol
                company_full_name = match.long_name or match.short_name or company_name
                print(f"[DEBUG] CompanyMatch - ticker: {ticker}, name: {company_full_name}")
            
            analysis = stock_service.get_analysis(ticker, company_full_name)
            print(f"[DEBUG] Analysis completed for {ticker}")
        except Exception as e:
            print(f"[ERROR] Exception in _handle_stock_query: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'reply': f"Error processing query: {str(e)}"})
        
        # Format HTML
        result_html = formatting_service.format_analysis_html(analysis)
        
        # Store in session
        session['analysis_context'] = result_html
        session['last_news_articles'] = analysis.news.get('news', [])
        
        return jsonify({'reply': result_html})
    
    def _handle_earnings(user_message: str, history: List) -> Dict:
        """Handle earnings-specific queries"""
        # Extract ticker from context
        context = session.get('analysis_context', '')
        ticker = query_service.extract_ticker_from_context(context, history)
        
        if not ticker:
            return jsonify({
                'reply': "Could not determine ticker for earnings lookup."
            })
        
        # Get earnings HTML
        earnings_html = query_service.handle_earnings_query(ticker)
        return jsonify({'reply': earnings_html})
    
    def _handle_news_article(article: Dict, model_key: str) -> Dict:
        """Handle news article summarization"""
        reply = query_service.handle_news_article(article, model_key)
        return jsonify({'reply': reply})
    
    def _handle_followup(user_message: str, model_key: str) -> Dict:
        """Handle general follow-up questions"""
        context = session.get('analysis_context', '')
        reply = query_service.handle_followup(user_message, context, model_key)
        return jsonify({'reply': reply})
    
    return stock_bp
