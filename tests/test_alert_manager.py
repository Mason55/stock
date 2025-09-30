# tests/test_alert_manager.py - Alert manager tests
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.monitoring.alert_manager import (
    AlertManager, Alert, AlertLevel, AlertChannel
)


class TestAlert:
    """Test Alert class."""

    def test_alert_creation(self):
        """Test alert creation."""
        alert = Alert(
            level=AlertLevel.WARNING,
            title='Test Alert',
            message='Test message',
            source='test',
            metadata={'key': 'value'}
        )

        assert alert.level == AlertLevel.WARNING
        assert alert.title == 'Test Alert'
        assert alert.message == 'Test message'
        assert alert.source == 'test'
        assert alert.metadata == {'key': 'value'}
        assert alert.timestamp is not None
        assert alert.alert_id.startswith('test_')

    def test_alert_to_dict(self):
        """Test alert conversion to dict."""
        alert = Alert(
            level=AlertLevel.ERROR,
            title='Test',
            message='Message',
            source='system'
        )

        alert_dict = alert.to_dict()

        assert alert_dict['level'] == 'error'
        assert alert_dict['title'] == 'Test'
        assert alert_dict['message'] == 'Message'
        assert alert_dict['source'] == 'system'
        assert 'timestamp' in alert_dict
        assert 'alert_id' in alert_dict


class TestAlertManager:
    """Test AlertManager functionality."""

    def test_initialization(self):
        """Test alert manager initialization."""
        manager = AlertManager(config={
            'channels': ['log', 'email'],
            'alert_cooldown': 300,
            'max_alerts_per_hour': 50
        })

        assert 'log' in manager.enabled_channels
        assert 'email' in manager.enabled_channels
        assert manager.alert_cooldown == 300
        assert manager.max_alerts_per_hour == 50

    def test_send_alert_log_channel(self):
        """Test sending alert to log."""
        manager = AlertManager(config={'channels': ['log']})

        success = manager.send_alert(
            level=AlertLevel.INFO,
            title='Test Alert',
            message='Test message',
            source='test'
        )

        assert success is True
        assert len(manager.alert_history) == 1
        assert manager.alert_history[0].title == 'Test Alert'

    def test_send_alert_multiple_levels(self):
        """Test sending alerts with different levels."""
        manager = AlertManager(config={
            'channels': ['log'],
            'alert_cooldown': 0  # Disable cooldown for test
        })

        for level in [AlertLevel.INFO, AlertLevel.WARNING, AlertLevel.ERROR, AlertLevel.CRITICAL]:
            manager.send_alert(
                level=level,
                title=f'{level.value} alert',
                message='Test',
                source='test'
            )

        assert len(manager.alert_history) == 4

    def test_rate_limiting(self):
        """Test alert rate limiting."""
        manager = AlertManager(config={
            'channels': ['log'],
            'max_alerts_per_hour': 3,
            'alert_cooldown': 0  # Disable cooldown to test rate limiting
        })

        # Send 3 alerts (should succeed)
        for i in range(3):
            success = manager.send_alert(
                level=AlertLevel.INFO,
                title=f'Alert {i}',
                message='Test',
                source='test_source'
            )
            assert success is True

        # 4th alert should be rate limited
        success = manager.send_alert(
            level=AlertLevel.INFO,
            title='Alert 4',
            message='Test',
            source='test_source'
        )
        assert success is False

    def test_cooldown_mechanism(self):
        """Test alert cooldown."""
        manager = AlertManager(config={
            'channels': ['log'],
            'alert_cooldown': 5  # 5 seconds
        })

        # First alert succeeds
        success1 = manager.send_alert(
            level=AlertLevel.INFO,
            title='Alert 1',
            message='Test',
            source='test_source'
        )
        assert success1 is True

        # Second alert immediately after should be blocked
        success2 = manager.send_alert(
            level=AlertLevel.INFO,
            title='Alert 2',
            message='Test',
            source='test_source'
        )
        assert success2 is False

        # Manually set last alert time to past
        manager.last_alert_time['test_source'] = datetime.now() - timedelta(seconds=10)

        # Now should succeed
        success3 = manager.send_alert(
            level=AlertLevel.INFO,
            title='Alert 3',
            message='Test',
            source='test_source'
        )
        assert success3 is True

    def test_different_sources_independent(self):
        """Test that different sources have independent limits."""
        manager = AlertManager(config={
            'channels': ['log'],
            'alert_cooldown': 60
        })

        # Alert from source1
        success1 = manager.send_alert(
            level=AlertLevel.INFO,
            title='Alert 1',
            message='Test',
            source='source1'
        )
        assert success1 is True

        # Alert from source2 should not be affected by source1's cooldown
        success2 = manager.send_alert(
            level=AlertLevel.INFO,
            title='Alert 2',
            message='Test',
            source='source2'
        )
        assert success2 is True

    @patch('smtplib.SMTP')
    def test_send_email_alert(self, mock_smtp):
        """Test sending email alert."""
        manager = AlertManager(config={
            'channels': ['email'],
            'smtp_host': 'smtp.test.com',
            'smtp_port': 587,
            'smtp_user': 'test@test.com',
            'smtp_password': 'password',
            'email_to': ['admin@test.com']
        })

        success = manager.send_alert(
            level=AlertLevel.CRITICAL,
            title='Critical Alert',
            message='System failure',
            source='system'
        )

        assert success is True
        mock_smtp.assert_called_once()

    @patch('requests.post')
    def test_send_webhook_alert(self, mock_post):
        """Test sending webhook alert."""
        mock_post.return_value.raise_for_status = Mock()

        manager = AlertManager(config={
            'channels': ['webhook'],
            'webhook_url': 'https://test.com/webhook'
        })

        success = manager.send_alert(
            level=AlertLevel.ERROR,
            title='Error Alert',
            message='Error occurred',
            source='app'
        )

        assert success is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert 'json' in call_kwargs

    @patch('requests.post')
    def test_send_dingtalk_alert(self, mock_post):
        """Test sending DingTalk alert."""
        mock_post.return_value.raise_for_status = Mock()

        manager = AlertManager(config={
            'channels': ['dingtalk'],
            'dingtalk_webhook': 'https://oapi.dingtalk.com/robot/send?access_token=xxx'
        })

        success = manager.send_alert(
            level=AlertLevel.WARNING,
            title='Warning',
            message='Warning message',
            source='monitor'
        )

        assert success is True
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_send_wechat_work_alert(self, mock_post):
        """Test sending WeChat Work alert."""
        mock_post.return_value.raise_for_status = Mock()

        manager = AlertManager(config={
            'channels': ['wechat_work'],
            'wechat_work_webhook': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx'
        })

        success = manager.send_alert(
            level=AlertLevel.INFO,
            title='Info',
            message='Info message',
            source='system'
        )

        assert success is True
        mock_post.assert_called_once()

    def test_custom_handler_registration(self):
        """Test custom handler registration."""
        manager = AlertManager()

        call_count = {'count': 0}

        def custom_handler(alert):
            call_count['count'] += 1

        manager.register_handler('custom', custom_handler)

        manager.send_alert(
            level=AlertLevel.INFO,
            title='Test',
            message='Test',
            source='test',
            channels=[AlertChannel.LOG]
        )

        assert call_count['count'] == 1

    def test_custom_handler_error_handling(self):
        """Test that custom handler errors don't break alert sending."""
        manager = AlertManager(config={'channels': ['log']})

        def failing_handler(alert):
            raise Exception("Handler failed")

        manager.register_handler('failing', failing_handler)

        # Should still succeed despite handler error
        success = manager.send_alert(
            level=AlertLevel.INFO,
            title='Test',
            message='Test',
            source='test'
        )

        assert success is True

    def test_get_alert_history(self):
        """Test getting alert history."""
        manager = AlertManager(config={
            'channels': ['log'],
            'alert_cooldown': 0  # Disable cooldown
        })

        # Send multiple alerts
        for i in range(5):
            manager.send_alert(
                level=AlertLevel.INFO,
                title=f'Alert {i}',
                message='Test',
                source='test'
            )

        history = manager.get_alert_history(hours=24)
        assert len(history) == 5

    def test_get_alert_history_by_source(self):
        """Test filtering alert history by source."""
        manager = AlertManager(config={
            'channels': ['log'],
            'alert_cooldown': 0  # Disable cooldown
        })

        manager.send_alert(AlertLevel.INFO, 'Test 1', 'Msg', 'source1')
        manager.send_alert(AlertLevel.INFO, 'Test 2', 'Msg', 'source2')
        manager.send_alert(AlertLevel.INFO, 'Test 3', 'Msg', 'source1')

        history = manager.get_alert_history(source='source1')
        assert len(history) == 2
        assert all(a.source == 'source1' for a in history)

    def test_get_alert_history_by_level(self):
        """Test filtering alert history by level."""
        manager = AlertManager(config={
            'channels': ['log'],
            'alert_cooldown': 0  # Disable cooldown
        })

        manager.send_alert(AlertLevel.INFO, 'Test 1', 'Msg', 'test')
        manager.send_alert(AlertLevel.ERROR, 'Test 2', 'Msg', 'test')
        manager.send_alert(AlertLevel.ERROR, 'Test 3', 'Msg', 'test')

        history = manager.get_alert_history(level=AlertLevel.ERROR)
        assert len(history) == 2
        assert all(a.level == AlertLevel.ERROR for a in history)

    def test_get_alert_history_time_window(self):
        """Test alert history time window."""
        manager = AlertManager(config={'channels': ['log']})

        # Add old alert manually
        old_alert = Alert(AlertLevel.INFO, 'Old', 'Msg', 'test')
        old_alert.timestamp = datetime.now() - timedelta(hours=48)
        manager.alert_history.append(old_alert)

        # Add recent alert
        manager.send_alert(AlertLevel.INFO, 'Recent', 'Msg', 'test')

        # Query last 24 hours
        history = manager.get_alert_history(hours=24)
        assert len(history) == 1
        assert history[0].title == 'Recent'

    def test_get_alert_summary(self):
        """Test alert summary statistics."""
        manager = AlertManager(config={
            'channels': ['log'],
            'alert_cooldown': 0  # Disable cooldown
        })

        manager.send_alert(AlertLevel.INFO, 'Test 1', 'Msg', 'source1')
        manager.send_alert(AlertLevel.WARNING, 'Test 2', 'Msg', 'source1')
        manager.send_alert(AlertLevel.ERROR, 'Test 3', 'Msg', 'source2')

        summary = manager.get_alert_summary()

        assert summary['total_alerts_24h'] == 3
        assert summary['by_level']['info'] == 1
        assert summary['by_level']['warning'] == 1
        assert summary['by_level']['error'] == 1
        assert summary['by_source']['source1'] == 2
        assert summary['by_source']['source2'] == 1
        assert summary['last_alert'] is not None

    def test_alert_history_trimming(self):
        """Test that old alerts are trimmed from history."""
        manager = AlertManager(config={'channels': ['log']})

        # Add old alert
        old_alert = Alert(AlertLevel.INFO, 'Old', 'Msg', 'test')
        old_alert.timestamp = datetime.now() - timedelta(days=2)
        manager.alert_history.append(old_alert)

        # Send new alert (triggers trimming)
        manager.send_alert(AlertLevel.INFO, 'New', 'Msg', 'test')

        # Old alert should be removed
        assert len(manager.alert_history) == 1
        assert manager.alert_history[0].title == 'New'

    def test_alert_with_metadata(self):
        """Test alert with metadata."""
        manager = AlertManager(config={'channels': ['log']})

        metadata = {
            'strategy': 'moving_average',
            'loss_pct': -2.5,
            'capital': 975000
        }

        manager.send_alert(
            level=AlertLevel.WARNING,
            title='Strategy Loss',
            message='Loss threshold exceeded',
            source='risk_monitor',
            metadata=metadata
        )

        alert = manager.alert_history[0]
        assert alert.metadata == metadata

    def test_specific_channel_override(self):
        """Test sending to specific channels."""
        manager = AlertManager(config={'channels': ['log', 'email']})

        # Send only to log
        manager.send_alert(
            level=AlertLevel.INFO,
            title='Test',
            message='Test',
            source='test',
            channels=[AlertChannel.LOG]
        )

        # Should still work
        assert len(manager.alert_history) == 1

    def test_alert_count_tracking(self):
        """Test alert count tracking per source."""
        manager = AlertManager(config={
            'channels': ['log'],
            'alert_cooldown': 0  # Disable cooldown
        })

        for i in range(5):
            manager.send_alert(
                level=AlertLevel.INFO,
                title=f'Alert {i}',
                message='Test',
                source='test_source'
            )

        assert manager.alert_counts['test_source'] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])