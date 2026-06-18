#!/usr/bin/env python3
"""Automated Trading Strategy Engine — OKX via ccxt.

Strategies:
  grid     — Grid trading (ranging markets)
  trend    — EMA crossover (trending markets)
  bollinger— Bollinger Bands mean reversion
  scalper  — Quick scalping with tight stops

Usage:
  python engine.py backtest GRID BTC/USDT  -- run backtest
  python engine.py live GRID BTC/USDT      -- live trading (needs API key)
  python engine.py list                    -- list available strategies
"""

import time, json, sys, sqlite3
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB = DATA_DIR / "trade.db"

# ── Strategy Base ──────────────────────────────────────────────────

class Strategy(ABC):
    def __init__(self, symbol, params=None):
        self.symbol = symbol
        self.params = params or {}
        self.position = None  # "long", "short", None
        self.entry_price = 0
        self.trades = []
        self.pnl = 0
        self.bars = []  # OHLCV data

    @abstractmethod
    def on_bar(self, bar):
        """Called on each new candle. Return 'buy', 'sell', 'close', or None."""
        pass

    def get_name(self):
        return self.__class__.__name__

# ── Grid Strategy ──────────────────────────────────────────────────

class GridStrategy(Strategy):
    """Grid trading: place buy/sell orders at fixed intervals.
    Best in ranging/sideways markets. Not for strong trends."""

    def __init__(self, symbol, params=None):
        super().__init__(symbol, params)
        self.grid_size = self.params.get("grid_size", 0.5)  # % spacing
        self.grid_levels = self.params.get("grid_levels", 5)
        self.base_price = None
        self.levels = []
        self.filled_levels = set()

    def on_bar(self, bar):
        price = bar["close"]
        if self.base_price is None:
            self.base_price = price
            self._setup_grid(price)
            return None

        # Check grid levels
        for i, level in enumerate(self.levels):
            if i in self.filled_levels:
                continue
            if price <= level["buy"]:
                self.filled_levels.add(i)
                return "buy"
            elif price >= level["sell"] and self.position:
                self.filled_levels.add(i)
                return "sell"

        return None

    def _setup_grid(self, price):
        step = price * self.grid_size / 100
        self.levels = []
        for i in range(self.grid_levels):
            self.levels.append({
                "buy": price - step * (i + 1),
                "sell": price + step * (i + 1),
            })

# ── Trend Following (EMA Crossover) ────────────────────────────────

class TrendStrategy(Strategy):
    """EMA crossover: buy when fast EMA crosses above slow EMA.
    Best in trending markets."""

    def __init__(self, symbol, params=None):
        super().__init__(symbol, params)
        self.fast = self.params.get("fast", 9)
        self.slow = self.params.get("slow", 21)
        self.prev_fast_ema = None
        self.prev_slow_ema = None

    def ema(self, data, period):
        if len(data) < period:
            return sum(d["close"] for d in data) / len(data)
        k = 2 / (period + 1)
        ema = sum(d["close"] for d in data[:period]) / period
        for d in data[period:]:
            ema = d["close"] * k + ema * (1 - k)
        return ema

    def on_bar(self, bar):
        self.bars.append(bar)
        if len(self.bars) < self.slow + 1:
            return None

        fast_ema = self.ema(self.bars, self.fast)
        slow_ema = self.ema(self.bars, self.slow)

        if self.prev_fast_ema and self.prev_slow_ema:
            # Crossover: fast crosses above slow → buy
            if self.prev_fast_ema <= self.prev_slow_ema and fast_ema > slow_ema:
                self.prev_fast_ema = fast_ema
                self.prev_slow_ema = slow_ema
                return "buy"
            # Crossunder: fast crosses below slow → sell
            elif self.prev_fast_ema >= self.prev_slow_ema and fast_ema < slow_ema:
                self.prev_fast_ema = fast_ema
                self.prev_slow_ema = slow_ema
                return "sell"

        self.prev_fast_ema = fast_ema
        self.prev_slow_ema = slow_ema
        return None

# ── Bollinger Bands Mean Reversion ─────────────────────────────────

class BollingerStrategy(Strategy):
    """Buy when price touches lower band, sell when touches upper band."""

    def __init__(self, symbol, params=None):
        super().__init__(symbol, params)
        self.period = self.params.get("period", 20)
        self.std_dev = self.params.get("std_dev", 2.0)

    def bollinger(self):
        if len(self.bars) < self.period:
            return None, None, None
        closes = [b["close"] for b in self.bars[-self.period:]]
        sma = sum(closes) / len(closes)
        variance = sum((c - sma) ** 2 for c in closes) / len(closes)
        std = variance ** 0.5
        return sma, sma + self.std_dev * std, sma - self.std_dev * std

    def on_bar(self, bar):
        self.bars.append(bar)
        mid, upper, lower = self.bollinger()
        if mid is None:
            return None

        price = bar["close"]
        if price <= lower and not self.position:
            return "buy"
        elif price >= upper and self.position:
            return "sell"
        elif price >= mid and self.position == "short":
            return "close"
        return None

# ── Scalping Strategy ──────────────────────────────────────────────

class ScalperStrategy(Strategy):
    """Quick in-and-out trades with tight stop-loss and take-profit."""

    def __init__(self, symbol, params=None):
        super().__init__(symbol, params)
        self.tp_pct = self.params.get("tp_pct", 0.3)  # Take profit %
        self.sl_pct = self.params.get("sl_pct", 0.2)  # Stop loss %
        self.rsi_period = self.params.get("rsi_period", 7)
        self.rsi_oversold = self.params.get("rsi_oversold", 30)
        self.rsi_overbought = self.params.get("rsi_overbought", 70)

    def rsi(self):
        if len(self.bars) < self.rsi_period + 1:
            return 50
        closes = [b["close"] for b in self.bars[-(self.rsi_period+1):]]
        gains, losses = 0, 0
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            if diff > 0: gains += diff
            else: losses -= diff
        if losses == 0: return 100
        rs = (gains / self.rsi_period) / (losses / self.rsi_period)
        return 100 - (100 / (1 + rs))

    def on_bar(self, bar):
        self.bars.append(bar)
        rsi_val = self.rsi()

        if self.position:
            # Check take profit / stop loss
            pnl_pct = (bar["close"] - self.entry_price) / self.entry_price * 100
            if self.position == "long":
                if pnl_pct >= self.tp_pct or pnl_pct <= -self.sl_pct:
                    return "sell"
            else:
                if pnl_pct <= -self.tp_pct or pnl_pct >= self.sl_pct:
                    return "close"
        else:
            if rsi_val < self.rsi_oversold:
                return "buy"
            elif rsi_val > self.rsi_overbought:
                return "sell"
        return None

# ── Strategy Registry ──────────────────────────────────────────────

STRATEGIES = {
    "grid": GridStrategy,
    "trend": TrendStrategy,
    "bollinger": BollingerStrategy,
    "scalper": ScalperStrategy,
}

# ── Backtesting Engine ─────────────────────────────────────────────

def backtest(strategy_class, symbol, bars, params=None, initial_capital=1000):
    """Run a backtest and return results."""
    strat = strategy_class(symbol, params)
    capital = initial_capital
    position = None  # "long", "short", None
    entry_price = 0
    quantity = 0
    trades = []

    for i, bar in enumerate(bars):
        signal = strat.on_bar(bar)
        price = bar["close"]

        if signal == "buy" and not position:
            quantity = (capital * 0.95) / price  # Use 95% of capital
            entry_price = price
            position = "long"
        elif signal == "sell" and position == "long":
            pnl = (price - entry_price) * quantity
            capital += pnl
            trades.append({
                "entry": entry_price, "exit": price,
                "pnl": pnl, "pnl_pct": (price/entry_price - 1) * 100,
                "bar_index": i,
            })
            position = None
            quantity = 0

    # Close any open position at last price
    if position and bars:
        final_price = bars[-1]["close"]
        pnl = (final_price - entry_price) * quantity
        capital += pnl
        trades.append({
            "entry": entry_price, "exit": final_price,
            "pnl": pnl, "pnl_pct": (final_price/entry_price - 1) * 100,
            "bar_index": len(bars) - 1,
        })

    total_return = (capital - initial_capital) / initial_capital * 100
    wins = len([t for t in trades if t["pnl"] > 0])
    win_rate = wins / len(trades) * 100 if trades else 0

    return {
        "strategy": strat.get_name(),
        "symbol": symbol,
        "initial_capital": initial_capital,
        "final_capital": round(capital, 2),
        "total_return_pct": round(total_return, 2),
        "trades": len(trades),
        "win_rate": round(win_rate, 1),
        "trade_list": trades[-10:],
        "params": params,
    }

# ── Fetch Historical Data ──────────────────────────────────────────

def fetch_ohlcv(symbol, timeframe="1h", limit=500):
    """Fetch historical OHLCV data from OKX via ccxt."""
    import ccxt
    ex = ccxt.okx({"enableRateLimit": True})
    try:
        raw = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
        return [{"timestamp": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]} for r in raw]
    except Exception as e:
        print(f"❌ Data fetch error: {e}")
        return []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python engine.py <command>")
        print("  backtest <strategy> <symbol>   Run backtest")
        print("  list                           List strategies")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        print("📋 Available strategies:")
        for name, cls in STRATEGIES.items():
            print(f"  {name:12} — {cls.__doc__[:60] if cls.__doc__ else ''}")

    elif cmd == "backtest":
        if len(sys.argv) < 4:
            print("Usage: backtest <strategy> <symbol>")
            sys.exit(1)

        strat_name = sys.argv[2].lower()
        symbol = sys.argv[3].upper()
        timeframe = sys.argv[4] if len(sys.argv) > 4 else "1h"

        if strat_name not in STRATEGIES:
            print(f"❌ Unknown strategy: {strat_name}")
            print(f"   Available: {list(STRATEGIES.keys())}")
            sys.exit(1)

        print(f"📊 Backtesting {strat_name.upper()} on {symbol} ({timeframe})...")
        bars = fetch_ohlcv(symbol, timeframe)
        if not bars:
            print("❌ No data fetched")
            sys.exit(1)

        print(f"   Loaded {len(bars)} candles")
        result = backtest(STRATEGIES[strat_name], symbol, bars)

        print(f"\n{'='*50}")
        print(f"  Strategy:    {result['strategy']}")
        print(f"  Symbol:      {result['symbol']}")
        print(f"  Capital:     ${result['initial_capital']} → ${result['final_capital']}")
        print(f"  Return:      {result['total_return_pct']}%")
        print(f"  Trades:      {result['trades']}")
        print(f"  Win Rate:    {result['win_rate']}%")
        print(f"{'='*50}")

        if result['trade_list']:
            print(f"\n  Recent trades:")
            for t in result['trade_list'][-5:]:
                emoji = "✅" if t['pnl'] > 0 else "❌"
                print(f"    {emoji} {t['entry']:.2f} → {t['exit']:.2f} | {t['pnl']:+.2f} ({t['pnl_pct']:+.2f}%)")
