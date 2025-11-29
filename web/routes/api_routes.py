"""
API Routes Blueprint
RESTful endpoints for data fetching
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
from services import StockAnalysisService

api_bp = Blueprint('api', __name__, url_prefix='/api')


def init_api_routes(stock_service: StockAnalysisService):
    """
    Initialize API routes with injected dependencies
    
    Args:
        stock_service: StockAnalysisService instance
    """
    
    @api_bp.route('/price-history', methods=['GET'])
    def get_price_history():
        """Fetch price history for chart rendering"""
        ticker = request.args.get('ticker', '')
        period = request.args.get('period', '1mo')
        
        if not ticker:
            return jsonify({'error': 'Ticker is required'}), 400
        
        try:
            price_data = stock_service.repository.get_price_history(ticker, period)
            return jsonify(price_data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return api_bp
