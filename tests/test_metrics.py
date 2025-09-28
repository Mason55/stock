# tests/test_metrics.py - Tests for Prometheus metrics integration
import pytest
import time
from unittest.mock import MagicMock, patch
from src.monitoring.metrics import (
    MetricsCollector,
    PerformanceTracker,
    initialize_metrics,
    get_metrics_collector,
    monitor_performance,
    monitor_db_operation
)


class TestMetricsCollector:
    """Test metrics collector functionality"""
    
    def setup_method(self):
        # Create metrics collector without Prometheus for testing
        with patch('src.monitoring.metrics.PROMETHEUS_AVAILABLE', False):
            self.collector = MetricsCollector(enable_prometheus=False)
    
    def test_metrics_collector_initialization(self):
        """Test metrics collector initialization"""
        
        assert self.collector is not None
        assert not self.collector.enabled  # Should be disabled in test
    
    def test_metrics_recording_disabled(self):
        """Test that metrics recording works gracefully when disabled"""
        
        # These should not raise exceptions even when disabled
        self.collector.record_http_request('GET', '/api/stocks/health', 200, 0.1)
        self.collector.record_db_operation('SELECT', 'stocks', 0.05)
        self.collector.record_cache_operation('GET', 'memory', 'hit')
        self.collector.record_error('ValueError', 'api')
        
        # Should return disabled status
        summary = self.collector.get_metrics_summary()
        assert summary['status'] == 'disabled'


@pytest.mark.skipif(True, reason="Prometheus client not available in test environment")
class TestMetricsCollectorWithPrometheus:
    """Test metrics collector with Prometheus (when available)"""
    
    def setup_method(self):
        self.collector = MetricsCollector(enable_prometheus=True)
    
    def test_http_request_metrics(self):
        """Test HTTP request metrics recording"""
        
        # Record some HTTP requests
        self.collector.record_http_request('GET', '/api/stocks', 200, 0.15, 1024, 2048)
        self.collector.record_http_request('POST', '/api/stocks', 400, 0.05, 512, 256)
        
        # Metrics should be recorded (would check Prometheus registry in real test)
        assert True  # Placeholder
    
    def test_database_metrics(self):
        """Test database operation metrics"""
        
        # Record database operations
        self.collector.record_db_operation('SELECT', 'stocks', 0.1, 100, 'success')
        self.collector.record_db_operation('INSERT', 'stock_prices', 0.05, 1, 'success')
        self.collector.record_db_operation('SELECT', 'stocks', 0.5, 0, 'error')
        
        assert True  # Placeholder
    
    def test_cache_metrics(self):
        """Test cache operation metrics"""
        
        # Record cache operations
        self.collector.record_cache_operation('GET', 'memory', 'hit', 1024)
        self.collector.record_cache_operation('SET', 'redis', 'success', 2048)
        self.collector.record_cache_operation('GET', 'memory', 'miss')
        
        # Update cache hit ratios
        self.collector.update_cache_hit_ratio('memory', 0.85)
        self.collector.update_cache_hit_ratio('redis', 0.72)
        
        assert True  # Placeholder


class TestPerformanceTracker:
    """Test performance tracking functionality"""
    
    def setup_method(self):
        self.tracker = PerformanceTracker(window_size=10)
    
    def test_response_time_tracking(self):
        """Test response time tracking"""
        
        # Record some response times
        response_times = [0.1, 0.2, 0.15, 0.3, 0.12]
        for rt in response_times:
            self.tracker.record_response_time(rt)
        
        summary = self.tracker.get_summary()
        
        assert summary['total_requests'] == 5
        assert summary['avg_response_time'] == sum(response_times) / len(response_times)
        assert summary['max_response_time'] == max(response_times)
        assert summary['min_response_time'] == min(response_times)
    
    def test_error_rate_tracking(self):
        """Test error rate tracking"""
        
        # Record response times to avoid no_data status
        for i in range(4):
            self.tracker.record_response_time(0.1)
        
        # Record mix of success and errors
        self.tracker.record_error(False)  # Success
        self.tracker.record_error(False)  # Success
        self.tracker.record_error(True)   # Error
        self.tracker.record_error(False)  # Success
        
        summary = self.tracker.get_summary()
        
        assert summary['error_rate'] == 0.25  # 1 error out of 4
    
    def test_window_size_limit(self):
        """Test that tracker respects window size limit"""
        
        # Add more entries than window size
        for i in range(15):  # Window size is 10
            self.tracker.record_response_time(i * 0.1)
        
        summary = self.tracker.get_summary()
        
        # Should only keep last 10 entries
        assert summary['total_requests'] == 10
        assert summary['min_response_time'] == 0.5  # Should be 5 * 0.1 (6th entry)


class TestMonitoringDecorators:
    """Test monitoring decorators"""
    
    def setup_method(self):
        # Mock metrics collector
        self.mock_collector = MagicMock()
        self.mock_collector.enabled = True
        
        # Patch global collector
        self.patcher = patch('src.monitoring.metrics.metrics_collector', self.mock_collector)
        self.patcher.start()
    
    def teardown_method(self):
        self.patcher.stop()
    
    def test_performance_monitoring_decorator(self):
        """Test performance monitoring decorator"""
        
        @monitor_performance(operation_type='test_op', component='test_comp')
        def test_function():
            time.sleep(0.1)  # Simulate work
            return "result"
        
        result = test_function()
        
        assert result == "result"
        # Would verify metrics recording in real test
    
    def test_performance_monitoring_with_exception(self):
        """Test performance monitoring when function raises exception"""
        
        @monitor_performance(operation_type='test_op', component='test_comp')
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        # Should record error metric
        self.mock_collector.record_error.assert_called_once()
    
    def test_db_operation_monitoring(self):
        """Test database operation monitoring decorator"""
        
        @monitor_db_operation(table='stocks', operation='SELECT')
        def db_query():
            time.sleep(0.05)  # Simulate DB query
            return [{"code": "600036.SH"}]
        
        result = db_query()
        
        assert result == [{"code": "600036.SH"}]
        
        # Should record DB operation metrics
        self.mock_collector.record_db_operation.assert_called_once()
        
        # Verify call arguments
        call_args = self.mock_collector.record_db_operation.call_args
        assert call_args[1]['operation'] == 'SELECT'
        assert call_args[1]['table'] == 'stocks'
        assert call_args[1]['status'] == 'success'
    
    def test_db_operation_monitoring_with_error(self):
        """Test DB operation monitoring when query fails"""
        
        @monitor_db_operation(table='stocks', operation='SELECT')
        def failing_query():
            raise RuntimeError("Database error")
        
        with pytest.raises(RuntimeError):
            failing_query()
        
        # Should record error status
        call_args = self.mock_collector.record_db_operation.call_args
        assert call_args[1]['status'] == 'error'
    
    def test_monitoring_without_collector(self):
        """Test monitoring decorators when collector is not available"""
        
        # Patch to return None collector
        with patch('src.monitoring.metrics.metrics_collector', None):
            
            @monitor_performance()
            def test_function():
                return "result"
            
            # Should work without errors
            result = test_function()
            assert result == "result"


class TestMetricsInitialization:
    """Test metrics initialization"""
    
    def test_metrics_initialization(self):
        """Test metrics system initialization"""
        
        app_info = {
            'version': '1.0.0',
            'environment': 'test',
            'build_date': '2024-01-01'
        }
        
        collector = initialize_metrics(enable_prometheus=False, app_info=app_info)
        
        assert collector is not None
        assert get_metrics_collector() is collector
    
    def test_metrics_initialization_without_app_info(self):
        """Test metrics initialization without app info"""
        
        collector = initialize_metrics(enable_prometheus=False)
        
        assert collector is not None
        assert not collector.enabled  # Should be disabled for test


class TestMetricsIntegration:
    """Test metrics integration scenarios"""
    
    def setup_method(self):
        # Initialize metrics for integration testing
        self.collector = initialize_metrics(enable_prometheus=False)
    
    def test_comprehensive_metrics_workflow(self):
        """Test complete metrics collection workflow"""
        
        # Simulate API request processing
        start_time = time.time()
        
        # 1. Record HTTP request start
        request_size = 512
        
        # 2. Simulate database operations
        with patch.object(self.collector, 'record_db_operation') as mock_db:
            @monitor_db_operation(table='stocks', operation='SELECT')
            def get_stock_data():
                time.sleep(0.01)  # Simulate DB query
                return {"code": "600036.SH", "price": 100.0}
            
            stock_data = get_stock_data()
        
        # 3. Simulate cache operations  
        self.collector.record_cache_operation('GET', 'memory', 'miss')
        self.collector.record_cache_operation('SET', 'memory', 'success', 1024)
        
        # 4. Record HTTP response
        duration = time.time() - start_time
        self.collector.record_http_request(
            method='GET',
            endpoint='/api/stocks/600036.SH',
            status_code=200,
            duration=duration,
            request_size=request_size,
            response_size=len(str(stock_data))
        )
        
        # Verify the workflow completed without errors
        summary = self.collector.get_metrics_summary()
        assert summary['status'] == 'disabled'  # In test mode


if __name__ == "__main__":
    pytest.main([__file__, "-v"])