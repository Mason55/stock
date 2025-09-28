# src/monitoring/metrics.py - Prometheus metrics collection for stock analysis system
import time
import logging
from typing import Dict, Any, Optional, List
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict, deque
from threading import Lock
import psutil
import threading

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary, Info, 
        generate_latest, CONTENT_TYPE_LATEST,
        CollectorRegistry, multiprocess, REGISTRY
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("Prometheus client not available. Metrics collection disabled.")
    PROMETHEUS_AVAILABLE = False
    
    # Create dummy classes for graceful fallback
    class DummyMetric:
        def inc(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    Counter = Histogram = Gauge = Summary = Info = DummyMetric


class MetricsCollector:
    """Central metrics collector for stock analysis system"""
    
    def __init__(self, enable_prometheus: bool = True):
        self.enabled = enable_prometheus and PROMETHEUS_AVAILABLE
        self._lock = Lock()
        
        if not self.enabled:
            logger.warning("Metrics collection disabled")
            return
        
        # API Performance Metrics
        self.http_requests_total = Counter(
            'stock_api_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code']
        )
        
        self.http_request_duration = Histogram(
            'stock_api_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        self.http_request_size = Histogram(
            'stock_api_request_size_bytes',
            'HTTP request size in bytes',
            ['method', 'endpoint'],
            buckets=[100, 1000, 10000, 100000, 1000000]
        )
        
        self.http_response_size = Histogram(
            'stock_api_response_size_bytes',
            'HTTP response size in bytes',
            ['method', 'endpoint'],
            buckets=[100, 1000, 10000, 100000, 1000000]
        )
        
        # Database Metrics
        self.db_operations_total = Counter(
            'stock_db_operations_total',
            'Total database operations',
            ['operation', 'table', 'status']
        )
        
        self.db_operation_duration = Histogram(
            'stock_db_operation_duration_seconds',
            'Database operation duration in seconds',
            ['operation', 'table'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
        )
        
        self.db_connections_active = Gauge(
            'stock_db_connections_active',
            'Number of active database connections'
        )
        
        self.db_query_rows_affected = Histogram(
            'stock_db_query_rows_affected',
            'Number of rows affected by database queries',
            ['operation', 'table'],
            buckets=[1, 10, 100, 1000, 10000, 100000]
        )
        
        # Cache Metrics
        self.cache_operations_total = Counter(
            'stock_cache_operations_total',
            'Total cache operations',
            ['operation', 'cache_level', 'status']
        )
        
        self.cache_hit_ratio = Gauge(
            'stock_cache_hit_ratio',
            'Cache hit ratio',
            ['cache_level']
        )
        
        self.cache_size_bytes = Gauge(
            'stock_cache_size_bytes',
            'Cache size in bytes',
            ['cache_level']
        )
        
        self.cache_evictions_total = Counter(
            'stock_cache_evictions_total',
            'Total cache evictions',
            ['cache_level', 'reason']
        )
        
        # Business Logic Metrics
        self.stock_analysis_requests = Counter(
            'stock_analysis_requests_total',
            'Total stock analysis requests',
            ['analysis_type', 'stock_code']
        )
        
        self.stock_analysis_duration = Histogram(
            'stock_analysis_duration_seconds',
            'Stock analysis duration in seconds',
            ['analysis_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        
        self.recommendation_accuracy = Histogram(
            'stock_recommendation_accuracy',
            'Recommendation accuracy score',
            ['model_type'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )
        
        self.data_freshness = Gauge(
            'stock_data_freshness_seconds',
            'Age of stock data in seconds',
            ['data_type', 'stock_code']
        )
        
        # System Metrics
        self.system_cpu_usage = Gauge(
            'stock_system_cpu_usage_percent',
            'System CPU usage percentage'
        )
        
        self.system_memory_usage = Gauge(
            'stock_system_memory_usage_bytes',
            'System memory usage in bytes',
            ['type']  # used, available, total
        )
        
        self.system_disk_usage = Gauge(
            'stock_system_disk_usage_bytes',
            'System disk usage in bytes',
            ['type', 'mount_point']  # used, free, total
        )
        
        # Error Metrics
        self.errors_total = Counter(
            'stock_errors_total',
            'Total errors',
            ['error_type', 'component', 'severity']
        )
        
        self.security_events_total = Counter(
            'stock_security_events_total',
            'Total security events',
            ['event_type', 'severity', 'source_ip']
        )
        
        # Application Info
        self.app_info = Info(
            'stock_app_info',
            'Application information'
        )
        
        # Performance tracking
        self.performance_tracker = PerformanceTracker()
        
        # Start background metrics collection
        self._start_background_collection()
        
        logger.info("Metrics collector initialized with Prometheus")
    
    def _start_background_collection(self):
        """Start background thread for system metrics collection"""
        if not self.enabled:
            return
            
        def collect_system_metrics():
            while True:
                try:
                    # CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    self.system_cpu_usage.set(cpu_percent)
                    
                    # Memory usage
                    memory = psutil.virtual_memory()
                    self.system_memory_usage.labels(type='used').set(memory.used)
                    self.system_memory_usage.labels(type='available').set(memory.available)
                    self.system_memory_usage.labels(type='total').set(memory.total)
                    
                    # Disk usage
                    disk = psutil.disk_usage('/')
                    self.system_disk_usage.labels(type='used', mount_point='/').set(disk.used)
                    self.system_disk_usage.labels(type='free', mount_point='/').set(disk.free)
                    self.system_disk_usage.labels(type='total', mount_point='/').set(disk.total)
                    
                except Exception as e:
                    logger.warning(f"Failed to collect system metrics: {e}")
                
                time.sleep(30)  # Collect every 30 seconds
        
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()
    
    def record_http_request(self, method: str, endpoint: str, 
                           status_code: int, duration: float,
                           request_size: int = 0, response_size: int = 0):
        """Record HTTP request metrics"""
        if not self.enabled:
            return
            
        self.http_requests_total.labels(
            method=method, 
            endpoint=endpoint, 
            status_code=str(status_code)
        ).inc()
        
        self.http_request_duration.labels(
            method=method, 
            endpoint=endpoint
        ).observe(duration)
        
        if request_size > 0:
            self.http_request_size.labels(
                method=method, 
                endpoint=endpoint
            ).observe(request_size)
        
        if response_size > 0:
            self.http_response_size.labels(
                method=method, 
                endpoint=endpoint
            ).observe(response_size)
    
    def record_db_operation(self, operation: str, table: str, 
                           duration: float, rows_affected: int = 0,
                           status: str = 'success'):
        """Record database operation metrics"""
        if not self.enabled:
            return
            
        self.db_operations_total.labels(
            operation=operation, 
            table=table, 
            status=status
        ).inc()
        
        self.db_operation_duration.labels(
            operation=operation, 
            table=table
        ).observe(duration)
        
        if rows_affected > 0:
            self.db_query_rows_affected.labels(
                operation=operation, 
                table=table
            ).observe(rows_affected)
    
    def record_cache_operation(self, operation: str, cache_level: str, 
                              status: str, size_bytes: int = 0):
        """Record cache operation metrics"""
        if not self.enabled:
            return
            
        self.cache_operations_total.labels(
            operation=operation, 
            cache_level=cache_level, 
            status=status
        ).inc()
        
        if size_bytes > 0:
            self.cache_size_bytes.labels(cache_level=cache_level).set(size_bytes)
    
    def record_analysis_request(self, analysis_type: str, stock_code: str, 
                               duration: float):
        """Record stock analysis request metrics"""
        if not self.enabled:
            return
            
        self.stock_analysis_requests.labels(
            analysis_type=analysis_type, 
            stock_code=stock_code
        ).inc()
        
        self.stock_analysis_duration.labels(
            analysis_type=analysis_type
        ).observe(duration)
    
    def record_error(self, error_type: str, component: str, 
                    severity: str = 'error'):
        """Record error metrics"""
        if not self.enabled:
            return
            
        self.errors_total.labels(
            error_type=error_type, 
            component=component, 
            severity=severity
        ).inc()
    
    def record_security_event(self, event_type: str, severity: str, 
                             source_ip: str = 'unknown'):
        """Record security event metrics"""
        if not self.enabled:
            return
            
        self.security_events_total.labels(
            event_type=event_type, 
            severity=severity, 
            source_ip=source_ip
        ).inc()
    
    def update_cache_hit_ratio(self, cache_level: str, hit_ratio: float):
        """Update cache hit ratio"""
        if not self.enabled:
            return
            
        self.cache_hit_ratio.labels(cache_level=cache_level).set(hit_ratio)
    
    def update_data_freshness(self, data_type: str, stock_code: str, 
                             age_seconds: float):
        """Update data freshness metrics"""
        if not self.enabled:
            return
            
        self.data_freshness.labels(
            data_type=data_type, 
            stock_code=stock_code
        ).set(age_seconds)
    
    def set_app_info(self, version: str, environment: str, 
                    build_date: str = None):
        """Set application information"""
        if not self.enabled:
            return
            
        info_dict = {
            'version': version,
            'environment': environment
        }
        
        if build_date:
            info_dict['build_date'] = build_date
            
        self.app_info.info(info_dict)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary for debugging"""
        if not self.enabled:
            return {'status': 'disabled'}
            
        return {
            'status': 'enabled',
            'performance': self.performance_tracker.get_summary(),
            'collection_time': datetime.now().isoformat()
        }


class PerformanceTracker:
    """Track performance metrics over time"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.response_times = deque(maxlen=window_size)
        self.error_rates = deque(maxlen=window_size)
        self._lock = Lock()
    
    def record_response_time(self, duration: float):
        """Record response time"""
        with self._lock:
            self.response_times.append({
                'duration': duration,
                'timestamp': time.time()
            })
    
    def record_error(self, error_occurred: bool = True):
        """Record error occurrence"""
        with self._lock:
            self.error_rates.append({
                'error': error_occurred,
                'timestamp': time.time()
            })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        with self._lock:
            if not self.response_times:
                return {'status': 'no_data'}
            
            recent_times = [r['duration'] for r in self.response_times]
            recent_errors = [r['error'] for r in self.error_rates]
            
            return {
                'avg_response_time': sum(recent_times) / len(recent_times),
                'max_response_time': max(recent_times),
                'min_response_time': min(recent_times),
                'error_rate': sum(recent_errors) / len(recent_errors) if recent_errors else 0,
                'total_requests': len(self.response_times)
            }


# Global metrics collector instance
metrics_collector: Optional[MetricsCollector] = None


def initialize_metrics(enable_prometheus: bool = True, app_info: Dict[str, str] = None):
    """Initialize global metrics collector"""
    global metrics_collector
    
    metrics_collector = MetricsCollector(enable_prometheus=enable_prometheus)
    
    if app_info and metrics_collector.enabled:
        metrics_collector.set_app_info(
            version=app_info.get('version', 'unknown'),
            environment=app_info.get('environment', 'development'),
            build_date=app_info.get('build_date')
        )
    
    logger.info("Metrics system initialized")
    return metrics_collector


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get global metrics collector"""
    return metrics_collector


# Decorators for automatic metrics collection
def monitor_performance(operation_type: str = None, 
                       component: str = None):
    """Decorator to monitor function performance"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not metrics_collector or not metrics_collector.enabled:
                return func(*args, **kwargs)
            
            start_time = time.time()
            operation = operation_type or func.__name__
            comp = component or func.__module__
            
            try:
                result = func(*args, **kwargs)
                
                # Record successful operation
                duration = time.time() - start_time
                
                if hasattr(metrics_collector, 'performance_tracker'):
                    metrics_collector.performance_tracker.record_response_time(duration)
                
                return result
                
            except Exception as e:
                # Record error
                metrics_collector.record_error(
                    error_type=type(e).__name__,
                    component=comp,
                    severity='error'
                )
                
                if hasattr(metrics_collector, 'performance_tracker'):
                    metrics_collector.performance_tracker.record_error(True)
                
                raise
        
        return wrapper
    return decorator


def monitor_db_operation(table: str = None, operation: str = None):
    """Decorator to monitor database operations"""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not metrics_collector or not metrics_collector.enabled:
                return func(*args, **kwargs)
            
            start_time = time.time()
            op = operation or func.__name__
            tbl = table or 'unknown'
            
            try:
                result = func(*args, **kwargs)
                
                # Record successful operation
                duration = time.time() - start_time
                metrics_collector.record_db_operation(
                    operation=op,
                    table=tbl,
                    duration=duration,
                    status='success'
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                metrics_collector.record_db_operation(
                    operation=op,
                    table=tbl,
                    duration=duration,
                    status='error'
                )
                raise
        
        return wrapper
    return decorator


def get_prometheus_metrics():
    """Get Prometheus metrics for /metrics endpoint"""
    if not PROMETHEUS_AVAILABLE:
        return "# Prometheus metrics not available\n", "text/plain"
    
    try:
        return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}")
        return f"# Error generating metrics: {e}\n", "text/plain"