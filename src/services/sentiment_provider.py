# src/services/sentiment_provider.py - Sentiment data aggregation
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

import requests

from config.settings import settings

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency guard
    yaml = None


class SentimentDataProvider:
    """Aggregate sentiment metrics from API or local files."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_endpoint: Optional[str] = settings.SENTIMENT_DATA_API
        self.local_path = Path(settings.SENTIMENT_DATA_PATH) if settings.SENTIMENT_DATA_PATH else None
        self.timeout = settings.SENTIMENT_DATA_TIMEOUT
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl: Dict[str, float] = {}  # track cache timestamp

        if self.local_path:
            self._load_local_file(self.local_path)

    def _load_local_file(self, path: Path) -> None:
        if not path.exists():
            self.logger.warning("Sentiment data file not found: %s", path)
            return

        try:
            content = path.read_text(encoding="utf-8")
            if path.suffix.lower() in {".yaml", ".yml"} and yaml:
                raw = yaml.safe_load(content)
            else:
                raw = json.loads(content)

            if isinstance(raw, dict):
                for code, payload in raw.items():
                    normalized = self._normalize(payload, source="local")
                    if normalized:
                        self.cache[code.upper()] = normalized
            else:
                self.logger.warning("Unexpected sentiment data format in %s", path)
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("Failed to load sentiment data file %s: %s", path, exc)

    def _request_api(self, stock_code: str) -> Optional[Dict[str, Any]]:
        if not self.api_endpoint:
            return None

        url = (
            self.api_endpoint.format(stock_code=stock_code)
            if "{stock_code}" in self.api_endpoint
            else f"{self.api_endpoint.rstrip('/')}/{stock_code}"
        )

        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code != 200:
                self.logger.warning(
                    "Sentiment API returned %s for %s", response.status_code, stock_code
                )
                return None
            payload = response.json()
            normalized = self._normalize(payload, source="api")
            if normalized:
                self.cache[stock_code.upper()] = normalized
            return normalized
        except Exception as exc:
            self.logger.error("Sentiment API error for %s: %s", stock_code, exc)
            return None

    def _normalize(self, payload: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None

        overall = payload.get("overall_sentiment") or payload.get("score")
        news = payload.get("news", payload.get("news_sentiment", {}))
        social = payload.get("social", payload.get("social_sentiment", {}))

        if overall is None and not news and not social:
            return None

        overall_value = float(overall) if overall is not None else None
        level = payload.get("sentiment_level")
        if level is None and overall_value is not None:
            if overall_value >= 0.65:
                level = "positive"
            elif overall_value <= 0.35:
                level = "negative"
            else:
                level = "neutral"

        normalized_news = {
            "score": news.get("score") if isinstance(news, dict) else news,
            "article_count": news.get("article_count") if isinstance(news, dict) else None,
        }
        normalized_social = {
            "score": social.get("score") if isinstance(social, dict) else social,
            "mention_count": social.get("mention_count") if isinstance(social, dict) else None,
        }

        return {
            "overall_sentiment": overall_value,
            "sentiment_level": level,
            "news_sentiment": normalized_news,
            "social_sentiment": normalized_social,
            "source": source,
            "updated_at": payload.get("updated_at"),
        }

    def _fetch_simple_sentiment(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """Generate sentiment based on technical indicators (simplified approach)

        This is a fallback when external APIs are unavailable.
        It derives sentiment from price momentum and volume changes.
        """
        try:
            # Try to get recent price data from Sina
            from src.api.stock_api import fetch_sina_realtime_sync, fetch_history_df

            # Get realtime quote
            quote = fetch_sina_realtime_sync(stock_code)
            if not quote:
                return None

            current_price = quote.get('current_price')
            prev_close = quote.get('previous_close')
            volume = quote.get('volume', 0)

            if not current_price or not prev_close:
                return None

            # Calculate price change
            price_change_pct = (current_price - prev_close) / prev_close

            # Get short-term trend (5-day MA vs current price)
            hist = fetch_history_df(stock_code, days=10)
            ma5_strength = 0.0
            if hist is not None and not hist.empty and len(hist) >= 5:
                import pandas as pd
                closes = hist['close'].astype(float)
                ma5 = closes.rolling(5).mean().iloc[-1]
                if pd.notna(ma5) and ma5 > 0:
                    ma5_strength = (current_price - ma5) / ma5

            # Calculate sentiment score (0-1 scale)
            # Weight: 70% price momentum, 30% MA trend
            momentum_score = 0.5 + (price_change_pct * 5)  # ±10% change = ±0.5 score
            trend_score = 0.5 + (ma5_strength * 5)

            sentiment_score = 0.7 * momentum_score + 0.3 * trend_score
            sentiment_score = max(0.0, min(1.0, sentiment_score))

            # Determine sentiment level
            if sentiment_score >= 0.6:
                level = "positive"
            elif sentiment_score <= 0.4:
                level = "negative"
            else:
                level = "neutral"

            # Estimate activity based on volume
            volume_level = "high" if volume > 1000000 else "medium" if volume > 100000 else "low"

            return {
                "overall_sentiment": round(sentiment_score, 2),
                "sentiment_level": level,
                "news_sentiment": {
                    "score": None,
                    "article_count": None
                },
                "social_sentiment": {
                    "score": round(sentiment_score, 2),
                    "mention_count": None,
                    "activity_level": volume_level,
                    "derived_from": "price_momentum"
                },
                "source": "technical_derived",
                "updated_at": datetime.utcnow().isoformat(),
                "note": "Sentiment derived from technical indicators (fallback mode)"
            }

        except Exception as exc:
            self.logger.warning("Simple sentiment calculation failed for %s: %s", stock_code, exc)
            return None

    def _fetch_eastmoney_sentiment(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """Fetch sentiment data from EastMoney (currently disabled due to API restrictions)

        This method is a placeholder for future implementation when
        a stable EastMoney API endpoint is available.
        """
        self.logger.debug("EastMoney Guba API currently disabled, using fallback")
        return None

    def _is_cache_valid(self, stock_code: str, max_age_seconds: int = 3600) -> bool:
        """Check if cache entry is still valid (default: 1 hour for sentiment data)"""
        if stock_code not in self.cache_ttl:
            return False
        age = time.time() - self.cache_ttl[stock_code]
        return age < max_age_seconds

    def get_sentiment_analysis(self, stock_code: str) -> Optional[Dict[str, Any]]:
        stock_code = stock_code.upper()

        # Check cache with TTL validation
        if stock_code in self.cache and self._is_cache_valid(stock_code):
            self.logger.debug("Using cached sentiment data for %s", stock_code)
            return self.cache[stock_code]

        # Try API first
        api_data = self._request_api(stock_code)
        if api_data:
            self.cache[stock_code] = api_data
            self.cache_ttl[stock_code] = time.time()
            return api_data

        # Fallback to EastMoney Guba crawler
        self.logger.info("Attempting EastMoney Guba for %s", stock_code)
        guba_data = self._fetch_eastmoney_sentiment(stock_code)
        if guba_data:
            self.cache[stock_code] = guba_data
            self.cache_ttl[stock_code] = time.time()
            return guba_data

        # Final fallback to technical-derived sentiment
        self.logger.info("Using technical-derived sentiment for %s", stock_code)
        simple_data = self._fetch_simple_sentiment(stock_code)
        if simple_data:
            self.cache[stock_code] = simple_data
            self.cache_ttl[stock_code] = time.time()
            return simple_data

        self.logger.warning("No sentiment data available for %s", stock_code)
        return None

sentiment_data_provider = SentimentDataProvider()
