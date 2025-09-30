# src/monitoring/alert_manager.py - Alert and notification system
import logging
import smtplib
import requests
from enum import Enum
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert delivery channels."""
    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    DINGTALK = "dingtalk"
    WECHAT_WORK = "wechat_work"


class Alert:
    """Alert message."""

    def __init__(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str = "system",
        metadata: Dict = None
    ):
        self.level = level
        self.title = title
        self.message = message
        self.source = source
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
        self.alert_id = f"{source}_{int(self.timestamp.timestamp())}"

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'alert_id': self.alert_id,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'source': self.source,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class AlertManager:
    """Manage alerts and notifications.

    Features:
    - Multi-channel delivery (email/webhook/IM)
    - Alert deduplication
    - Rate limiting
    - Alert aggregation
    - Configurable routing rules
    """

    def __init__(self, config: Dict = None):
        config = config or {}

        # Configuration
        self.enabled_channels = set(config.get('channels', ['log']))
        self.alert_cooldown = config.get('alert_cooldown', 300)  # 5 min
        self.max_alerts_per_hour = config.get('max_alerts_per_hour', 50)

        # Email config
        self.smtp_host = config.get('smtp_host', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_user = config.get('smtp_user')
        self.smtp_password = config.get('smtp_password')
        self.email_from = config.get('email_from', self.smtp_user)
        self.email_to = config.get('email_to', [])

        # Webhook config
        self.webhook_url = config.get('webhook_url')
        self.dingtalk_webhook = config.get('dingtalk_webhook')
        self.wechat_work_webhook = config.get('wechat_work_webhook')

        # State
        self.alert_history: List[Alert] = []
        self.last_alert_time: Dict[str, datetime] = {}
        self.alert_counts: Dict[str, int] = defaultdict(int)

        # Custom handlers
        self.custom_handlers: Dict[str, Callable] = {}

        logger.info(
            f"Alert Manager initialized with channels: {self.enabled_channels}"
        )

    def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        source: str = "system",
        metadata: Dict = None,
        channels: List[AlertChannel] = None
    ) -> bool:
        """Send alert through configured channels.

        Args:
            level: Alert severity
            title: Alert title
            message: Alert message
            source: Alert source identifier
            metadata: Additional context
            channels: Specific channels (uses all enabled if None)

        Returns:
            True if sent successfully
        """
        alert = Alert(level, title, message, source, metadata)

        # Check rate limiting
        if not self._check_rate_limit(alert):
            logger.debug(f"Alert rate limited: {alert.alert_id}")
            return False

        # Check cooldown
        if not self._check_cooldown(alert):
            logger.debug(f"Alert in cooldown: {alert.alert_id}")
            return False

        # Store in history
        self.alert_history.append(alert)
        self._trim_history()

        # Update tracking
        self.last_alert_time[alert.source] = alert.timestamp
        self.alert_counts[alert.source] += 1

        # Determine channels
        if channels is None:
            channels = [AlertChannel(c) for c in self.enabled_channels]

        # Send through channels
        success = False
        for channel in channels:
            try:
                if channel == AlertChannel.LOG:
                    self._send_log(alert)
                    success = True
                elif channel == AlertChannel.EMAIL:
                    self._send_email(alert)
                    success = True
                elif channel == AlertChannel.WEBHOOK:
                    self._send_webhook(alert)
                    success = True
                elif channel == AlertChannel.DINGTALK:
                    self._send_dingtalk(alert)
                    success = True
                elif channel == AlertChannel.WECHAT_WORK:
                    self._send_wechat_work(alert)
                    success = True
            except Exception as e:
                logger.error(f"Failed to send alert via {channel.value}: {e}")

        # Custom handlers
        for handler in self.custom_handlers.values():
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Custom handler error: {e}")

        return success

    def _check_rate_limit(self, alert: Alert) -> bool:
        """Check if alert exceeds rate limit."""
        # Count alerts in last hour from this source
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_alerts = [
            a for a in self.alert_history
            if a.source == alert.source and a.timestamp > one_hour_ago
        ]

        return len(recent_alerts) < self.max_alerts_per_hour

    def _check_cooldown(self, alert: Alert) -> bool:
        """Check if alert is in cooldown period."""
        if alert.source not in self.last_alert_time:
            return True

        last_time = self.last_alert_time[alert.source]
        elapsed = (datetime.now() - last_time).total_seconds()

        return elapsed >= self.alert_cooldown

    def _trim_history(self):
        """Remove old alerts from history."""
        # Keep only last 24 hours
        cutoff = datetime.now() - timedelta(days=1)
        self.alert_history = [
            a for a in self.alert_history
            if a.timestamp > cutoff
        ]

    def _send_log(self, alert: Alert):
        """Send alert to log."""
        log_level = {
            AlertLevel.INFO: logging.INFO,
            AlertLevel.WARNING: logging.WARNING,
            AlertLevel.ERROR: logging.ERROR,
            AlertLevel.CRITICAL: logging.CRITICAL
        }.get(alert.level, logging.INFO)

        logger.log(
            log_level,
            f"[ALERT] {alert.title} | {alert.message} | Source: {alert.source}"
        )

    def _send_email(self, alert: Alert):
        """Send alert via email."""
        if not self.smtp_user or not self.email_to:
            logger.warning("Email not configured")
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = ', '.join(self.email_to)
            msg['Subject'] = f"[{alert.level.value.upper()}] {alert.title}"

            body = f"""
Alert Level: {alert.level.value}
Source: {alert.source}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Message:
{alert.message}

Metadata:
{alert.metadata}
"""
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email alert sent: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

    def _send_webhook(self, alert: Alert):
        """Send alert via webhook."""
        if not self.webhook_url:
            logger.warning("Webhook not configured")
            return

        try:
            payload = alert.to_dict()
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5
            )
            response.raise_for_status()

            logger.info(f"Webhook alert sent: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            raise

    def _send_dingtalk(self, alert: Alert):
        """Send alert via DingTalk (‰‰)."""
        if not self.dingtalk_webhook:
            logger.warning("DingTalk webhook not configured")
            return

        try:
            # DingTalk message format
            content = f"""
### {alert.title}

**§+**: {alert.level.value}
**e**: {alert.source}
**φτ**: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}
"""

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": alert.title,
                    "text": content
                }
            }

            response = requests.post(
                self.dingtalk_webhook,
                json=payload,
                timeout=5
            )
            response.raise_for_status()

            logger.info(f"DingTalk alert sent: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send DingTalk: {e}")
            raise

    def _send_wechat_work(self, alert: Alert):
        """Send alert via WeChat Work (®α)."""
        if not self.wechat_work_webhook:
            logger.warning("WeChat Work webhook not configured")
            return

        try:
            # WeChat Work message format
            content = f"""
<font color="warning">{alert.title}</font>
> §+: {alert.level.value}
> e: {alert.source}
> φτ: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

{alert.message}
"""

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }

            response = requests.post(
                self.wechat_work_webhook,
                json=payload,
                timeout=5
            )
            response.raise_for_status()

            logger.info(f"WeChat Work alert sent: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send WeChat Work: {e}")
            raise

    def register_handler(self, name: str, handler: Callable):
        """Register custom alert handler.

        Args:
            name: Handler identifier
            handler: Callable that takes Alert as argument
        """
        self.custom_handlers[name] = handler
        logger.info(f"Custom handler registered: {name}")

    def get_alert_history(
        self,
        source: str = None,
        level: AlertLevel = None,
        hours: int = 24
    ) -> List[Alert]:
        """Get alert history.

        Args:
            source: Filter by source
            level: Filter by level
            hours: Hours to look back

        Returns:
            List of alerts
        """
        cutoff = datetime.now() - timedelta(hours=hours)

        alerts = [a for a in self.alert_history if a.timestamp > cutoff]

        if source:
            alerts = [a for a in alerts if a.source == source]

        if level:
            alerts = [a for a in alerts if a.level == level]

        return alerts

    def get_alert_summary(self) -> Dict:
        """Get alert statistics."""
        if not self.alert_history:
            return {}

        cutoff = datetime.now() - timedelta(hours=24)
        recent_alerts = [a for a in self.alert_history if a.timestamp > cutoff]

        level_counts = defaultdict(int)
        source_counts = defaultdict(int)

        for alert in recent_alerts:
            level_counts[alert.level.value] += 1
            source_counts[alert.source] += 1

        return {
            'total_alerts_24h': len(recent_alerts),
            'by_level': dict(level_counts),
            'by_source': dict(source_counts),
            'last_alert': self.alert_history[-1].to_dict() if self.alert_history else None
        }