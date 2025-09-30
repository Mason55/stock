# src/strategies/__init__.py - Trading strategies module
"""
Production-ready trading strategies.

Available strategies:
- MovingAverageCrossover: Double MA strategy
- MeanReversion: Bollinger Bands + RSI strategy
- Momentum: Price momentum strategy
- PairsTrading: Statistical arbitrage strategy
- MLPredictor: Machine learning based strategy
"""

from src.strategies.moving_average import MovingAverageCrossover
from src.strategies.mean_reversion import MeanReversion
from src.strategies.momentum import Momentum

__all__ = [
    'MovingAverageCrossover',
    'MeanReversion',
    'Momentum',
]