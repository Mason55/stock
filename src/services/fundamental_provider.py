# src/services/fundamental_provider.py - Fundamental data aggregation
import copy
import json
import logging
import re
import time
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
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
        self.cache_ttl: Dict[str, float] = {}  # track cache timestamp

        if self.local_path:
            self._load_local_file(self.local_path)

    def _normalize_numeric(self, value: Any, percent: bool = False) -> Optional[float]:
        """Convert raw string/numeric values to float. When percent=True, return decimal."""
        if value in (None, "", "--", "-"):
            return None
        try:
            normalized = float(str(value).replace(",", ""))
            if percent:
                return normalized / 100.0
            return normalized
        except Exception:
            return None

    def _select_reporting_period(self, columns: list[str]) -> Optional[str]:
        """Pick the latest column that looks like a report date (prefer annual)."""
        date_columns = [
            col
            for col in columns
            if isinstance(col, str) and re.match(r"^20\d{2}-\d{2}-\d{2}$", col)
        ]
        if not date_columns:
            return None
        # Prefer full-year reports ending with 12-31, fallback to most recent column
        for col in sorted(date_columns, reverse=True):
            if col.endswith("12-31"):
                return col
        return sorted(date_columns, reverse=True)[0]

    def _fetch_financial_table(self, stock_code: str) -> Optional[pd.DataFrame]:
        """Download and parse Sina financial guideline table for the stock."""
        symbol = stock_code.split(".")[0]
        current_year = datetime.now().year
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Referer": "https://finance.sina.com.cn",
        }
        for year in range(current_year, current_year - 6, -1):
            url = (
                "https://money.finance.sina.com.cn/corp/go.php/vFD_FinancialGuideLine/"
                f"stockid/{symbol}/ctrl/{year}/displaytype/4.phtml"
            )
            try:
                resp = requests.get(url, headers=headers, timeout=self.timeout)
                if resp.status_code != 200:
                    continue
                tables = pd.read_html(StringIO(resp.text))
                if len(tables) <= 12:
                    continue
                table = tables[12].iloc[:, :-1]  # drop trailing notes column
                table.columns = table.iloc[0]
                table = table.iloc[1:].copy()
                first_col = table.columns[0]
                table.rename(columns={first_col: "指标"}, inplace=True)
                period = self._select_reporting_period(list(table.columns)[1:])
                if period:
                    table.attrs["selected_period"] = period
                    return table.reset_index(drop=True)
            except Exception as exc:
                self.logger.debug(
                    "Failed to fetch Sina financial table for %s (%s): %s",
                    stock_code,
                    year,
                    exc,
                )
        return None

    def _extract_financial_metrics(
        self, table: pd.DataFrame, price_hint: Optional[float]
    ) -> Optional[Dict[str, Any]]:
        """Transform Sina table into normalized financial metrics."""
        period = table.attrs.get("selected_period")
        if not period:
            return None

        indicator_sections = {
            "每股指标",
            "盈利能力",
            "成长能力",
            "偿债及资本结构",
            "现金流量",
        }
        effective_rows: Dict[str, Dict[str, Any]] = {}
        current_section = None
        for _, row in table.iterrows():
            indicator = row.get("指标")
            if isinstance(indicator, str) and indicator in indicator_sections:
                current_section = indicator
                continue
            if current_section is None or not isinstance(indicator, str):
                continue
            effective_rows[indicator] = row

        series = {
            key: effective_rows[key].get(period)
            for key in effective_rows
            if period in effective_rows[key]
        }

        eps = self._normalize_numeric(series.get("摊薄每股收益(元)"))
        book_value = self._normalize_numeric(series.get("每股净资产_调整后(元)")) or self._normalize_numeric(
            series.get("调整后的每股净资产(元)")
        )
        roe = self._normalize_numeric(series.get("净资产收益率(%)"), percent=True)
        net_margin = self._normalize_numeric(series.get("销售净利率(%)"), percent=True)
        gross_margin = self._normalize_numeric(series.get("销售毛利率(%)"), percent=True)
        revenue_growth = self._normalize_numeric(series.get("主营业务收入增长率(%)"), percent=True)
        net_income_growth = self._normalize_numeric(series.get("净利润增长率(%)"), percent=True)
        debt_ratio = self._normalize_numeric(series.get("资产负债率(%)"), percent=True)
        current_ratio = self._normalize_numeric(series.get("流动比率"))
        quick_ratio = self._normalize_numeric(series.get("速动比率"))
        operating_cash = self._normalize_numeric(
            series.get("经营现金净流量对销售收入比率(%)"), percent=True
        )

        valuation = {
            "pe_ratio": None,
            "pb_ratio": None,
            "eps": eps,
            "book_value_per_share": book_value,
            "report_period": period,
        }
        if price_hint and eps not in (None, 0):
            valuation["pe_ratio"] = round(price_hint / eps, 2)
        if price_hint and book_value not in (None, 0):
            valuation["pb_ratio"] = round(price_hint / book_value, 2)

        return {
            "valuation": valuation,
            "profitability": {
                "roe": roe,
                "net_margin": net_margin,
                "gross_margin": gross_margin,
            },
            "growth": {
                "revenue_growth": revenue_growth,
                "net_income_growth": net_income_growth,
            },
            "financial_health": {
                "debt_ratio": debt_ratio,
                "current_ratio": current_ratio,
                "quick_ratio": quick_ratio,
                "operating_cash_flow_ratio": operating_cash,
            },
            "source": "sina_financial",
            "updated_at": datetime.utcnow().isoformat(),
        }

    def _fetch_sina_financials(
        self, stock_code: str, price_hint: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch and normalize fundamentals from Sina when no API/local data."""
        try:
            table = self._fetch_financial_table(stock_code)
            if table is None:
                return None
            return self._extract_financial_metrics(table, price_hint)
        except Exception as exc:
            self.logger.warning(
                "Sina financial fetch failed for %s: %s", stock_code, exc
            )
            return None

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

    def _is_cache_valid(self, stock_code: str, max_age_seconds: int = 86400) -> bool:
        """Check if cache entry is still valid (default: 24 hours)"""
        if stock_code not in self.cache_ttl:
            return False
        age = time.time() - self.cache_ttl[stock_code]
        return age < max_age_seconds

    def get_fundamental_analysis(
        self, stock_code: str, price_hint: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        stock_code = stock_code.upper()

        # Check cache with TTL validation
        if stock_code in self.cache and self._is_cache_valid(stock_code):
            self.logger.debug("Using cached fundamental data for %s", stock_code)
            return copy.deepcopy(self.cache[stock_code])

        # Try API first
        api_data = self._request_api(stock_code)
        if api_data:
            self.cache[stock_code] = api_data
            self.cache_ttl[stock_code] = time.time()
            return copy.deepcopy(api_data)

        # Fallback to Sina financial crawler
        self.logger.info("Falling back to Sina financials for %s", stock_code)
        sina_data = self._fetch_sina_financials(stock_code, price_hint=price_hint)
        if sina_data:
            self.cache[stock_code] = sina_data
            self.cache_ttl[stock_code] = time.time()
            return copy.deepcopy(sina_data)

        self.logger.warning("No fundamental data available for %s", stock_code)
        return None


fundamental_data_provider = FundamentalDataProvider()
