# src/services/recommendation_engine.py - ML-based recommendation engine
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import shap
from sqlalchemy.orm import Session
from src.models.stock import StockPrice, StockRecommendation


class RecommendationEngine:
    """ML-based stock recommendation engine"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.explainer = None
    
    def calculate_technical_indicators(self, prices_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators from price data"""
        df = prices_df.copy()
        
        # Moving averages
        df['ma_5'] = df['close_price'].rolling(window=5).mean()
        df['ma_20'] = df['close_price'].rolling(window=20).mean()
        df['ma_60'] = df['close_price'].rolling(window=60).mean()
        
        # RSI calculation
        delta = df['close_price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close_price'].ewm(span=12).mean()
        exp2 = df['close_price'].ewm(span=26).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        
        # Bollinger Bands
        rolling_mean = df['close_price'].rolling(window=20).mean()
        rolling_std = df['close_price'].rolling(window=20).std()
        df['bb_upper'] = rolling_mean + (rolling_std * 2)
        df['bb_lower'] = rolling_mean - (rolling_std * 2)
        band_width = df['bb_upper'] - df['bb_lower']
        df['bb_position'] = np.where(
            band_width != 0,
            (df['close_price'] - df['bb_lower']) / band_width,
            np.nan
        )

        # KDJ stochastic oscillator
        low_min = df['low_price'].rolling(window=9).min()
        high_max = df['high_price'].rolling(window=9).max()
        rsv = np.where(
            (high_max - low_min) == 0,
            0,
            (df['close_price'] - low_min) / (high_max - low_min) * 100
        )
        rsv_series = pd.Series(rsv, index=df.index).fillna(0)
        df['kdj_k'] = rsv_series.ewm(alpha=1/3, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(alpha=1/3, adjust=False).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']

        # Average True Range
        prev_close = df['close_price'].shift(1)
        tr_components = pd.concat([
            df['high_price'] - df['low_price'],
            (df['high_price'] - prev_close).abs(),
            (df['low_price'] - prev_close).abs()
        ], axis=1)
        true_range = tr_components.max(axis=1)
        df['atr'] = true_range.rolling(window=14).mean()
        df['atr_percent'] = (df['atr'] / df['close_price']).replace([np.inf, -np.inf], np.nan) * 100

        # Volume indicators
        df['volume_ma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']

        return df
    
    def extract_features(self, stock_code: str, days_back: int = 60) -> Optional[Dict]:
        """Extract features for a specific stock"""
        try:
            # Get price data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            prices = self.db_session.query(StockPrice).filter(
                StockPrice.stock_code == stock_code,
                StockPrice.timestamp >= start_date
            ).order_by(StockPrice.timestamp).all()
            
            if len(prices) < 30:  # Need minimum data
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame([{
                'timestamp': p.timestamp,
                'open_price': p.open_price,
                'high_price': p.high_price,
                'low_price': p.low_price,
                'close_price': p.close_price,
                'volume': p.volume,
                'change_pct': p.change_pct
            } for p in prices])
            
            # Calculate technical indicators
            df = self.calculate_technical_indicators(df)
            
            # Get latest values
            latest = df.iloc[-1]
            
            features = {
                'price_momentum_5d': (latest['close_price'] / df['close_price'].iloc[-6] - 1) * 100 if len(df) > 5 else 0,
                'price_momentum_20d': (latest['close_price'] / df['close_price'].iloc[-21] - 1) * 100 if len(df) > 20 else 0,
                'ma_5_ratio': latest['close_price'] / latest['ma_5'] if pd.notna(latest['ma_5']) else 1,
                'ma_20_ratio': latest['close_price'] / latest['ma_20'] if pd.notna(latest['ma_20']) else 1,
                'rsi': latest['rsi'] if pd.notna(latest['rsi']) else 50,
                'macd': latest['macd'] if pd.notna(latest['macd']) else 0,
                'bb_position': latest['bb_position'] if pd.notna(latest['bb_position']) else 0.5,
                'volume_ratio': latest['volume_ratio'] if pd.notna(latest['volume_ratio']) else 1,
                'kdj_k': latest['kdj_k'] if pd.notna(latest['kdj_k']) else 50,
                'kdj_d': latest['kdj_d'] if pd.notna(latest['kdj_d']) else 50,
                'kdj_j': latest['kdj_j'] if pd.notna(latest['kdj_j']) else 50,
                'atr': latest['atr'] if pd.notna(latest['atr']) else 0,
                'atr_percent': latest['atr_percent'] if pd.notna(latest['atr_percent']) else 0,
                'volatility': df['change_pct'].std() if len(df) > 1 else 0,
                'avg_volume': df['volume'].mean(),
                'price_std': df['close_price'].std()
            }

            return features
        except Exception as e:
            self.logger.error(f"Failed to extract features for {stock_code}: {e}")
            return None
    
    def train_model(self, training_data: List[Dict]) -> bool:
        """Train the recommendation model"""
        try:
            if len(training_data) < 100:  # Need sufficient training data
                self.logger.warning("Insufficient training data")
                return False
            
            df = pd.DataFrame(training_data)
            
            # Prepare features
            self.feature_columns = [col for col in df.columns if col not in ['stock_code', 'target', 'timestamp']]
            X = df[self.feature_columns]
            y = df['target']  # 0: sell, 1: hold, 2: buy
            
            # Handle missing values
            X = X.fillna(X.mean())
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=6,
                random_state=42
            )
            self.model.fit(X_scaled, y)
            
            # Initialize SHAP explainer
            self.explainer = shap.TreeExplainer(self.model)
            
            self.logger.info("Model training completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Model training failed: {e}")
            return False
    
    def predict_recommendation(self, stock_code: str) -> Optional[Dict]:
        """Generate recommendation for a stock"""
        try:
            if not self.model:
                self.logger.error("Model not trained")
                return None
            
            # Extract features
            features = self.extract_features(stock_code)
            if not features:
                return None
            
            # Prepare feature vector
            feature_vector = pd.DataFrame([features])
            feature_vector = feature_vector.reindex(columns=self.feature_columns, fill_value=0)
            feature_vector_scaled = self.scaler.transform(feature_vector)
            
            # Make prediction
            prediction_proba = self.model.predict_proba(feature_vector_scaled)[0]
            prediction = self.model.predict(feature_vector_scaled)[0]
            
            # Map prediction to action
            actions = ['sell', 'hold', 'buy']
            action = actions[prediction]
            confidence = float(np.max(prediction_proba))
            
            # Get SHAP explanation
            shap_values = self.explainer.shap_values(feature_vector_scaled)
            feature_importance = {}
            
            if len(shap_values.shape) == 3:  # Multi-class
                shap_vals = shap_values[prediction][0]
            else:
                shap_vals = shap_values[0]
            
            for i, feature in enumerate(self.feature_columns):
                feature_importance[feature] = float(shap_vals[i])
            
            # Get top contributing factors
            top_factors = sorted(feature_importance.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
            
            reasoning = self._generate_reasoning(action, confidence, top_factors)
            
            recommendation = {
                'stock_code': stock_code,
                'action': action,
                'confidence': confidence,
                'reasoning': reasoning,
                'factors': json.dumps(feature_importance),
                'timestamp': datetime.now()
            }
            
            # Save to database
            self._save_recommendation(recommendation)
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Prediction failed for {stock_code}: {e}")
            return None
    
    def _generate_reasoning(self, action: str, confidence: float, top_factors: List[Tuple[str, float]]) -> str:
        """Generate human-readable reasoning for recommendation"""
        reasoning_parts = [f"Recommendation: {action.upper()} (confidence: {confidence:.2f})"]
        
        if top_factors:
            reasoning_parts.append("Key factors:")
            for factor, importance in top_factors:
                direction = "positive" if importance > 0 else "negative"
                reasoning_parts.append(f"- {factor}: {direction} impact ({importance:.3f})")
        
        return " ".join(reasoning_parts)
    
    def _save_recommendation(self, recommendation: Dict):
        """Save recommendation to database"""
        try:
            rec = StockRecommendation(**recommendation)
            self.db_session.add(rec)
            self.db_session.commit()
        except Exception as e:
            self.logger.error(f"Failed to save recommendation: {e}")
            self.db_session.rollback()
    
    def get_latest_recommendation(self, stock_code: str) -> Optional[Dict]:
        """Get the latest recommendation for a stock"""
        try:
            rec = self.db_session.query(StockRecommendation).filter(
                StockRecommendation.stock_code == stock_code
            ).order_by(StockRecommendation.timestamp.desc()).first()
            
            if rec:
                return {
                    'stock_code': rec.stock_code,
                    'action': rec.action,
                    'confidence': rec.confidence,
                    'target_price': rec.target_price,
                    'reasoning': rec.reasoning,
                    'timestamp': rec.timestamp
                }
            return None
        except Exception as e:
            self.logger.error(f"Failed to get recommendation: {e}")
            return None
