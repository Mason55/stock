# src/services/__init__.py - Business services module
try:
    from .data_collector import DataCollector
except ImportError:
    DataCollector = None

try:
    from .recommendation_engine import RecommendationEngine
except ImportError:
    from .simple_recommendation import SimpleRecommendationEngine as RecommendationEngine

__all__ = ['DataCollector', 'RecommendationEngine']