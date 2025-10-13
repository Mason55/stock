# src/services/sentiment_provider.py - Sentiment data aggregation
import json
import logging
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

    def get_sentiment_analysis(self, stock_code: str) -> Optional[Dict[str, Any]]:
        stock_code = stock_code.upper()
        if stock_code in self.cache:
            return self.cache[stock_code]

        return self._request_api(stock_code)

sentiment_data_provider = SentimentDataProvider()
