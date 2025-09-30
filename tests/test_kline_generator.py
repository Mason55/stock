# tests/test_kline_generator.py - K-line generator tests
import pytest
from datetime import datetime, timedelta

from src.data_sources.kline_generator import KLineGenerator, KLine, Tick


class TestKLine:
    """Test KLine class."""

    def test_kline_creation(self):
        """Test K-line creation."""
        kline = KLine(
            symbol='000001.SZ',
            interval='1m',
            timestamp=datetime(2025, 1, 1, 9, 30)
        )

        assert kline.symbol == '000001.SZ'
        assert kline.interval == '1m'
        assert kline.open == 0.0
        assert kline.high == 0.0
        assert kline.low == float('inf')
        assert kline.close == 0.0
        assert kline.volume == 0
        assert kline.tick_count == 0

    def test_kline_update(self):
        """Test K-line update with tick."""
        kline = KLine(
            symbol='000001.SZ',
            interval='1m',
            timestamp=datetime(2025, 1, 1, 9, 30)
        )

        tick = Tick(
            symbol='000001.SZ',
            price=10.50,
            volume=1000,
            timestamp=datetime(2025, 1, 1, 9, 30, 15)
        )

        kline.update(tick)

        assert kline.open == 10.50
        assert kline.high == 10.50
        assert kline.low == 10.50
        assert kline.close == 10.50
        assert kline.volume == 1000
        assert kline.tick_count == 1

    def test_kline_multiple_updates(self):
        """Test K-line with multiple ticks."""
        kline = KLine('000001.SZ', '1m', datetime(2025, 1, 1, 9, 30))

        ticks = [
            Tick('000001.SZ', 10.50, 1000, datetime(2025, 1, 1, 9, 30, 0)),
            Tick('000001.SZ', 10.60, 500, datetime(2025, 1, 1, 9, 30, 15)),
            Tick('000001.SZ', 10.40, 800, datetime(2025, 1, 1, 9, 30, 30)),
            Tick('000001.SZ', 10.55, 600, datetime(2025, 1, 1, 9, 30, 45))
        ]

        for tick in ticks:
            kline.update(tick)

        assert kline.open == 10.50  # First tick
        assert kline.high == 10.60  # Highest
        assert kline.low == 10.40   # Lowest
        assert kline.close == 10.55 # Last tick
        assert kline.volume == 2900 # Sum of volumes
        assert kline.tick_count == 4

    def test_kline_to_dict(self):
        """Test K-line conversion to dict."""
        kline = KLine('000001.SZ', '5m', datetime(2025, 1, 1, 9, 30))
        kline.update(Tick('000001.SZ', 10.50, 1000, datetime.now()))

        kline_dict = kline.to_dict()

        assert kline_dict['symbol'] == '000001.SZ'
        assert kline_dict['interval'] == '5m'
        assert kline_dict['open'] == 10.50
        assert 'timestamp' in kline_dict


class TestKLineGenerator:
    """Test KLineGenerator functionality."""

    def test_initialization(self):
        """Test generator initialization."""
        generator = KLineGenerator(
            intervals=['1m', '5m'],
            config={'save_to_db': False, 'max_history': 500}
        )

        assert '1m' in generator.intervals
        assert '5m' in generator.intervals
        assert generator.save_to_db is False
        assert generator.max_history == 500

    def test_invalid_interval(self):
        """Test that invalid interval raises error."""
        with pytest.raises(ValueError):
            KLineGenerator(intervals=['invalid'])

    def test_process_tick_creates_kline(self):
        """Test that processing tick creates K-line."""
        generator = KLineGenerator(intervals=['1m'])

        timestamp = datetime(2025, 1, 1, 9, 30, 15)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp)

        current = generator.get_current_kline('000001.SZ', '1m')

        assert current is not None
        assert current.symbol == '000001.SZ'
        assert current.close == 10.50

    def test_process_tick_multiple_intervals(self):
        """Test processing tick for multiple intervals."""
        generator = KLineGenerator(intervals=['1m', '5m'])

        timestamp = datetime(2025, 1, 1, 9, 30, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp)

        kline_1m = generator.get_current_kline('000001.SZ', '1m')
        kline_5m = generator.get_current_kline('000001.SZ', '5m')

        assert kline_1m is not None
        assert kline_5m is not None
        assert kline_1m.interval == '1m'
        assert kline_5m.interval == '5m'

    def test_kline_completion_on_time_boundary(self):
        """Test that K-line completes on time boundary."""
        generator = KLineGenerator(intervals=['1m'])

        # First tick at 9:30:00
        timestamp1 = datetime(2025, 1, 1, 9, 30, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp1)

        # Second tick at 9:31:00 (new minute)
        timestamp2 = datetime(2025, 1, 1, 9, 31, 0)
        generator.process_tick('000001.SZ', 10.60, 1000, timestamp2)

        # History should have 1 completed K-line
        history = generator.get_history('000001.SZ', '1m')
        assert len(history) == 1
        assert history[0].close == 10.50

        # Current K-line should be the new one
        current = generator.get_current_kline('000001.SZ', '1m')
        assert current.close == 10.60

    def test_kline_timestamp_alignment(self):
        """Test that K-line timestamps are aligned to boundaries."""
        generator = KLineGenerator(intervals=['1m'])

        # Tick at 9:30:37 should align to 9:30:00
        timestamp = datetime(2025, 1, 1, 9, 30, 37)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp)

        current = generator.get_current_kline('000001.SZ', '1m')
        assert current.timestamp.minute == 30
        assert current.timestamp.second == 0

    def test_5min_kline_alignment(self):
        """Test 5-minute K-line alignment."""
        generator = KLineGenerator(intervals=['5m'])

        # 9:32 should align to 9:30
        timestamp1 = datetime(2025, 1, 1, 9, 32, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp1)

        current = generator.get_current_kline('000001.SZ', '5m')
        assert current.timestamp.minute == 30

        # 9:37 should align to 9:35
        timestamp2 = datetime(2025, 1, 1, 9, 37, 0)
        generator.process_tick('000001.SZ', 10.60, 1000, timestamp2)

        current = generator.get_current_kline('000001.SZ', '5m')
        assert current.timestamp.minute == 35

    def test_callback_registration(self):
        """Test callback registration."""
        generator = KLineGenerator(intervals=['1m'])

        callback_called = {'count': 0}

        def test_callback(kline):
            callback_called['count'] += 1

        generator.register_callback('1m', test_callback)

        assert len(generator.callbacks['1m']) == 1

    def test_callback_invoked_on_completion(self):
        """Test that callback is invoked when K-line completes."""
        generator = KLineGenerator(intervals=['1m'])

        completed_klines = []

        def test_callback(kline):
            completed_klines.append(kline)

        generator.register_callback('1m', test_callback)

        # First tick
        timestamp1 = datetime(2025, 1, 1, 9, 30, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp1)

        assert len(completed_klines) == 0

        # Second tick (completes first K-line)
        timestamp2 = datetime(2025, 1, 1, 9, 31, 0)
        generator.process_tick('000001.SZ', 10.60, 1000, timestamp2)

        assert len(completed_klines) == 1
        assert completed_klines[0].close == 10.50

    def test_callback_error_handling(self):
        """Test that callback errors don't break processing."""
        generator = KLineGenerator(intervals=['1m'])

        def failing_callback(kline):
            raise Exception("Callback error")

        generator.register_callback('1m', failing_callback)

        # Should not crash
        timestamp1 = datetime(2025, 1, 1, 9, 30, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp1)

        timestamp2 = datetime(2025, 1, 1, 9, 31, 0)
        generator.process_tick('000001.SZ', 10.60, 1000, timestamp2)

        # Should have completed despite error
        history = generator.get_history('000001.SZ', '1m')
        assert len(history) == 1

    def test_get_history(self):
        """Test getting K-line history."""
        generator = KLineGenerator(intervals=['1m'])

        # Generate 5 K-lines
        for i in range(5):
            timestamp = datetime(2025, 1, 1, 9, 30 + i, 0)
            generator.process_tick('000001.SZ', 10.50 + i*0.1, 1000, timestamp)

        # Complete by going to next minute
        timestamp_final = datetime(2025, 1, 1, 9, 35, 0)
        generator.process_tick('000001.SZ', 11.0, 1000, timestamp_final)

        history = generator.get_history('000001.SZ', '1m', count=3)

        assert len(history) == 3
        # Should be most recent 3
        assert history[0].timestamp.minute == 32

    def test_get_latest_kline(self):
        """Test getting latest completed K-line."""
        generator = KLineGenerator(intervals=['1m'])

        timestamp1 = datetime(2025, 1, 1, 9, 30, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp1)

        # Complete K-line
        timestamp2 = datetime(2025, 1, 1, 9, 31, 0)
        generator.process_tick('000001.SZ', 10.60, 1000, timestamp2)

        latest = generator.get_latest_kline('000001.SZ', '1m')

        assert latest is not None
        assert latest.close == 10.50

    def test_history_trimming(self):
        """Test that history is trimmed to max_history."""
        generator = KLineGenerator(
            intervals=['1m'],
            config={'max_history': 5}
        )

        # Generate 10 K-lines
        for i in range(10):
            timestamp = datetime(2025, 1, 1, 9, 30 + i, 0)
            generator.process_tick('000001.SZ', 10.50 + i*0.1, 1000, timestamp)

        # Complete all
        timestamp_final = datetime(2025, 1, 1, 9, 40, 0)
        generator.process_tick('000001.SZ', 11.5, 1000, timestamp_final)

        history = generator.get_history('000001.SZ', '1m', count=100)

        # Should be trimmed to 5
        assert len(history) <= 5

    def test_calculate_indicators(self):
        """Test technical indicator calculation."""
        generator = KLineGenerator(intervals=['1m'])

        # Generate 20 K-lines
        for i in range(20):
            timestamp = datetime(2025, 1, 1, 9, 30 + i, 0)
            generator.process_tick('000001.SZ', 10.0 + i*0.1, 1000 + i*100, timestamp)

        # Complete
        timestamp_final = datetime(2025, 1, 1, 9, 50, 0)
        generator.process_tick('000001.SZ', 12.0, 3000, timestamp_final)

        indicators = generator.calculate_indicators('000001.SZ', '1m', period=20)

        assert 'ma' in indicators
        assert 'ema' in indicators
        assert 'volume_ma' in indicators
        assert indicators['period'] == 20
        assert indicators['ma'] > 0
        assert indicators['ema'] > 0

    def test_calculate_indicators_insufficient_data(self):
        """Test indicator calculation with insufficient data."""
        generator = KLineGenerator(intervals=['1m'])

        # Only 5 K-lines
        for i in range(5):
            timestamp = datetime(2025, 1, 1, 9, 30 + i, 0)
            generator.process_tick('000001.SZ', 10.0, 1000, timestamp)

        indicators = generator.calculate_indicators('000001.SZ', '1m', period=20)

        # Should return empty dict
        assert indicators == {}

    def test_get_statistics(self):
        """Test generator statistics."""
        generator = KLineGenerator(intervals=['1m', '5m'])

        # Process some ticks
        timestamp = datetime(2025, 1, 1, 9, 30, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp)
        generator.process_tick('600000.SH', 20.50, 2000, timestamp)

        stats = generator.get_statistics()

        assert stats['active_symbols'] == 2
        assert stats['active_klines'] == 4  # 2 symbols × 2 intervals
        assert stats['intervals'] == ['1m', '5m']

    def test_multiple_symbols(self):
        """Test handling multiple symbols simultaneously."""
        generator = KLineGenerator(intervals=['1m'])

        timestamp = datetime(2025, 1, 1, 9, 30, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp)
        generator.process_tick('600000.SH', 20.50, 2000, timestamp)
        generator.process_tick('000002.SZ', 15.50, 1500, timestamp)

        kline1 = generator.get_current_kline('000001.SZ', '1m')
        kline2 = generator.get_current_kline('600000.SH', '1m')
        kline3 = generator.get_current_kline('000002.SZ', '1m')

        assert kline1.close == 10.50
        assert kline2.close == 20.50
        assert kline3.close == 15.50

    def test_15min_interval(self):
        """Test 15-minute interval."""
        generator = KLineGenerator(intervals=['15m'])

        # 9:37 should align to 9:30
        timestamp1 = datetime(2025, 1, 1, 9, 37, 0)
        generator.process_tick('000001.SZ', 10.50, 1000, timestamp1)

        current = generator.get_current_kline('000001.SZ', '15m')
        assert current.timestamp.minute == 30

        # 9:47 should complete first 15m and start new one at 9:45
        timestamp2 = datetime(2025, 1, 1, 9, 47, 0)
        generator.process_tick('000001.SZ', 10.60, 1000, timestamp2)

        current = generator.get_current_kline('000001.SZ', '15m')
        assert current.timestamp.minute == 45

        history = generator.get_history('000001.SZ', '15m')
        assert len(history) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])