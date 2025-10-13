# src/services/fundamental_provider.py - Fundamental data aggregation
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

import requests

from config.settings import settings

try:
    import yaml
except Exception:  # pragma: no cover - PyYAML optional
    yaml = None


class FundamentalDataProvider:
    """Load fundamental metrics from configurable sources."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_endpoint: Optional[str] = settings.FUNDAMENTAL_DATA_API
        self.local_path = Path(settings.FUNDAMENTAL_DATA_PATH) if settings.FUNDAMENTAL_DATA_PATH else None
        self.timeout = settings.FUNDAMENTAL_DATA_TIMEOUT
        self.cache: Dict[str, Dict[str, Any]] = {}

        if self.local_path:
            self._load_local_file(self.local_path)

    def _load_local_file(self, path: Path) -> None:
        if not path.exists():
            self.logger.warning("Fundamental data file not found: %s", path)
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
                self.logger.warning("Unexpected data format in %s", path)
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("Failed to load fundamental data file %s: %s", path, exc)

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
                    "Fundamental API returned %s for %s", response.status_code, stock_code
                )
                return None
            payload = response.json()
            normalized = self._normalize(payload, source="api")
            if normalized:
                self.cache[stock_code.upper()] = normalized
            return normalized
        except Exception as exc:
            self.logger.error("Fundamental API error for %s: %s", stock_code, exc)
            return None

    def _normalize(self, payload: Dict[str, Any], source: str) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None

        def _pick(keys, default=None):
            for key in keys:
                if key in payload:
                    return payload[key]
            return default

        valuation = {
            "pe_ratio": _pick(["pe", "pe_ratio", "price_earnings"], None),
            "pb_ratio": _pick(["pb", "pb_ratio", "price_book"], None),
        }
        profitability = {
            "roe": _pick(["roe", "return_on_equity"], None),
            "roa": _pick(["roa", "return_on_assets"], None),
            "gross_margin": _pick(["gross_margin"], None),
        }
        growth = {
            "revenue_growth": _pick(["revenue_growth", "yoy_revenue"], None),
            "net_income_growth": _pick(["net_income_growth"], None),
        }
        financial_health = {
            "debt_ratio": _pick(["debt_ratio", "debt_to_asset", "de_ratio"], None),
            "current_ratio": _pick(["current_ratio"], None),
        }

        if all(
            value is None
            for section in (valuation, profitability, growth, financial_health)
            for value in section.values()
        ):
            return None

        return {
            "valuation": valuation,
            "profitability": profitability,
            "growth": growth,
            "financial_health": financial_health,
            "source": source,
            "updated_at": payload.get("updated_at"),
        }

    def get_fundamental_analysis(self, stock_code: str) -> Optional[Dict[str, Any]]:
        stock_code = stock_code.upper()
        if stock_code in self.cache:
            return self.cache[stock_code]

        return self._request_api(stock_code)


fundamental_data_provider = FundamentalDataProvider()
