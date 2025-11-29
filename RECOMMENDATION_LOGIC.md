# Stock Recommendation System - Complete Explanation

## Overview

The stock analysis system generates **buy/sell/hold recommendations** across **three time horizons** (short, medium, long-term) by combining **fundamental** and **technical analysis** with different weights based on the investment timeframe.

---

## 1. Fundamental Analysis Scoring

### Purpose
Evaluates the company's **financial health, profitability, and growth potential** using balance sheet and income statement data.

### Scoring System
- **Score starts at 0**
- Positive factors **add points** (+1 or +2)
- Negative factors **subtract points** (-1 or -2)
- Final score determines the label

### Metrics Analyzed

#### A. Valuation Metrics

**P/E Ratio (Price-to-Earnings)**
- **< 15**: +2 points (undervalued)
- **15-25**: +1 point (fair value)
- **> 40**: -1 point (overvalued)
- *Reasoning*: Lower P/E suggests the stock is cheaper relative to earnings

**PEG Ratio (P/E to Growth)**
- **< 1**: +2 points (growth justifies price)
- **1-2**: +1 point (reasonable)
- **> 3**: -1 point (overvalued for growth)
- *Reasoning*: PEG < 1 means you're paying less for growth than the growth rate

**Price-to-Book Ratio**
- **< 1**: +2 points (trading below book value)
- **1-3**: +1 point (fair)
- **> 5**: -1 point (expensive vs assets)
- *Reasoning*: Low P/B may indicate undervaluation, especially for asset-heavy companies

#### B. Growth Metrics

**Revenue Growth (YoY)**
- **> 20%**: +2 points (high growth)
- **10-20%**: +1 point (moderate growth)
- **< 0%**: -1 point (declining sales)
- *Reasoning*: Growing revenue indicates increasing demand and market share

**Earnings Growth (YoY)**
- **> 20%**: +2 points (strong profitability growth)
- **10-20%**: +1 point (healthy growth)
- **< 0%**: -1 point (shrinking profits)
- *Reasoning*: Profit growth shows the company is scaling efficiently

#### C. Financial Health Metrics

**Debt-to-Equity Ratio**
- **< 0.5**: +2 points (conservative leverage)
- **0.5-1.0**: +1 point (moderate debt)
- **> 2.0**: -1 point (high leverage risk)
- *Reasoning*: Lower debt means less financial risk and more flexibility

**Current Ratio (Short-term Liquidity)**
- **> 2.0**: +2 points (strong liquidity)
- **1.5-2.0**: +1 point (healthy)
- **< 1.0**: -1 point (liquidity concerns)
- *Reasoning*: Higher ratio means company can easily cover short-term obligations

#### D. Profitability Metrics

**Profit Margins**
- **> 20%**: +2 points (highly profitable)
- **10-20%**: +1 point (decent margins)
- **< 0%**: -2 points (losing money)
- *Reasoning*: Higher margins mean the company keeps more of each dollar earned

**Return on Equity (ROE)**
- **> 20%**: +2 points (excellent returns)
- **15-20%**: +1 point (good returns)
- **< 0%**: -1 point (destroying shareholder value)
- *Reasoning*: High ROE means the company efficiently generates profits from equity

### Fundamental Label Determination
```
Score >= 3:  STRONG BUY
Score 1-2:   BUY
Score -1 to 0: HOLD
Score < -1:  SELL
```

### Example Calculation
```
Company XYZ Analysis:
+ P/E = 12 → +2 (undervalued)
+ Revenue Growth = 25% → +2 (high growth)
+ Debt/Equity = 0.4 → +2 (low debt)
+ Profit Margin = 18% → +1 (moderate)
+ ROE = 22% → +2 (excellent)
─────────────────────────
Total Score = 9 → STRONG BUY

Reasons shown to user:
"Low P/E (12), High revenue growth (0.25), Low debt-to-equity (0.4), Moderate profit margins (0.18)"
```

---

## 2. Technical Analysis Scoring

### Purpose
Evaluates **price momentum, trends, and trading signals** using chart patterns and mathematical indicators.

### Scoring System
- **Signals start at 0**
- Bullish signals **add points** (+1 or +2)
- Bearish signals **subtract points** (-1 or -2)

### Indicators Analyzed

#### A. Momentum Oscillators

**RSI (Relative Strength Index, 0-100)**
- **< 30**: +2 (oversold, potential bounce)
- **30-40**: +1 (slightly oversold)
- **> 70**: -2 (overbought, potential pullback)
- **60-70**: -1 (slightly overbought)
- *Reasoning*: RSI shows if a stock has been sold or bought too aggressively

**Stochastic Oscillator (K & D lines, 0-100)**
- **Both < 20**: +2 (oversold)
- **Both > 80**: -2 (overbought)
- **K crosses above D**: +1 (bullish signal)
- **K crosses below D**: -1 (bearish signal)
- *Reasoning*: Measures where price is within recent range; crossovers signal changes

**MFI (Money Flow Index, 0-100)**
- **< 20**: +2 (money flowing out, oversold)
- **> 80**: -2 (money flowing in, overbought)
- *Reasoning*: Like RSI but considers volume; shows buying/selling pressure

#### B. Trend Indicators

**MACD (Moving Average Convergence Divergence)**
- **MACD > Signal Line**: +1 (bullish momentum)
- **MACD < Signal Line**: -1 (bearish momentum)
- **Histogram increasing**: +1 (strengthening trend)
- **Histogram decreasing**: -1 (weakening trend)
- *Reasoning*: Shows if short-term momentum is stronger than long-term

**ADX (Average Directional Index, 0-100)**
- **ADX > 25 + +DI > -DI**: +2 (strong uptrend)
- **ADX > 25 + -DI > +DI**: -2 (strong downtrend)
- **ADX < 20**: 0 (no clear trend)
- *Reasoning*: Measures trend strength; tells if a trend is worth following

**Moving Averages (SMA 20, SMA 50)**
- **Price > SMA 20**: +1 (short-term uptrend)
- **Price < SMA 20**: -1 (short-term downtrend)
- **Price > SMA 50**: +1 (medium-term uptrend)
- **Price < SMA 50**: -1 (medium-term downtrend)
- **SMA 20 crosses above SMA 50**: +2 (golden cross - strong bullish)
- **SMA 20 crosses below SMA 50**: -2 (death cross - strong bearish)
- *Reasoning*: Moving averages smooth out noise; price vs MA shows trend direction

#### C. Volatility Indicators

**Bollinger Bands Width**
- **Width < 0.05**: +1 (low volatility, potential breakout coming)
- **Width > 0.15**: -1 (high volatility, risk)
- *Reasoning*: Narrow bands often precede big moves; wide bands show uncertainty

**ATR (Average True Range)**
- **Increasing ATR**: -1 (volatility rising, risk)
- **Decreasing ATR**: +1 (volatility falling, stability)
- *Reasoning*: Higher volatility means bigger swings and more risk

#### D. Volume Indicators

**OBV (On-Balance Volume)**
- **OBV trending up with price**: +1 (volume confirms uptrend)
- **OBV trending down with price**: -1 (volume confirms downtrend)
- **OBV diverges from price**: Warning signal (not scored but noted)
- *Reasoning*: Volume should confirm price moves; divergence suggests weakness

### Technical Label Determination
```
Signals >= 3:  STRONG BUY
Signals 1-2:   BUY
Signals -1 to 0: HOLD
Signals < -1:  SELL
```

### Example Calculation
```
Stock ABC Technical Signals:
+ RSI = 28 → +2 (oversold)
+ Stochastic K=15, D=18 → +2 (oversold)
+ MACD > Signal → +1 (bullish momentum)
+ Price > SMA 20 → +1 (short-term uptrend)
+ ADX = 30, +DI > -DI → +2 (strong uptrend)
─────────────────────────
Total Signals = 8 → STRONG BUY

Reasons shown:
"RSI oversold (28), Stochastic oversold (K=15, D=18), MACD bullish, Price above SMA20"
```

---

## 3. Time Horizon Recommendations

The system generates **three different recommendations** based on investment timeframe:

### Short-Term (1 Week)
**Uses: Technical Analysis ONLY**

**Reasoning:**
- Short-term moves driven by **momentum and trader sentiment**
- Fundamentals don't change week-to-week
- Technical indicators capture market psychology

**Example:**
```
Technical Score: +5
→ Label: STRONG BUY
→ Summary: "RSI oversold (28), MACD bullish, Price above SMA20"
```

### Medium-Term (3 Months)
**Uses: 50% Technical + 50% Fundamental (Combined)**

**Reasoning:**
- Both fundamentals and technicals matter
- Fundamentals start influencing price over months
- Technical momentum can extend trends

**Calculation:**
```
Fundamental Label → Score:
  STRONG BUY = +2
  BUY = +1
  HOLD = 0
  SELL = -1

Technical Label → Same scoring

Combined Score = Fundamental Score + Technical Score

Combined >= 2:  STRONG BUY
Combined 1:     BUY
Combined -1 to 0: HOLD
Combined < -1:  SELL
```

**Example:**
```
Fundamental: BUY (+1)
Technical: STRONG BUY (+2)
Combined = +3 → STRONG BUY

Summary: "Fundamentals: High revenue growth, Low debt | Technical: RSI oversold, MACD bullish"
```

### Long-Term (6-12 Months)
**Uses: Fundamental Analysis ONLY**

**Reasoning:**
- Over months/years, **fundamentals drive value**
- Technical patterns become noise
- Company quality and growth determine returns

**Example:**
```
Fundamental Score: +7
→ Label: STRONG BUY
→ Summary: "Low P/E (12), High revenue growth (0.25), High profit margins (0.22)"
```

---

## 4. Why This Approach?

### Different Timeframes Need Different Lenses

**Day Traders (< 1 week):**
- Care about: Chart patterns, momentum, volume
- Don't care about: Whether the company will be profitable in 5 years
- Use: **Technical only**

**Swing Traders (1-3 months):**
- Care about: Both near-term momentum AND company health
- Want: Good companies with positive technical setup
- Use: **Balanced mix**

**Long-Term Investors (6+ months):**
- Care about: Business fundamentals, competitive position, growth
- Don't care about: Whether RSI is 65 or 70 today
- Use: **Fundamentals only**

### Real-World Example: Apple (AAPL)

**Scenario:** AAPL is down 15% in a week after earnings miss, but fundamentals are strong

```
Technical Analysis:
- RSI = 25 (oversold) → +2
- Price < SMA 20, SMA 50 → -2
- MACD bearish → -1
Total: -1 → HOLD

Fundamental Analysis:
- P/E = 18 → +1
- Revenue growth = 12% → +1
- Profit margin = 25% → +2
- ROE = 35% → +2
- Debt/Equity = 0.7 → +1
Total: +7 → STRONG BUY

RECOMMENDATIONS:
→ Short-term (1 week): HOLD (wait for momentum to turn)
→ Medium-term (3 months): BUY (fundamentals + oversold bounce)
→ Long-term (6-12 months): STRONG BUY (great business, temporary weakness)
```

**Investor Action:**
- **Day trader**: Stay out (momentum is bearish)
- **Swing trader**: Consider buying the dip (good company + oversold)
- **Long-term investor**: Strong buy (fundamentals excellent, ignore short-term noise)

---

## 5. Summary of Recommendation Logic

| Time Horizon | Weight | Logic | Best For |
|-------------|---------|-------|----------|
| **Short-term (1 week)** | 100% Technical | Momentum & chart patterns | Day/swing traders |
| **Medium-term (3 months)** | 50% Technical + 50% Fundamental | Balanced approach | Active investors |
| **Long-term (6-12 months)** | 100% Fundamental | Company quality & value | Buy-and-hold investors |

### Key Insights

1. **No single "right" recommendation** - it depends on your timeframe
2. **Scores are transparent** - you see exactly what metrics drove the decision
3. **Reasons are provided** - top 4 factors shown in summary
4. **Objective and systematic** - same rules applied to every stock
5. **Combines multiple signals** - reduces false positives from single indicators

### Limitations

- **Backward-looking**: Based on historical data
- **No market context**: Doesn't consider overall market conditions
- **No news events**: Major announcements can override technical/fundamental signals
- **Simple scoring**: Equal weights may not suit all sectors (e.g., tech vs utilities)
- **No risk adjustment**: Doesn't account for individual risk tolerance

---

## 6. How to Use These Recommendations

1. **Match to your timeframe**: Don't use short-term signals for long-term investing
2. **Look at all three**: Conflicting signals tell you something (e.g., good company, bad momentum)
3. **Read the reasons**: Understand WHY, not just the label
4. **Combine with research**: Use as a starting point, not the final decision
5. **Consider your risk**: STRONG BUY doesn't mean "bet everything"

**Example Decision Framework:**
- All three say STRONG BUY → High conviction
- Short/Medium BUY, Long HOLD → Trade not invest
- Short SELL, Long BUY → Good company, bad entry point (wait)
- All three say SELL → Strong signal to avoid/exit
