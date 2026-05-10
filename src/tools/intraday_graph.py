import yfinance as yf
import matplotlib.pyplot as plt
import os
from datetime import datetime

import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os
from datetime import datetime

def save_intraday_graph(ticker: str, out_dir: str = "web/static") -> str:
    """(Deprecated) Intraday price graph generator.

    Currently unused in the refactored architecture. Retained for future
    planned visualization enhancements. Safe to remove if storage or
    dependency footprint (matplotlib) becomes undesirable.

    Returns:
        Relative path to saved image or empty string if generation failed.
    """
    # Download today's 1m interval data
    try:
        df = yf.download(tickers=ticker, period="1d", interval="5m")
        if df.empty:
            print(f"[intraday_graph] No intraday data for {ticker}")
            return ""
        plt.figure(figsize=(7, 3))
        plt.plot(df.index, df['Close'], label=f"{ticker} intraday")
        plt.title(f"{ticker} - Today's Performance")
        plt.xlabel("Time")
        plt.ylabel("Price")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        # Save to static directory with timestamp to avoid caching
        os.makedirs(out_dir, exist_ok=True)
        fname = f"{ticker}_intraday_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        fpath = os.path.join(out_dir, fname)
        plt.savefig(fpath)
        plt.close()
        print(f"[intraday_graph] Saved intraday graph for {ticker} at {fpath}")
        # Return relative path for HTML
        return f"static/{fname}"
    except Exception as e:
        print(f"[intraday_graph] Error generating graph for {ticker}: {e}")
        return ""
