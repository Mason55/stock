# src/strategies/__init__.py - Trading strategies module
"""
Production-ready trading strategies.

Available strategies:
- MovingAverageCrossover: Double MA strategy
- MeanReversion: Bollinger Bands + RSI strategy
- Momentum: Price momentum strategy
- BollingerBreakout: Bollinger Bands breakout/reversion strategy
- RSIReversal: RSI-based mean reversion strategy
- BollingerRSICombo: Combined Bollinger + RSI confirmation strategy
- GridTrading: Grid trading for range-bound markets
"""

from src.strategies.moving_average import MovingAverageCrossover
from src.strategies.mean_reversion import MeanReversion
from src.strategies.momentum import Momentum
from src.strategies.bollinger_breakout import BollingerBreakout
from src.strategies.rsi_reversal import RSIReversal
from src.strategies.boll_rsi_combo import BollingerRSICombo
from src.strategies.grid_trading import GridTrading

__all__ = [
    "MovingAverageCrossover",
    "MeanReversion",
    "Momentum",
    "BollingerBreakout",
    "RSIReversal",
    "BollingerRSICombo",
    "GridTrading",
]

# Strategy registry for easy loading by name
STRATEGY_REGISTRY = {
    "moving_average": MovingAverageCrossover,
    "mean_reversion": MeanReversion,
    "momentum": Momentum,
    "bollinger_breakout": BollingerBreakout,
    "rsi_reversal": RSIReversal,
    "boll_rsi_combo": BollingerRSICombo,
    "grid_trading": GridTrading,
}