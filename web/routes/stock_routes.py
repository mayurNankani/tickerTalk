"""
Stock Routes Blueprint
Main page and chat endpoints — agentic architecture
"""

import os
from flask import Blueprint, request, jsonify, session, Response
from typing import Any
from services.agent_service import AgentService


def init_stock_routes(agent_service: AgentService, **_kwargs):
    """
    Initialize stock routes.

    Args:
        agent_service: AgentService instance that owns the full agentic loop.
        **_kwargs: Ignored — kept for backwards-compat with app.py call site.
    """
    stock_bp = Blueprint('stock', __name__)

    @stock_bp.route('/')
    def index():
        """Serve the main HTML page"""
        try:
            routes_dir = os.path.dirname(os.path.abspath(__file__))
            web_dir = os.path.dirname(routes_dir)
            html_path = os.path.join(web_dir, 'index.html')
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return Response(content, mimetype='text/html')
        except Exception as e:
            return f"Error loading page: {e}", 500

    @stock_bp.route('/chat', methods=['POST'])
    def chat():
        """Single unified chat handler — agent decides what to do."""
        data = request.get_json() or {}
        # history from client: [{role, content}, ...] — plain text only, no HTML blobs
        client_history: list = data.get('history', [])
        model_key: str = data.get('model', 'gemma3')

        if not client_history:
            return jsonify({'reply': 'Please ask about a stock or company.'})

        user_message: str = client_history[-1].get('content', '')

        # Conversation history stored in session (plain text, small)
        # We use the session copy as source of truth, not the client copy,
        # to avoid injecting large HTML blobs back from the browser.
        conv_history: list = session.get('conversation_history', [])

        result = agent_service.run(
            user_message=user_message,
            conversation_history=conv_history,
            model_key=model_key,
        )

        reply: str = result.get('reply', '')
        tool_updates: list = result.get('tool_updates', [])
        analysis_html: str = result.get('analysis_html', '')

        # Persist conversation in session (plain text only)
        conv_history.append({'role': 'user', 'content': user_message})
        conv_history.append({'role': 'assistant', 'content': reply})
        # Keep last 20 turns to avoid session growth
        session['conversation_history'] = conv_history[-20:]
        session.modified = True

        response_payload: dict[str, Any] = {
            'reply': reply,
            'tool_updates': tool_updates,
        }
        if analysis_html:
            response_payload['analysis_html'] = analysis_html

        return jsonify(response_payload)

    return stock_bp

