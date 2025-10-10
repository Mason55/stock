# src/monitoring/price_alert.py - Price alert and notification system
"""Price monitoring and alert system for stock trading."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Alert trigger types."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CHANGE_PCT = "price_change_pct"
    MA_CROSS = "ma_cross"
    RSI_OVERBOUGHT = "rsi_overbought"
    RSI_OVERSOLD = "rsi_oversold"
    VOLUME_SPIKE = "volume_spike"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class PriceAlert:
    """Price alert configuration."""
    alert_id: str
    symbol: str
    alert_type: AlertType
    threshold: float
    message: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    status: AlertStatus = AlertStatus.ACTIVE
    triggered_at: Optional[datetime] = None
    metadata: Dict = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'alert_id': self.alert_id,
            'symbol': self.symbol,
            'alert_type': self.alert_type.value,
            'threshold': self.threshold,
            'message': self.message,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'status': self.status.value,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'metadata': self.metadata or {}
        }


class AlertManager:
    """Manage price alerts and notifications."""

    def __init__(self):
        self.alerts: Dict[str, PriceAlert] = {}
        self.alert_history: List[PriceAlert] = []
        self.notification_callbacks: List[Callable] = []
        self._next_alert_id = 1

    def create_alert(
        self,
        symbol: str,
        alert_type: AlertType,
        threshold: float,
        message: str = None,
        expires_in_hours: int = 24
    ) -> str:
        """Create a new price alert.

        Args:
            symbol: Stock symbol
            alert_type: Type of alert
            threshold: Threshold value
            message: Custom alert message
            expires_in_hours: Hours until alert expires (default: 24)

        Returns:
            Alert ID
        """
        alert_id = f"alert_{self._next_alert_id}"
        self._next_alert_id += 1

        if message is None:
            message = self._generate_message(symbol, alert_type, threshold)

        expires_at = datetime.now() + timedelta(hours=expires_in_hours)

        alert = PriceAlert(
            alert_id=alert_id,
            symbol=symbol,
            alert_type=alert_type,
            threshold=threshold,
            message=message,
            created_at=datetime.now(),
            expires_at=expires_at,
            status=AlertStatus.ACTIVE
        )

        self.alerts[alert_id] = alert
        logger.info(f"Created alert {alert_id}: {symbol} {alert_type.value} {threshold}")

        return alert_id

    def create_price_target_alert(
        self,
        symbol: str,
        target_price: float,
        direction: str = "above"
    ) -> str:
        """Create a price target alert.

        Args:
            symbol: Stock symbol
            target_price: Target price
            direction: 'above' or 'below'

        Returns:
            Alert ID
        """
        alert_type = AlertType.PRICE_ABOVE if direction == "above" else AlertType.PRICE_BELOW
        message = f"{symbol} reached target price ¥{target_price:.2f}"

        return self.create_alert(symbol, alert_type, target_price, message)

    def create_support_resistance_alerts(
        self,
        symbol: str,
        support_levels: List[float],
        resistance_levels: List[float]
    ) -> List[str]:
        """Create alerts for support and resistance levels.

        Args:
            symbol: Stock symbol
            support_levels: List of support prices
            resistance_levels: List of resistance prices

        Returns:
            List of alert IDs
        """
        alert_ids = []

        # Create support alerts
        for level in support_levels:
            message = f"⚠️ {symbol} approaching support ¥{level:.2f}"
            alert_id = self.create_alert(
                symbol,
                AlertType.PRICE_BELOW,
                level,
                message
            )
            alert_ids.append(alert_id)

        # Create resistance alerts
        for level in resistance_levels:
            message = f"📈 {symbol} approaching resistance ¥{level:.2f}"
            alert_id = self.create_alert(
                symbol,
                AlertType.PRICE_ABOVE,
                level,
                message
            )
            alert_ids.append(alert_id)

        return alert_ids

    def create_technical_alerts(self, symbol: str, config: Dict = None) -> List[str]:
        """Create technical indicator alerts.

        Args:
            symbol: Stock symbol
            config: Configuration dict with thresholds

        Returns:
            List of alert IDs
        """
        config = config or {}
        alert_ids = []

        # RSI alerts
        rsi_oversold = config.get('rsi_oversold', 30)
        rsi_overbought = config.get('rsi_overbought', 70)

        alert_ids.append(self.create_alert(
            symbol,
            AlertType.RSI_OVERSOLD,
            rsi_oversold,
            f"💡 {symbol} RSI below {rsi_oversold} - Oversold signal"
        ))

        alert_ids.append(self.create_alert(
            symbol,
            AlertType.RSI_OVERBOUGHT,
            rsi_overbought,
            f"⚠️ {symbol} RSI above {rsi_overbought} - Overbought signal"
        ))

        # Price change alert
        price_change_pct = config.get('price_change_pct', 5.0)
        alert_ids.append(self.create_alert(
            symbol,
            AlertType.PRICE_CHANGE_PCT,
            price_change_pct,
            f"📊 {symbol} price changed more than {price_change_pct}%"
        ))

        return alert_ids

    def check_alert(self, alert: PriceAlert, current_data: Dict) -> bool:
        """Check if alert should be triggered.

        Args:
            alert: Alert to check
            current_data: Current market data

        Returns:
            True if alert triggered
        """
        if alert.status != AlertStatus.ACTIVE:
            return False

        if alert.expires_at and datetime.now() > alert.expires_at:
            alert.status = AlertStatus.EXPIRED
            return False

        current_price = current_data.get('current_price', 0)
        triggered = False

        if alert.alert_type == AlertType.PRICE_ABOVE:
            triggered = current_price >= alert.threshold

        elif alert.alert_type == AlertType.PRICE_BELOW:
            triggered = current_price <= alert.threshold

        elif alert.alert_type == AlertType.PRICE_CHANGE_PCT:
            prev_close = current_data.get('previous_close', current_price)
            if prev_close > 0:
                change_pct = abs((current_price - prev_close) / prev_close * 100)
                triggered = change_pct >= alert.threshold

        elif alert.alert_type == AlertType.RSI_OVERBOUGHT:
            rsi = current_data.get('rsi', 50)
            triggered = rsi >= alert.threshold

        elif alert.alert_type == AlertType.RSI_OVERSOLD:
            rsi = current_data.get('rsi', 50)
            triggered = rsi <= alert.threshold

        elif alert.alert_type == AlertType.VOLUME_SPIKE:
            volume = current_data.get('volume', 0)
            avg_volume = current_data.get('avg_volume', volume)
            if avg_volume > 0:
                volume_ratio = volume / avg_volume
                triggered = volume_ratio >= alert.threshold

        if triggered:
            alert.status = AlertStatus.TRIGGERED
            alert.triggered_at = datetime.now()
            self.alert_history.append(alert)
            self._send_notification(alert, current_data)
            logger.info(f"Alert triggered: {alert.alert_id} - {alert.message}")

        return triggered

    def check_all_alerts(self, market_data: Dict[str, Dict]) -> List[PriceAlert]:
        """Check all active alerts against current market data.

        Args:
            market_data: Dict of {symbol: data}

        Returns:
            List of triggered alerts
        """
        triggered_alerts = []

        for alert_id, alert in list(self.alerts.items()):
            if alert.symbol in market_data:
                data = market_data[alert.symbol]
                if self.check_alert(alert, data):
                    triggered_alerts.append(alert)
                    del self.alerts[alert_id]

        return triggered_alerts

    def cancel_alert(self, alert_id: str) -> bool:
        """Cancel an active alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if cancelled successfully
        """
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.CANCELLED
            self.alert_history.append(alert)
            del self.alerts[alert_id]
            logger.info(f"Cancelled alert: {alert_id}")
            return True
        return False

    def get_active_alerts(self, symbol: str = None) -> List[PriceAlert]:
        """Get active alerts, optionally filtered by symbol.

        Args:
            symbol: Stock symbol filter (optional)

        Returns:
            List of active alerts
        """
        alerts = list(self.alerts.values())
        if symbol:
            alerts = [a for a in alerts if a.symbol == symbol]
        return alerts

    def get_alert_history(
        self,
        symbol: str = None,
        hours: int = 24
    ) -> List[PriceAlert]:
        """Get alert history.

        Args:
            symbol: Stock symbol filter (optional)
            hours: Hours to look back

        Returns:
            List of historical alerts
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        history = [a for a in self.alert_history if a.triggered_at and a.triggered_at >= cutoff]

        if symbol:
            history = [a for a in history if a.symbol == symbol]

        return sorted(history, key=lambda a: a.triggered_at, reverse=True)

    def register_notification_callback(self, callback: Callable):
        """Register a notification callback function.

        Args:
            callback: Function that takes (alert, market_data)
        """
        self.notification_callbacks.append(callback)

    def _send_notification(self, alert: PriceAlert, market_data: Dict):
        """Send notification for triggered alert."""
        for callback in self.notification_callbacks:
            try:
                callback(alert, market_data)
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")

    def _generate_message(
        self,
        symbol: str,
        alert_type: AlertType,
        threshold: float
    ) -> str:
        """Generate default alert message."""
        messages = {
            AlertType.PRICE_ABOVE: f"{symbol} price above ¥{threshold:.2f}",
            AlertType.PRICE_BELOW: f"{symbol} price below ¥{threshold:.2f}",
            AlertType.PRICE_CHANGE_PCT: f"{symbol} price changed more than {threshold}%",
            AlertType.RSI_OVERBOUGHT: f"{symbol} RSI above {threshold}",
            AlertType.RSI_OVERSOLD: f"{symbol} RSI below {threshold}",
            AlertType.VOLUME_SPIKE: f"{symbol} volume spike {threshold}x average",
        }
        return messages.get(alert_type, f"{symbol} alert triggered")

    def export_alerts(self, filename: str = "alerts.json"):
        """Export alerts to JSON file."""
        data = {
            'active_alerts': [a.to_dict() for a in self.alerts.values()],
            'alert_history': [a.to_dict() for a in self.alert_history[-100:]]
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported alerts to {filename}")


# Example notification callbacks
def console_notification(alert: PriceAlert, market_data: Dict):
    """Print alert to console."""
    print(f"\n{'='*60}")
    print(f"🔔 ALERT TRIGGERED!")
    print(f"{'='*60}")
    print(f"Symbol: {alert.symbol}")
    print(f"Type: {alert.alert_type.value}")
    print(f"Message: {alert.message}")
    print(f"Current Price: ¥{market_data.get('current_price', 'N/A')}")
    print(f"Triggered At: {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


def log_notification(alert: PriceAlert, market_data: Dict):
    """Log alert to file."""
    logger.warning(
        f"ALERT: {alert.symbol} - {alert.message} "
        f"(Price: ¥{market_data.get('current_price', 'N/A')})"
    )
