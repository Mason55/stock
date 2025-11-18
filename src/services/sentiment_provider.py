# src/services/sentiment_provider.py - Sentiment data aggregation
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List

import requests

from config.settings import settings
from src.cache.persistent_cache import get_persistent_cache

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency guard
    yaml = None


class SentimentDataProvider:
    """Aggregate sentiment metrics from API or local files."""

    def __init__(self, use_persistent_cache: bool = True):
        self.logger = logging.getLogger(__name__)
        self.api_endpoint: Optional[str] = settings.SENTIMENT_DATA_API
        self.local_path = Path(settings.SENTIMENT_DATA_PATH) if settings.SENTIMENT_DATA_PATH else None
        self.timeout = settings.SENTIMENT_DATA_TIMEOUT

        # Use persistent cache instead of memory cache
        self.use_persistent_cache = use_persistent_cache
        if self.use_persistent_cache:
            self.cache_manager = get_persistent_cache()
        else:
            # Fallback to memory cache for backward compatibility
            self.cache: Dict[str, Dict[str, Any]] = {}
            self.cache_ttl: Dict[str, float] = {}

        # Rate limiting for crawler
        self.last_crawl_time: Dict[str, float] = {}  # stock_code -> timestamp
        self.crawl_interval = 5.0  # seconds between crawls for same stock
        self.global_last_crawl = 0.0  # global rate limit
        self.global_crawl_interval = 2.0  # seconds between any crawls

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

    def _should_rate_limit(self, stock_code: str) -> bool:
        """Check if we should rate limit this request"""
        current_time = time.time()

        # Check global rate limit (avoid hammering server)
        if current_time - self.global_last_crawl < self.global_crawl_interval:
            wait_time = self.global_crawl_interval - (current_time - self.global_last_crawl)
            self.logger.debug(f"Global rate limit, waiting {wait_time:.1f}s")
            time.sleep(wait_time)

        # Check per-stock rate limit
        last_crawl = self.last_crawl_time.get(stock_code, 0)
        if current_time - last_crawl < self.crawl_interval:
            self.logger.info(f"Rate limiting {stock_code}, too soon since last crawl")
            return True

        return False

    def _update_rate_limit(self, stock_code: str):
        """Update rate limit timestamps after successful crawl"""
        current_time = time.time()
        self.last_crawl_time[stock_code] = current_time
        self.global_last_crawl = current_time

    def _analyze_guba_sentiment(self, posts: List[Dict]) -> Dict[str, Any]:
        """Analyze sentiment from Guba post titles using keyword matching"""
        # Sentiment keyword dictionary
        positive_keywords = [
            '看多', '看好', '上涨', '涨停', '加仓', '买入', '抄底', '起飞', '牛',
            '突破', '反弹', '强势', '利好', '暴涨', '大涨', '机会', '底部', '金叉',
            '放量', '主力', '拉升', '新高', '爆发', '龙头', '翻倍', '暴力'
        ]

        negative_keywords = [
            '看空', '看跌', '下跌', '跌停', '减仓', '卖出', '割肉', '崩盘', '熊',
            '破位', '暴跌', '大跌', '利空', '阴跌', '套牢', '被套', '亏损', '死叉',
            '缩量', '出货', '砸盘', '跳水', '新低', '完了', '垃圾', '扶不起'
        ]

        neutral_keywords = [
            '观望', '震荡', '横盘', '整理', '等待', '持有', '不动', '犹豫',
            '不确定', '看不懂', '迷茫', '谨慎', '风险'
        ]

        # Analyze each post
        sentiment_scores = []
        keyword_counter = {}

        for post in posts:
            title = post['title']
            engagement = post.get('engagement', 1)

            # Calculate base sentiment for this post
            pos_count = sum(1 for kw in positive_keywords if kw in title)
            neg_count = sum(1 for kw in negative_keywords if kw in title)
            neu_count = sum(1 for kw in neutral_keywords if kw in title)

            # Sentiment score for this post (-1 to +1)
            if pos_count + neg_count + neu_count == 0:
                post_sentiment = 0.0  # Neutral if no keywords
            else:
                post_sentiment = (pos_count - neg_count) / (pos_count + neg_count + neu_count + 1)

            # Weight by engagement (popular posts matter more)
            weight = min(10, 1 + engagement / 100)
            sentiment_scores.append(post_sentiment * weight)

            # Track keywords
            for kw in positive_keywords:
                if kw in title:
                    keyword_counter[kw] = keyword_counter.get(kw, 0) + 1
            for kw in negative_keywords:
                if kw in title:
                    keyword_counter[kw] = keyword_counter.get(kw, 0) + 1
            for kw in neutral_keywords:
                if kw in title:
                    keyword_counter[kw] = keyword_counter.get(kw, 0) + 1

        # Calculate overall sentiment (normalize to 0-1)
        if sentiment_scores:
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            # Map from [-1, 1] to [0, 1]
            overall_score = (avg_sentiment + 1) / 2
        else:
            overall_score = 0.5

        # Determine sentiment level
        if overall_score >= 0.6:
            level = 'positive'
        elif overall_score <= 0.4:
            level = 'negative'
        else:
            level = 'neutral'

        # Top keywords
        top_keywords = sorted(keyword_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        keywords = [kw for kw, _ in top_keywords]

        return {
            'overall_score': round(overall_score, 2),
            'level': level,
            'keywords': keywords,
            'post_count': len(posts)
        }

    def _fetch_eastmoney_sentiment(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """Fetch sentiment data from EastMoney Guba (stock forum)"""
        try:
            from bs4 import BeautifulSoup

            # Check rate limit
            if self._should_rate_limit(stock_code):
                self.logger.info(f"Skipping Guba crawl for {stock_code} due to rate limit")
                return None

            # Convert stock code to Guba format (remove market suffix)
            code_num = stock_code.split('.')[0]
            url = f"https://guba.eastmoney.com/list,{code_num}.html"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://guba.eastmoney.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }

            # Fetch page with timeout
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code != 200:
                self.logger.warning(f"Guba returned status {response.status_code} for {stock_code}")
                return None

            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            # Parse post list
            posts = []
            post_items = soup.select('tr.listitem')

            for item in post_items[:30]:  # Top 30 posts
                try:
                    title_elem = item.select_one('div.title a')
                    read_elem = item.select_one('div.read')
                    reply_elem = item.select_one('div.reply')

                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        read_count = int(read_elem.get_text(strip=True)) if read_elem else 0
                        reply_count = int(reply_elem.get_text(strip=True)) if reply_elem else 0

                        posts.append({
                            'title': title,
                            'reads': read_count,
                            'replies': reply_count,
                            'engagement': read_count + reply_count * 10  # Weight replies higher
                        })
                except Exception as e:
                    self.logger.debug(f"Failed to parse post item: {e}")
                    continue

            if not posts:
                self.logger.warning(f"No posts extracted from Guba for {stock_code}")
                return None

            # Analyze sentiment from post titles
            sentiment_result = self._analyze_guba_sentiment(posts)

            # Update rate limit after successful crawl
            self._update_rate_limit(stock_code)

            result = {
                'overall_sentiment': sentiment_result['overall_score'],
                'sentiment_level': sentiment_result['level'],
                'news_sentiment': {
                    'score': None,
                    'article_count': None
                },
                'social_sentiment': {
                    'score': sentiment_result['overall_score'],
                    'mention_count': len(posts),
                    'total_engagement': sum(p['engagement'] for p in posts),
                    'keywords': sentiment_result['keywords']
                },
                'source': 'eastmoney_guba',
                'updated_at': datetime.utcnow().isoformat(),
                'post_count': len(posts)
            }

            self.logger.info(f"Successfully crawled Guba for {stock_code}: {len(posts)} posts, sentiment={sentiment_result['overall_score']}")
            return result

        except ImportError:
            self.logger.error("BeautifulSoup4 not installed. Run: pip install beautifulsoup4")
            return None
        except Exception as exc:
            self.logger.warning(f"EastMoney Guba fetch failed for {stock_code}: {exc}")
            return None

    def get_sentiment_analysis(self, stock_code: str) -> Optional[Dict[str, Any]]:
        stock_code = stock_code.upper()

        # Use persistent cache
        if self.use_persistent_cache:
            cache_key = f"sentiment:{stock_code}"
            cached_data = self.cache_manager.get(cache_key, max_age=3600)  # 1 hour
            if cached_data:
                self.logger.debug("Using persistent cached sentiment data for %s", stock_code)
                return cached_data

            # Try API first
            api_data = self._request_api(stock_code)
            if api_data:
                self.cache_manager.set(
                    cache_key,
                    api_data,
                    ttl=3600,
                    data_type="sentiment",
                    stock_code=stock_code
                )
                return api_data

            # Fallback to EastMoney Guba crawler
            self.logger.info("Attempting EastMoney Guba for %s", stock_code)
            guba_data = self._fetch_eastmoney_sentiment(stock_code)
            if guba_data:
                self.cache_manager.set(
                    cache_key,
                    guba_data,
                    ttl=3600,
                    data_type="sentiment",
                    stock_code=stock_code
                )
                return guba_data

            # Final fallback to technical-derived sentiment
            self.logger.info("Using technical-derived sentiment for %s", stock_code)
            simple_data = self._fetch_simple_sentiment(stock_code)
            if simple_data:
                self.cache_manager.set(
                    cache_key,
                    simple_data,
                    ttl=3600,
                    data_type="sentiment",
                    stock_code=stock_code
                )
                return simple_data

        else:
            # Fallback to memory cache
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

    def _is_cache_valid(self, stock_code: str, max_age_seconds: int = 3600) -> bool:
        """Check if memory cache entry is still valid (default: 1 hour for sentiment data)"""
        if not hasattr(self, 'cache_ttl') or stock_code not in self.cache_ttl:
            return False
        age = time.time() - self.cache_ttl[stock_code]
        return age < max_age_seconds

sentiment_data_provider = SentimentDataProvider()
