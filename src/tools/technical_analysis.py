"""
Technical Analysis Tool
Analyzes technical indicators including momentum, trend, volatility, and volume.
"""

import yfinance as yf
import pandas as pd
import ta
from typing import Dict, Any
from .base import AnalysisTool, ToolResult, ResultStatus


class TechnicalAnalysis(AnalysisTool):
    """Performs technical analysis on stocks using price and volume data"""
    
    def analyze(self, ticker: str, period: str = "1y", **kwargs) -> ToolResult:
        """
        Perform comprehensive technical analysis on a stock.
        
        Args:
            ticker: The stock ticker symbol
            period: Historical data period (default: 1y)
            **kwargs: Additional parameters
            
        Returns:
            ToolResult containing technical indicators
        """
        # Validate ticker
        if not self._validate_ticker(ticker):
            return ToolResult(
                status=ResultStatus.ERROR,
                error="Invalid ticker format"
            )
        
        try:
            ticker = ticker.upper().strip()
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            
            # Check if we have enough data
            if df.empty or len(df) < 50:
                return ToolResult(
                    status=ResultStatus.NO_DATA,
                    error=f"Insufficient historical data for {ticker}"
                )
            
            # Calculate all technical indicators
            df = self._calculate_indicators(df)
            
            # Extract latest values
            analysis_data = self._extract_latest_values(df)
            
            return ToolResult(
                status=ResultStatus.SUCCESS,
                data=analysis_data,
                metadata={
                    'ticker': ticker,
                    'period': period,
                    'data_points': len(df)
                }
            )
            
        except Exception as e:
            return self._handle_error(e, ticker)
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators on the dataframe"""
        
        # Momentum Indicators
        df['RSI'] = ta.momentum.RSIIndicator(df['Close']).rsi()
        
        stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
        df['STOCH_K'] = stoch.stoch()
        df['STOCH_D'] = stoch.stoch_signal()
        
        df['UO'] = ta.momentum.UltimateOscillator(
            df['High'], df['Low'], df['Close']
        ).ultimate_oscillator()
        
        # Trend Indicators
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
        
        adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'])
        df['ADX'] = adx.adx()
        df['ADX_POS'] = adx.adx_pos()
        df['ADX_NEG'] = adx.adx_neg()
        
        # Volatility Indicators
        bollinger = ta.volatility.BollingerBands(df['Close'])
        df['BB_Upper'] = bollinger.bollinger_hband()
        df['BB_Lower'] = bollinger.bollinger_lband()
        df['BB_MA'] = bollinger.bollinger_mavg()
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_MA']
        
        df['ATR'] = ta.volatility.AverageTrueRange(
            df['High'], df['Low'], df['Close']
        ).average_true_range()
        
        # Volume Indicators
        df['OBV'] = ta.volume.OnBalanceVolumeIndicator(
            df['Close'], df['Volume']
        ).on_balance_volume()
        
        df['MFI'] = ta.volume.MFIIndicator(
            df['High'], df['Low'], df['Close'], df['Volume']
        ).money_flow_index()
        
        # Moving Averages
        df['SMA_20'] = ta.trend.SMAIndicator(df['Close'], window=20).sma_indicator()
        df['SMA_50'] = ta.trend.SMAIndicator(df['Close'], window=50).sma_indicator()
        df['SMA_200'] = ta.trend.SMAIndicator(df['Close'], window=200).sma_indicator()
        df['EMA_20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
        
        return df
    
    def _extract_latest_values(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract latest technical indicator values"""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        return {
            # Price and Volume
            "current_price": latest['Close'],
            "volume": latest['Volume'],
            "price_change": (latest['Close'] - prev['Close']) / prev['Close'] * 100,
            
            # Momentum Indicators
            "rsi": latest['RSI'],
            "stoch_k": latest['STOCH_K'],
            "stoch_d": latest['STOCH_D'],
            "ultimate_oscillator": latest['UO'],
            
            # Trend Indicators
            "macd": latest['MACD'],
            "macd_signal": latest['MACD_Signal'],
            "macd_hist": latest['MACD_Hist'],
            "adx": latest['ADX'],
            "adx_positive": latest['ADX_POS'],
            "adx_negative": latest['ADX_NEG'],
            
            # Volatility Indicators
            "bb_upper": latest['BB_Upper'],
            "bb_lower": latest['BB_Lower'],
            "bb_middle": latest['BB_MA'],
            "bb_width": latest['BB_Width'],
            "atr": latest['ATR'],
            
            # Volume Indicators
            "obv": latest['OBV'],
            "mfi": latest['MFI'],
            
            # Moving Averages
            "sma_20": latest['SMA_20'],
            "sma_50": latest['SMA_50'],
            "sma_200": latest['SMA_200'],
            "ema_20": latest['EMA_20'],
            
            # Trend Signals
            "above_sma_20": latest['Close'] > latest['SMA_20'],
            "above_sma_50": latest['Close'] > latest['SMA_50'],
            "above_sma_200": latest['Close'] > latest['SMA_200'],
            "sma_20_cross_50": (
                prev['SMA_20'] <= prev['SMA_50'] and 
                latest['SMA_20'] > latest['SMA_50']
            ),
            "sma_50_cross_200": (
                prev['SMA_50'] <= prev['SMA_200'] and 
                latest['SMA_50'] > latest['SMA_200']
            )
        }
