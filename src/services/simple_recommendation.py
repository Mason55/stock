# src/services/simple_recommendation.py - Simplified recommendation engine without ML dependencies
import logging
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from src.models.stock import StockPrice

logger = logging.getLogger(__name__)


class SimpleRecommendationEngine:
    """Simple rule-based recommendation engine for minimal dependencies"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        
    def get_latest_recommendation(self, stock_code: str) -> Optional[Dict]:
        """Generate simple recommendation based on basic rules"""
        try:
            # Get latest price data
            latest_price = self.db_session.query(StockPrice).filter_by(
                stock_code=stock_code
            ).order_by(StockPrice.timestamp.desc()).first()
            
            if not latest_price:
                return None
            
            # Simple rule-based recommendation
            change_pct = latest_price.change_pct or 0
            
            if change_pct > 5:
                action = '买入'
                confidence = 0.8
                risk_level = '中等风险'
            elif change_pct > 0:
                action = '持有'
                confidence = 0.6
                risk_level = '低风险'
            elif change_pct > -5:
                action = '观望'
                confidence = 0.5
                risk_level = '中等风险'
            else:
                action = '观望'
                confidence = 0.7
                risk_level = '高风险'
            
            return {
                'action': action,
                'confidence': confidence,
                'score': confidence * 10,
                'risk_level': risk_level,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return None
    
    def predict_recommendation(self, stock_code: str) -> Optional[Dict]:
        """Alias for get_latest_recommendation for compatibility"""
        return self.get_latest_recommendation(stock_code)
    
    def extract_features(self, stock_code: str) -> Optional[Dict]:
        """Extract basic features for analysis"""
        try:
            latest_price = self.db_session.query(StockPrice).filter_by(
                stock_code=stock_code
            ).order_by(StockPrice.timestamp.desc()).first()
            
            if not latest_price:
                return None
            
            return {
                'current_price': latest_price.close_price,
                'volume': latest_price.volume,
                'change_pct': latest_price.change_pct,
                'volatility': abs(latest_price.change_pct or 0),
                'timestamp': latest_price.timestamp.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None