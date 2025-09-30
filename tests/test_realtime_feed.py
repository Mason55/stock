# tests/test_realtime_feed.py - Realtime feed tests
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from src.data_sources.realtime_feed import SinaRealtimeFeed


class TestSinaRealtimeFeed:
    """Test SinaRealtimeFeed functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test feed initialization."""
        feed = SinaRealtimeFeed(config={
            'update_interval': 2.0,
            'max_retries': 3
        })

        assert feed.update_interval == 2.0
        assert feed.max_retries == 3
        assert feed.is_connected is False
        assert feed.is_running is False
        assert len(feed.subscribed_symbols) == 0

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connection establishment."""
        feed = SinaRealtimeFeed()

        await feed.connect()

        assert feed.is_connected is True
        assert feed.is_running is True
        assert feed._update_task is not None
        assert feed._heartbeat_task is not None

        await feed.disconnect()

    @pytest.mark.asyncio
    async def test_subscribe(self):
        """Test symbol subscription."""
        feed = SinaRealtimeFeed()
        await feed.connect()

        symbols = ['000001.SZ', '600000.SH']
        await feed.subscribe(symbols)

        assert '000001.SZ' in feed.subscribed_symbols
        assert '600000.SH' in feed.subscribed_symbols
        assert len(feed.subscribed_symbols) == 2

        await feed.disconnect()

    @pytest.mark.asyncio
    async def test_subscribe_duplicate(self):
        """Test subscribing to already subscribed symbols."""
        feed = SinaRealtimeFeed()
        await feed.connect()

        await feed.subscribe(['000001.SZ'])
        await feed.subscribe(['000001.SZ', '600000.SH'])

        # Should have 2 unique symbols
        assert len(feed.subscribed_symbols) == 2

        await feed.disconnect()

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Test symbol unsubscription."""
        feed = SinaRealtimeFeed()
        await feed.connect()

        await feed.subscribe(['000001.SZ', '600000.SH', '000002.SZ'])
        await feed.unsubscribe(['600000.SH'])

        assert '000001.SZ' in feed.subscribed_symbols
        assert '600000.SH' not in feed.subscribed_symbols
        assert '000002.SZ' in feed.subscribed_symbols

        await feed.disconnect()

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_cache(self):
        """Test that unsubscribe removes cached data."""
        feed = SinaRealtimeFeed()
        await feed.connect()

        await feed.subscribe(['000001.SZ'])
        feed.latest_data['000001.SZ'] = {'price': 10.0}

        await feed.unsubscribe(['000001.SZ'])

        assert '000001.SZ' not in feed.latest_data

        await feed.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection."""
        feed = SinaRealtimeFeed()
        await feed.connect()

        await feed.disconnect()

        assert feed.is_connected is False
        assert feed.is_running is False

    @pytest.mark.asyncio
    async def test_register_callback(self):
        """Test callback registration."""
        feed = SinaRealtimeFeed()

        callback_called = {'count': 0}

        async def test_callback(symbol, data):
            callback_called['count'] += 1

        feed.register_callback(test_callback)

        assert len(feed.callbacks) == 1

    @pytest.mark.asyncio
    async def test_callback_invocation(self):
        """Test that callbacks are invoked on data update."""
        feed = SinaRealtimeFeed(config={'update_interval': 0.1})

        callback_data = {'symbol': None, 'data': None}

        async def test_callback(symbol, data):
            callback_data['symbol'] = symbol
            callback_data['data'] = data

        feed.register_callback(test_callback)

        # Mock Sina API
        with patch('src.data_sources.sina_finance.SinaFinanceDataSource') as mock_api_class:
            mock_api = Mock()
            mock_api.get_realtime_quote.return_value = {
                'current_price': 10.50,
                'change_pct': 0.02,
                'volume': 1000000
            }
            mock_api_class.return_value = mock_api

            await feed.connect()
            await feed.subscribe(['000001.SZ'])

            # Wait for update
            await asyncio.sleep(0.3)

            await feed.disconnect()

            # Callback should have been called
            assert callback_data['symbol'] == '000001.SZ'
            assert callback_data['data'] is not None

    @pytest.mark.asyncio
    async def test_sync_callback(self):
        """Test synchronous callback support."""
        feed = SinaRealtimeFeed(config={'update_interval': 0.1})

        callback_called = {'count': 0}

        def sync_callback(symbol, data):
            callback_called['count'] += 1

        feed.register_callback(sync_callback)

        with patch('src.data_sources.sina_finance.SinaFinanceDataSource') as mock_api_class:
            mock_api = Mock()
            mock_api.get_realtime_quote.return_value = {'current_price': 10.0}
            mock_api_class.return_value = mock_api

            await feed.connect()
            await feed.subscribe(['000001.SZ'])
            await asyncio.sleep(0.3)
            await feed.disconnect()

            assert callback_called['count'] > 0

    @pytest.mark.asyncio
    async def test_get_latest(self):
        """Test getting latest data for symbol."""
        feed = SinaRealtimeFeed()

        feed.latest_data['000001.SZ'] = {
            'symbol': '000001.SZ',
            'price': 10.50,
            'volume': 1000000
        }

        data = feed.get_latest('000001.SZ')

        assert data is not None
        assert data['price'] == 10.50
        assert data['volume'] == 1000000

    @pytest.mark.asyncio
    async def test_get_latest_missing_symbol(self):
        """Test getting latest data for non-existent symbol."""
        feed = SinaRealtimeFeed()

        data = feed.get_latest('NONEXISTENT')

        assert data is None

    @pytest.mark.asyncio
    async def test_get_all_latest(self):
        """Test getting all latest data."""
        feed = SinaRealtimeFeed()

        feed.latest_data['000001.SZ'] = {'price': 10.0}
        feed.latest_data['600000.SH'] = {'price': 20.0}

        all_data = feed.get_all_latest()

        assert len(all_data) == 2
        assert '000001.SZ' in all_data
        assert '600000.SH' in all_data

    @pytest.mark.asyncio
    async def test_update_loop_empty_subscription(self):
        """Test that update loop handles empty subscription list."""
        feed = SinaRealtimeFeed(config={'update_interval': 0.1})

        await feed.connect()

        # No subscriptions
        await asyncio.sleep(0.3)

        # Should not crash
        assert feed.is_running is True

        await feed.disconnect()

    @pytest.mark.asyncio
    async def test_callback_error_handling(self):
        """Test that callback errors don't break the feed."""
        feed = SinaRealtimeFeed(config={'update_interval': 0.1})

        async def failing_callback(symbol, data):
            raise Exception("Callback error")

        feed.register_callback(failing_callback)

        with patch('src.data_sources.sina_finance.SinaFinanceDataSource') as mock_api_class:
            mock_api = Mock()
            mock_api.get_realtime_quote.return_value = {'current_price': 10.0}
            mock_api_class.return_value = mock_api

            await feed.connect()
            await feed.subscribe(['000001.SZ'])

            # Should not crash
            await asyncio.sleep(0.3)

            assert feed.is_running is True

            await feed.disconnect()

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test handling of API errors."""
        feed = SinaRealtimeFeed(config={'update_interval': 0.1})

        with patch('src.data_sources.sina_finance.SinaFinanceDataSource') as mock_api_class:
            mock_api = Mock()
            mock_api.get_realtime_quote.side_effect = Exception("API error")
            mock_api_class.return_value = mock_api

            await feed.connect()
            await feed.subscribe(['000001.SZ'])

            # Should not crash
            await asyncio.sleep(0.3)

            assert feed.is_running is True

            await feed.disconnect()

    @pytest.mark.asyncio
    async def test_data_structure(self):
        """Test that data has correct structure."""
        feed = SinaRealtimeFeed(config={'update_interval': 0.1})

        data_received = {'data': None}

        async def capture_callback(symbol, data):
            data_received['data'] = data

        feed.register_callback(capture_callback)

        with patch('src.data_sources.sina_finance.SinaFinanceDataSource') as mock_api_class:
            mock_api = Mock()
            mock_api.get_realtime_quote.return_value = {
                'current_price': 10.50,
                'change_pct': 0.02,
                'volume': 1000000,
                'turnover': 10500000,
                'bid_price': 10.49,
                'ask_price': 10.51,
                'high': 10.80,
                'low': 10.20,
                'open': 10.30,
                'prev_close': 10.30
            }
            mock_api_class.return_value = mock_api

            await feed.connect()
            await feed.subscribe(['000001.SZ'])
            await asyncio.sleep(0.3)
            await feed.disconnect()

            data = data_received['data']
            assert data is not None
            assert 'symbol' in data
            assert 'price' in data
            assert 'volume' in data
            assert 'timestamp' in data

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self):
        """Test multiple callbacks registration."""
        feed = SinaRealtimeFeed(config={'update_interval': 0.1})

        call_counts = {'callback1': 0, 'callback2': 0}

        async def callback1(symbol, data):
            call_counts['callback1'] += 1

        async def callback2(symbol, data):
            call_counts['callback2'] += 1

        feed.register_callback(callback1)
        feed.register_callback(callback2)

        with patch('src.data_sources.sina_finance.SinaFinanceDataSource') as mock_api_class:
            mock_api = Mock()
            mock_api.get_realtime_quote.return_value = {'current_price': 10.0}
            mock_api_class.return_value = mock_api

            await feed.connect()
            await feed.subscribe(['000001.SZ'])
            await asyncio.sleep(0.3)
            await feed.disconnect()

            # Both callbacks should be called
            assert call_counts['callback1'] > 0
            assert call_counts['callback2'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])