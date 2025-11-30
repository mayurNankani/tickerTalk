# Testing Old vs New Recommendation Systems

## Quick Start

### Method 1: Using the Test Script (Easiest)
```bash
./test_comparison.sh AAPL
./test_comparison.sh AAPL TSLA GOOGL MSFT
./test_comparison.sh QQQ SPY
```

### Method 2: Using Python Directly
```bash
.venv/bin/python compare_systems.py AAPL
.venv/bin/python compare_systems.py AAPL TSLA GOOGL
```

### Method 3: Interactive Python
```python
from src.agent import StockAnalysisAgent
from src.agent_improved import StockAnalysisAgentImproved

# Test old system
old = StockAnalysisAgent()
old_rec = old.get_recommendation("AAPL")
print(old_rec)

# Test new system
new = StockAnalysisAgentImproved()
new_rec = new.get_recommendation("AAPL")
print(new_rec)
```

## What to Look For

### 1. **Numerical Scores (New System Only)**
The new system provides 0-100 scores:
- **90-100**: Very strong signal (rare)
- **75-89**: Strong signal
- **60-74**: Moderate signal
- **40-59**: Neutral/weak signal
- **25-39**: Moderate negative
- **0-24**: Strong negative

### 2. **Confidence Percentages (New System Only)**
- **100%**: All 8 key fundamental metrics available
- **87.5%**: 7/8 metrics available
- **75%**: 6/8 metrics available
- **< 50%**: Low confidence, missing data

### 3. **Different Labels Near Thresholds**
The old system has hard cutoffs, so you might see:
- Old: **STRONG BUY** (score was 3)
- New: **BUY** (score was 62/100)

This is expected! The new system is more conservative.

### 4. **Better Differentiation**
Old system can't tell difference between:
- Stock A: STRONG BUY (score 3)
- Stock B: STRONG BUY (score 15)

New system shows:
- Stock A: STRONG BUY (score 76/100)
- Stock B: STRONG BUY (score 92/100)

## Test Cases to Try

### 1. High-Growth Tech Stock
```bash
./test_comparison.sh NVDA
```
**Expected**: New system should be less harsh on high PE ratios for growth stocks

### 2. Value Stock
```bash
./test_comparison.sh BAC
```
**Expected**: New system should reward low PE and good fundamentals

### 3. Declining Company
```bash
./test_comparison.sh F
```
**Expected**: New system should be more nuanced about negative growth

### 4. Index Fund
```bash
./test_comparison.sh SPY
```
**Expected**: Should be fairly neutral, balanced scores

### 5. High Debt Company
```bash
./test_comparison.sh TSLA
```
**Expected**: New system considers debt more carefully in context

## Real Example Output

```
COMPARING RECOMMENDATIONS FOR: AAPL
================================================================================

📊 OLD SYSTEM:
  Short-Term:   STRONG BUY
  Medium-Term:  STRONG BUY  
  Long-Term:    BUY

🚀 NEW SYSTEM:
  Short-Term:   HOLD (Score: 45.9/100, Confidence: 100%)
  Medium-Term:  HOLD (Score: 50.9/100, Confidence: 93.8%)
  Long-Term:    HOLD (Score: 54.3/100, Confidence: 87.5%)
```

**Why Different?**
- AAPL has high PE (37) → old system still gives +1, new system penalizes more
- Stochastic overbought → old system ignores intensity, new system weights it
- High debt-to-equity → old system misses it (not > 2), new system sees 1.8 as risky
- Combined: Old = optimistic, New = realistic

## Understanding Disagreements

### When Old Says BUY, New Says HOLD
**Likely Reason**: Stock is near a threshold
- Old: PE=24.9 → +1 (BUY)
- New: PE=24.9 → 0.55/1.0 (HOLD after weighting)

**Action**: Check the numerical score. If it's 55-59, it's marginal.

### When Old Says STRONG BUY, New Says BUY
**Likely Reason**: One or two metrics are borderline
- Old: Hit 3+ simple points
- New: Weighted score is 65-74 (good but not great)

**Action**: The new system is more conservative and realistic.

### When Both Agree
**Confidence**: High confidence in the recommendation
- Check new system's confidence % - if >80%, very reliable

## Backtesting (Advanced)

To see which system is more accurate historically:

```python
# Test on historical data (requires historical recommendations)
tickers = ["AAPL", "TSLA", "GOOGL", "MSFT", "AMZN"]
for ticker in tickers:
    old_rec = StockAnalysisAgent().get_recommendation(ticker)
    new_rec = StockAnalysisAgentImproved().get_recommendation(ticker)
    
    # Compare with actual 3-month performance
    # (would need historical price data)
```

## Switching to New System

Once you're confident, switch by editing `web/repositories/stock_repository.py`:

```python
# Change this:
from src.agent import StockAnalysisAgent

# To this:
from src.agent_improved import StockAnalysisAgentImproved as StockAnalysisAgent
```

## Customizing Weights (Advanced)

Edit `src/agent_improved.py` to adjust weights:

```python
# Line ~200: Increase PEG importance
peg_score * 5.0  # instead of 4.0

# Line ~250: Decrease debt penalty for tech stocks
SECTOR_WEIGHTS = {
    "Technology": {"growth": 1.5, "valuation": 0.7, "profitability": 1.3, "health": 0.6},
    # Changed health from 0.8 to 0.6 (less debt penalty)
}
```

## Common Questions

**Q: Why does new system give lower scores?**
A: It's more conservative and uses weighted continuous scoring, not binary thresholds.

**Q: Should I always trust the new system?**
A: Check the confidence %. If < 60%, data is incomplete.

**Q: Can I use both systems together?**
A: Yes! If they disagree, it means the stock is borderline - do more research.

**Q: Which timeframe is most important?**
A: Depends on your strategy:
- Day trading → Short-term (technical only)
- Swing trading → Medium-term (balanced)
- Long-term investing → Long-term (fundamental only)

## Files
- `compare_systems.py` - Main comparison script
- `test_comparison.sh` - Quick test wrapper
- `src/agent.py` - Old system
- `src/agent_improved.py` - New system
- `IMPROVEMENTS.md` - Detailed technical documentation
