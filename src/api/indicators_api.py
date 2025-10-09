# src/api/indicators_api.py - Enhanced technical indicators API with interpretations
import logging
from datetime import date, timedelta
from typing import Optional

from flask import Blueprint, g, jsonify, request
from sqlalchemy.orm import Session

from src.database import get_db_session
from src.middleware.validator import require_stock_code
from src.models.indicators import TechnicalIndicators
from src.services.indicators_calculator import IndicatorsCalculator
from src.utils.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

indicators_bp = Blueprint("indicators", __name__, url_prefix="/api/indicators")


def get_current_session() -> Optional[Session]:
    """Get database session for current request"""
    if not hasattr(g, "db_session"):
        g.db_session = next(get_db_session(), None)
    return g.db_session


def interpret_ma(indicators: dict) -> list:
    """Interpret Moving Average signals"""
    interpretations = []

    ma_5 = indicators.get("ma_5")
    ma_20 = indicators.get("ma_20")
    ma_60 = indicators.get("ma_60")
    close = indicators.get("close_price")

    if ma_5 and ma_20 and close:
        if ma_5 > ma_20:
            trend = "uptrend"
            if close > ma_5:
                interpretations.append(
                    {
                        "indicator": "MA",
                        "signal": "BULLISH",
                        "strength": 0.8,
                        "description": f"Short-term uptrend confirmed. Price ({close:.2f}) above MA5 ({ma_5:.2f}) and MA5 above MA20 ({ma_20:.2f})",
                    }
                )
            else:
                interpretations.append(
                    {
                        "indicator": "MA",
                        "signal": "NEUTRAL",
                        "strength": 0.5,
                        "description": f"MA5 ({ma_5:.2f}) > MA20 ({ma_20:.2f}), but price pulled back below MA5",
                    }
                )
        else:
            if close < ma_5:
                interpretations.append(
                    {
                        "indicator": "MA",
                        "signal": "BEARISH",
                        "strength": 0.8,
                        "description": f"Downtrend confirmed. Price ({close:.2f}) below MA5 ({ma_5:.2f}) and MA5 below MA20 ({ma_20:.2f})",
                    }
                )

    return interpretations


def interpret_macd(indicators: dict) -> list:
    """Interpret MACD signals"""
    interpretations = []

    dif = indicators.get("macd_dif")
    dea = indicators.get("macd_dea")
    hist = indicators.get("macd_histogram")

    if dif and dea and hist:
        if dif > dea and hist > 0:
            strength = min(abs(hist) * 10, 0.9)  # Scale histogram to strength
            interpretations.append(
                {
                    "indicator": "MACD",
                    "signal": "BULLISH",
                    "strength": strength,
                    "description": f"MACD golden cross. DIF ({dif:.4f}) > DEA ({dea:.4f}), histogram positive ({hist:.4f})",
                }
            )
        elif dif < dea and hist < 0:
            strength = min(abs(hist) * 10, 0.9)
            interpretations.append(
                {
                    "indicator": "MACD",
                    "signal": "BEARISH",
                    "strength": strength,
                    "description": f"MACD death cross. DIF ({dif:.4f}) < DEA ({dea:.4f}), histogram negative ({hist:.4f})",
                }
            )

    return interpretations


def interpret_rsi(indicators: dict) -> list:
    """Interpret RSI signals"""
    interpretations = []

    rsi_12 = indicators.get("rsi_12")

    if rsi_12:
        if rsi_12 < 30:
            interpretations.append(
                {
                    "indicator": "RSI",
                    "signal": "BULLISH",
                    "strength": 0.7,
                    "description": f"RSI oversold zone ({rsi_12:.2f}). Potential bounce opportunity",
                }
            )
        elif rsi_12 > 70:
            interpretations.append(
                {
                    "indicator": "RSI",
                    "signal": "BEARISH",
                    "strength": 0.7,
                    "description": f"RSI overbought zone ({rsi_12:.2f}). Potential pullback risk",
                }
            )
        elif 40 <= rsi_12 <= 60:
            interpretations.append(
                {
                    "indicator": "RSI",
                    "signal": "NEUTRAL",
                    "strength": 0.5,
                    "description": f"RSI in neutral zone ({rsi_12:.2f}). No clear directional bias",
                }
            )

    return interpretations


def interpret_bollinger(indicators: dict) -> list:
    """Interpret Bollinger Bands signals"""
    interpretations = []

    upper = indicators.get("boll_upper")
    middle = indicators.get("boll_middle")
    lower = indicators.get("boll_lower")
    width = indicators.get("boll_width")
    close = indicators.get("close_price")

    if all([upper, middle, lower, close, width]):
        position = (close - lower) / (upper - lower) if (upper - lower) > 0 else 0.5

        if close < lower:
            interpretations.append(
                {
                    "indicator": "BOLL",
                    "signal": "BULLISH",
                    "strength": 0.8,
                    "description": f"Price ({close:.2f}) below lower band ({lower:.2f}). Oversold, mean reversion expected. Band width: {width:.4f}",
                }
            )
        elif close > upper:
            interpretations.append(
                {
                    "indicator": "BOLL",
                    "signal": "BEARISH",
                    "strength": 0.8,
                    "description": f"Price ({close:.2f}) above upper band ({upper:.2f}). Overbought, pullback risk. Band width: {width:.4f}",
                }
            )
        elif width < 0.05:
            interpretations.append(
                {
                    "indicator": "BOLL",
                    "signal": "NEUTRAL",
                    "strength": 0.6,
                    "description": f"Bollinger squeeze detected (width: {width:.4f}). Expect volatility breakout soon",
                }
            )

    return interpretations


def interpret_kdj(indicators: dict) -> list:
    """Interpret KDJ signals"""
    interpretations = []

    k = indicators.get("kdj_k")
    d = indicators.get("kdj_d")
    j = indicators.get("kdj_j")

    if all([k, d, j]):
        if k < 20 and d < 20:
            interpretations.append(
                {
                    "indicator": "KDJ",
                    "signal": "BULLISH",
                    "strength": 0.75,
                    "description": f"KDJ oversold (K:{k:.2f}, D:{d:.2f}, J:{j:.2f}). Strong buy signal",
                }
            )
        elif k > 80 and d > 80:
            interpretations.append(
                {
                    "indicator": "KDJ",
                    "signal": "BEARISH",
                    "strength": 0.75,
                    "description": f"KDJ overbought (K:{k:.2f}, D:{d:.2f}, J:{j:.2f}). Strong sell signal",
                }
            )
        elif k > d and j > k:
            interpretations.append(
                {
                    "indicator": "KDJ",
                    "signal": "BULLISH",
                    "strength": 0.6,
                    "description": f"KDJ golden cross. K ({k:.2f}) > D ({d:.2f}), J ({j:.2f}) accelerating upward",
                }
            )
        elif k < d and j < k:
            interpretations.append(
                {
                    "indicator": "KDJ",
                    "signal": "BEARISH",
                    "strength": 0.6,
                    "description": f"KDJ death cross. K ({k:.2f}) < D ({d:.2f}), J ({j:.2f}) accelerating downward",
                }
            )

    return interpretations


def interpret_atr(indicators: dict) -> list:
    """Interpret ATR (volatility) signals"""
    interpretations = []

    atr = indicators.get("atr_14")
    atr_pct = indicators.get("atr_normalized")

    if atr and atr_pct:
        if atr_pct > 3.0:
            interpretations.append(
                {
                    "indicator": "ATR",
                    "signal": "HIGH_VOLATILITY",
                    "strength": 0.7,
                    "description": f"High volatility detected. ATR: {atr:.4f} ({atr_pct:.2f}% of price). Wider stops recommended",
                }
            )
        elif atr_pct < 1.0:
            interpretations.append(
                {
                    "indicator": "ATR",
                    "signal": "LOW_VOLATILITY",
                    "strength": 0.6,
                    "description": f"Low volatility. ATR: {atr:.4f} ({atr_pct:.2f}% of price). Expect consolidation or breakout",
                }
            )
        else:
            interpretations.append(
                {
                    "indicator": "ATR",
                    "signal": "NORMAL_VOLATILITY",
                    "strength": 0.5,
                    "description": f"Normal volatility. ATR: {atr:.4f} ({atr_pct:.2f}% of price)",
                }
            )

    return interpretations


@indicators_bp.route("/<stock_code>", methods=["GET"])
@require_stock_code
def get_indicators(stock_code: str):
    """Get technical indicators with interpretations

    Query params:
    - date: specific date (YYYY-MM-DD), default to latest
    """
    try:
        db = get_current_session()
        if not db:
            return jsonify({"error": "Database unavailable"}), 503

        # Get date parameter
        date_str = request.args.get("date")
        if date_str:
            target_date = date.fromisoformat(date_str)
        else:
            target_date = date.today()

        # Query indicators from database
        indicator = (
            db.query(TechnicalIndicators)
            .filter(
                TechnicalIndicators.symbol == stock_code,
                TechnicalIndicators.calc_date <= target_date,
            )
            .order_by(TechnicalIndicators.calc_date.desc())
            .first()
        )

        if not indicator:
            raise ResourceNotFoundError(f"No indicators found for {stock_code}")

        # Convert to dict
        indicators_dict = {
            "symbol": indicator.symbol,
            "calc_date": indicator.calc_date.isoformat(),
            "ma_5": float(indicator.ma_5) if indicator.ma_5 else None,
            "ma_10": float(indicator.ma_10) if indicator.ma_10 else None,
            "ma_20": float(indicator.ma_20) if indicator.ma_20 else None,
            "ma_60": float(indicator.ma_60) if indicator.ma_60 else None,
            "macd_dif": float(indicator.macd_dif) if indicator.macd_dif else None,
            "macd_dea": float(indicator.macd_dea) if indicator.macd_dea else None,
            "macd_histogram": float(indicator.macd_histogram) if indicator.macd_histogram else None,
            "rsi_6": float(indicator.rsi_6) if indicator.rsi_6 else None,
            "rsi_12": float(indicator.rsi_12) if indicator.rsi_12 else None,
            "rsi_24": float(indicator.rsi_24) if indicator.rsi_24 else None,
            "boll_upper": float(indicator.boll_upper) if indicator.boll_upper else None,
            "boll_middle": float(indicator.boll_middle) if indicator.boll_middle else None,
            "boll_lower": float(indicator.boll_lower) if indicator.boll_lower else None,
            "boll_width": float(indicator.boll_width) if indicator.boll_width else None,
            "kdj_k": float(indicator.kdj_k) if indicator.kdj_k else None,
            "kdj_d": float(indicator.kdj_d) if indicator.kdj_d else None,
            "kdj_j": float(indicator.kdj_j) if indicator.kdj_j else None,
            "atr_14": float(indicator.atr_14) if indicator.atr_14 else None,
            "atr_normalized": float(indicator.atr_normalized) if indicator.atr_normalized else None,
            "volume_ratio": float(indicator.volume_ratio) if indicator.volume_ratio else None,
        }

        # Generate interpretations
        interpretations = []
        interpretations.extend(interpret_ma(indicators_dict))
        interpretations.extend(interpret_macd(indicators_dict))
        interpretations.extend(interpret_rsi(indicators_dict))
        interpretations.extend(interpret_bollinger(indicators_dict))
        interpretations.extend(interpret_kdj(indicators_dict))
        interpretations.extend(interpret_atr(indicators_dict))

        # Calculate overall signal
        bullish = sum(1 for i in interpretations if i["signal"] == "BULLISH")
        bearish = sum(1 for i in interpretations if i["signal"] == "BEARISH")
        total = bullish + bearish

        if total > 0:
            if bullish > bearish:
                overall_signal = "BUY"
                overall_strength = bullish / total
            else:
                overall_signal = "SELL"
                overall_strength = bearish / total
        else:
            overall_signal = "HOLD"
            overall_strength = 0.5

        return jsonify(
            {
                "stock_code": stock_code,
                "indicators": indicators_dict,
                "interpretations": interpretations,
                "overall": {
                    "signal": overall_signal,
                    "strength": round(overall_strength, 2),
                    "bullish_signals": bullish,
                    "bearish_signals": bearish,
                },
            }
        )

    except ResourceNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to get indicators for {stock_code}: {e}")
        return jsonify({"error": "Internal server error"}), 500


@indicators_bp.route("/<stock_code>/history", methods=["GET"])
@require_stock_code
def get_indicators_history(stock_code: str):
    """Get historical indicators

    Query params:
    - days: number of days to retrieve (default 30)
    """
    try:
        db = get_current_session()
        if not db:
            return jsonify({"error": "Database unavailable"}), 503

        days = int(request.args.get("days", 30))
        start_date = date.today() - timedelta(days=days)

        indicators = (
            db.query(TechnicalIndicators)
            .filter(
                TechnicalIndicators.symbol == stock_code,
                TechnicalIndicators.calc_date >= start_date,
            )
            .order_by(TechnicalIndicators.calc_date)
            .all()
        )

        if not indicators:
            raise ResourceNotFoundError(f"No indicators history found for {stock_code}")

        result = []
        for ind in indicators:
            result.append(
                {
                    "date": ind.calc_date.isoformat(),
                    "ma_5": float(ind.ma_5) if ind.ma_5 else None,
                    "ma_20": float(ind.ma_20) if ind.ma_20 else None,
                    "rsi_12": float(ind.rsi_12) if ind.rsi_12 else None,
                    "macd_histogram": float(ind.macd_histogram) if ind.macd_histogram else None,
                    "kdj_k": float(ind.kdj_k) if ind.kdj_k else None,
                    "kdj_d": float(ind.kdj_d) if ind.kdj_d else None,
                }
            )

        return jsonify({"stock_code": stock_code, "history": result, "count": len(result)})

    except ResourceNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Failed to get indicators history for {stock_code}: {e}")
        return jsonify({"error": "Internal server error"}), 500