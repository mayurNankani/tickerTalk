"""
Repositories Package
Data access layer components
"""

from .stock_repository import IStockRepository, StockRepository

__all__ = ['IStockRepository', 'StockRepository']
