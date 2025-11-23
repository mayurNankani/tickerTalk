import yfinance as yf
import pandas as pd
import ta
from typing import Dict, Any
from .base import AnalysisTool

class TechnicalAnalysis(AnalysisTool):
    def analyze(self, ticker: str) -> Dict[str, Any]:
        """
        Perform technical analysis on a stock.
        
        Args:
            ticker (str): The stock ticker symbol
            
        Returns:
            Dict[str, Any]: Technical analysis results
        """
        try:
            # Get historical data
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y")
            
            # Calculate technical indicators
            
            # Momentum Indicators
            # RSI
            df['RSI'] = ta.momentum.RSIIndicator(df['Close']).rsi()
            
            # Stochastic Oscillator
            stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
            df['STOCH_K'] = stoch.stoch()
            df['STOCH_D'] = stoch.stoch_signal()
            
            # Ultimate Oscillator
            df['UO'] = ta.momentum.UltimateOscillator(df['High'], df['Low'], df['Close']).ultimate_oscillator()
            
            # Trend Indicators
            # MACD
            macd = ta.trend.MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['MACD_Signal'] = macd.macd_signal()
            df['MACD_Hist'] = macd.macd_diff()
            
            # ADX (Average Directional Index)
            adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'])
            df['ADX'] = adx.adx()
            df['ADX_POS'] = adx.adx_pos()
            df['ADX_NEG'] = adx.adx_neg()
            
            # Volatility Indicators
            # Bollinger Bands
            bollinger = ta.volatility.BollingerBands(df['Close'])
            df['BB_Upper'] = bollinger.bollinger_hband()
            df['BB_Lower'] = bollinger.bollinger_lband()
            df['BB_MA'] = bollinger.bollinger_mavg()
            df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_MA']
            
            # Average True Range
            df['ATR'] = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range()
            
            # Volume Indicators
            # On-Balance Volume
            df['OBV'] = ta.volume.OnBalanceVolumeIndicator(df['Close'], df['Volume']).on_balance_volume()
            
            # Money Flow Index
            df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume']).money_flow_index()
            
            # Get moving averages
            df['SMA_20'] = ta.trend.SMAIndicator(df['Close'], window=20).sma_indicator()
            df['SMA_50'] = ta.trend.SMAIndicator(df['Close'], window=50).sma_indicator()
            df['EMA_20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()
            
            # Get the most recent values
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            analysis = {
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
                "ema_20": latest['EMA_20'],
                
                # Trend Signals
                "above_sma_20": latest['Close'] > latest['SMA_20'],
                "above_sma_50": latest['Close'] > latest['SMA_50'],
                "sma_20_cross_50": (prev['SMA_20'] <= prev['SMA_50'] and latest['SMA_20'] > latest['SMA_50'])
            }
            
            return analysis
            
        except Exception as e:
            return {
                "error": str(e)
            }