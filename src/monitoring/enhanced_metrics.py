# src/monitoring/enhanced_metrics.py - Enhanced Prometheus metrics collection
import logging
import time
from collections import defaultdict
from typing import Dict

try:
    from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Fallback implementations
    class Counter:
        def __init__(self, *args, **kwargs):
            self.value = 0
        def inc(self, amount=1):
            self.value += amount
        def labels(self, *args, **kwargs):
            return self

    class Gauge:
        def __init__(self, *args, **kwargs):
            self.value = 0
        def set(self, value):
            self.value = value
        def inc(self, amount=1):
            self.value += amount
        def dec(self, amount=1):
            self.value -= amount
        def labels(self, *args, **kwargs):
            return self

    class Histogram:
        def __init__(self, *args, **kwargs):
            self.values = []
        def observe(self, value):
            self.values.append(value)
        def labels(self, *args, **kwargs):
            return self

    class Info:
        def __init__(self, *args, **kwargs):
            pass
        def info(self, data):
            pass

    def generate_latest():
        return b""

logger = logging.getLogger(__name__)


class EnhancedMetricsCollector:
    """Enhanced metrics collector with detailed application metrics"""

    def __init__(self):
        # HTTP metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )

        self.http_request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        )

        self.http_requests_in_progress = Gauge(
            "http_requests_in_progress",
            "HTTP requests currently being processed",
            ["method", "endpoint"],
        )

        # Database metrics
        self.db_queries_total = Counter(
            "db_queries_total",
            "Total database queries",
            ["operation", "table"],
        )

        self.db_query_duration = Histogram(
            "db_query_duration_seconds",
            "Database query duration",
            ["operation", "table"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
        )

        self.db_connection_pool_size = Gauge(
            "db_connection_pool_size",
            "Database connection pool size",
        )

        self.db_connection_pool_available = Gauge(
            "db_connection_pool_available",
            "Available database connections",
        )

        # Cache metrics
        self.cache_hits_total = Counter(
            "cache_hits_total",
            "Total cache hits",
            ["cache_type"],
        )

        self.cache_misses_total = Counter(
            "cache_misses_total",
            "Total cache misses",
            ["cache_type"],
        )

        self.cache_size_bytes = Gauge(
            "cache_size_bytes",
            "Cache size in bytes",
            ["cache_type"],
        )

        # Stock analysis metrics
        self.stock_analysis_total = Counter(
            "stock_analysis_total",
            "Total stock analyses performed",
            ["analysis_type"],
        )

        self.stock_analysis_duration = Histogram(
            "stock_analysis_duration_seconds",
            "Stock analysis duration",
            ["analysis_type"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )

        self.stock_analysis_errors = Counter(
            "stock_analysis_errors_total",
            "Stock analysis errors",
            ["analysis_type", "error_type"],
        )

        # Data source metrics
        self.data_source_requests = Counter(
            "data_source_requests_total",
            "Data source requests",
            ["source", "symbol"],
        )

        self.data_source_failures = Counter(
            "data_source_failures_total",
            "Data source failures",
            ["source", "error_type"],
        )

        self.data_source_latency = Histogram(
            "data_source_latency_seconds",
            "Data source request latency",
            ["source"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        )

        # Strategy metrics
        self.strategy_signals_total = Counter(
            "strategy_signals_total",
            "Total trading signals generated",
            ["strategy", "signal_type"],
        )

        self.strategy_execution_duration = Histogram(
            "strategy_execution_duration_seconds",
            "Strategy execution duration",
            ["strategy"],
        )

        self.active_positions = Gauge(
            "active_positions",
            "Number of active positions",
            ["strategy"],
        )

        # ETL metrics
        self.etl_runs_total = Counter(
            "etl_runs_total",
            "Total ETL runs",
            ["job_type", "status"],
        )

        self.etl_duration = Histogram(
            "etl_duration_seconds",
            "ETL job duration",
            ["job_type"],
            buckets=[10, 30, 60, 300, 600, 1800, 3600],
        )

        self.etl_records_processed = Counter(
            "etl_records_processed_total",
            "Total records processed by ETL",
            ["job_type", "table"],
        )

        # System health metrics
        self.app_info = Info(
            "stock_analysis_app",
            "Application information",
        )

        self.healthy_components = Gauge(
            "healthy_components",
            "Number of healthy system components",
        )

        # Rate limiting metrics
        self.rate_limit_hits = Counter(
            "rate_limit_hits_total",
            "Rate limit hits",
            ["endpoint", "client"],
        )

        # Initialize app info
        if PROMETHEUS_AVAILABLE:
            self.app_info.info(
                {
                    "version": "1.0.0",
                    "environment": "production",
                }
            )

    def record_http_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        self.http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def record_db_query(self, operation: str, table: str, duration: float):
        """Record database query metrics"""
        self.db_queries_total.labels(operation=operation, table=table).inc()
        self.db_query_duration.labels(operation=operation, table=table).observe(duration)

    def record_cache_hit(self, cache_type: str):
        """Record cache hit"""
        self.cache_hits_total.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str):
        """Record cache miss"""
        self.cache_misses_total.labels(cache_type=cache_type).inc()

    def record_stock_analysis(self, analysis_type: str, duration: float, success: bool = True, error_type: str = None):
        """Record stock analysis metrics"""
        self.stock_analysis_total.labels(analysis_type=analysis_type).inc()
        self.stock_analysis_duration.labels(analysis_type=analysis_type).observe(duration)
        if not success and error_type:
            self.stock_analysis_errors.labels(
                analysis_type=analysis_type, error_type=error_type
            ).inc()

    def record_data_source_request(self, source: str, symbol: str, duration: float, success: bool = True, error_type: str = None):
        """Record data source request metrics"""
        self.data_source_requests.labels(source=source, symbol=symbol).inc()
        self.data_source_latency.labels(source=source).observe(duration)
        if not success and error_type:
            self.data_source_failures.labels(source=source, error_type=error_type).inc()

    def record_strategy_signal(self, strategy: str, signal_type: str):
        """Record trading signal"""
        self.strategy_signals_total.labels(strategy=strategy, signal_type=signal_type).inc()

    def record_etl_run(self, job_type: str, duration: float, records_processed: int, status: str = "success"):
        """Record ETL run metrics"""
        self.etl_runs_total.labels(job_type=job_type, status=status).inc()
        self.etl_duration.labels(job_type=job_type).observe(duration)

    def update_connection_pool_stats(self, pool_size: int, available: int):
        """Update connection pool statistics"""
        self.db_connection_pool_size.set(pool_size)
        self.db_connection_pool_available.set(available)

    def export_metrics(self) -> bytes:
        """Export metrics in Prometheus format"""
        if PROMETHEUS_AVAILABLE:
            return generate_latest()
        else:
            return b"# Prometheus client not available\n"


# Global metrics collector instance
metrics_collector = EnhancedMetricsCollector()


# Context managers for automatic metric recording
class MetricsContext:
    """Context manager for recording metrics"""

    def __init__(self, collector: EnhancedMetricsCollector, metric_type: str, **labels):
        self.collector = collector
        self.metric_type = metric_type
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if self.metric_type == "http":
            self.collector.record_http_request(
                method=self.labels.get("method"),
                endpoint=self.labels.get("endpoint"),
                status=self.labels.get("status", 500 if exc_type else 200),
                duration=duration,
            )
        elif self.metric_type == "db":
            self.collector.record_db_query(
                operation=self.labels.get("operation"),
                table=self.labels.get("table"),
                duration=duration,
            )
        elif self.metric_type == "analysis":
            self.collector.record_stock_analysis(
                analysis_type=self.labels.get("analysis_type"),
                duration=duration,
                success=exc_type is None,
                error_type=exc_type.__name__ if exc_type else None,
            )

        return False  # Don't suppress exceptions


def track_http_request(method: str, endpoint: str):
    """Decorator for tracking HTTP requests"""
    return MetricsContext(metrics_collector, "http", method=method, endpoint=endpoint)


def track_db_query(operation: str, table: str):
    """Decorator for tracking database queries"""
    return MetricsContext(metrics_collector, "db", operation=operation, table=table)


def track_analysis(analysis_type: str):
    """Decorator for tracking stock analysis"""
    return MetricsContext(metrics_collector, "analysis", analysis_type=analysis_type)