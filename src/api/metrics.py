# src/api/metrics.py - Metrics and monitoring endpoints
import time
import psutil
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from typing import Dict, List
from config.settings import settings

logger = logging.getLogger(__name__)

metrics_bp = Blueprint('metrics', __name__, url_prefix='/metrics')

# Simple in-memory metrics storage
request_count = 0
request_times: List[float] = []
error_count = 0
start_time = time.time()


def record_request(duration_ms: float, status_code: int):
    """Record request metrics"""
    global request_count, error_count, request_times
    
    request_count += 1
    request_times.append(duration_ms)
    
    # Keep only recent times (last 1000 requests)
    if len(request_times) > 1000:
        request_times = request_times[-1000:]
    
    if status_code >= 400:
        error_count += 1


@metrics_bp.route('/', methods=['GET'])
def get_prometheus_metrics():
    """Prometheus-compatible metrics endpoint"""
    uptime = time.time() - start_time
    
    # Calculate average response time
    avg_response_time = sum(request_times) / len(request_times) if request_times else 0
    
    # Get system metrics
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
    except Exception as e:
        logger.warning(f"Failed to get system metrics: {e}")
        cpu_percent = 0
        memory = type('obj', (object,), {'percent': 0, 'used': 0, 'total': 0})
        disk = type('obj', (object,), {'percent': 0, 'used': 0, 'total': 0})
    
    metrics_data = f"""# HELP stock_api_requests_total Total number of requests
# TYPE stock_api_requests_total counter
stock_api_requests_total {request_count}

# HELP stock_api_errors_total Total number of errors
# TYPE stock_api_errors_total counter
stock_api_errors_total {error_count}

# HELP stock_api_response_time_ms Average response time in milliseconds
# TYPE stock_api_response_time_ms gauge
stock_api_response_time_ms {avg_response_time:.2f}

# HELP stock_api_uptime_seconds Uptime in seconds
# TYPE stock_api_uptime_seconds counter
stock_api_uptime_seconds {uptime:.2f}

# HELP system_cpu_percent CPU usage percentage
# TYPE system_cpu_percent gauge
system_cpu_percent {cpu_percent}

# HELP system_memory_percent Memory usage percentage
# TYPE system_memory_percent gauge
system_memory_percent {memory.percent}

# HELP system_disk_percent Disk usage percentage
# TYPE system_disk_percent gauge
system_disk_percent {disk.percent}

# HELP stock_api_mode_info Mode information
# TYPE stock_api_mode_info gauge
stock_api_mode_info{{deployment_mode="{settings.DEPLOYMENT_MODE}",offline_mode="{settings.OFFLINE_MODE}",use_redis="{settings.USE_REDIS}"}} 1
"""
    
    return metrics_data, 200, {'Content-Type': 'text/plain; charset=utf-8'}


@metrics_bp.route('/health', methods=['GET'])
def detailed_health_check():
    """Detailed health check with multiple components"""
    from src.database import db_manager
    
    health_status = {
        'timestamp': datetime.now().isoformat(),
        'uptime_seconds': time.time() - start_time,
        'version': '1.0.0',
        'environment': settings.DEPLOYMENT_MODE
    }
    
    # Database health
    db_health = db_manager.health_check()
    health_status['database'] = db_health
    
    # System health
    try:
        health_status['system'] = {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
    except Exception as e:
        health_status['system'] = {'error': str(e)}
    
    # Service health
    health_status['services'] = {
        'redis': 'available' if settings.USE_REDIS and not settings.OFFLINE_MODE else 'disabled',
        'external_apis': 'disabled' if settings.OFFLINE_MODE else 'enabled',
        'mock_data': 'enabled' if settings.MOCK_DATA_ENABLED else 'disabled'
    }
    
    # Performance metrics
    health_status['performance'] = {
        'total_requests': request_count,
        'error_rate': (error_count / request_count * 100) if request_count > 0 else 0,
        'avg_response_time_ms': sum(request_times) / len(request_times) if request_times else 0,
        'recent_requests': len(request_times)
    }
    
    # Overall status
    overall_status = 'healthy'
    if db_health['status'] == 'degraded':
        overall_status = 'degraded'
    elif db_health['status'] in ['unhealthy', 'unavailable']:
        overall_status = 'unhealthy'
    
    health_status['status'] = overall_status
    
    status_code = 200 if overall_status in ['healthy', 'degraded'] else 503
    return jsonify(health_status), status_code


@metrics_bp.route('/debug', methods=['GET'])
def debug_info():
    """Debug information endpoint (only in development)"""
    if settings.is_production():
        return jsonify({'error': 'Debug endpoint disabled in production'}), 403
    
    debug_data = {
        'timestamp': datetime.now().isoformat(),
        'python_version': f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}",
        'process_info': {
            'pid': psutil.os.getpid(),
            'memory_mb': psutil.Process().memory_info().rss / 1024 / 1024,
            'cpu_percent': psutil.Process().cpu_percent(),
            'threads': psutil.Process().num_threads(),
            'open_files': len(psutil.Process().open_files()) if hasattr(psutil.Process(), 'open_files') else 0
        },
        'configuration': {
            'database_url': settings.DATABASE_URL.split('@')[0] + '@***' if '@' in settings.DATABASE_URL else 'sqlite',
            'redis_enabled': settings.USE_REDIS,
            'offline_mode': settings.OFFLINE_MODE,
            'log_to_file': settings.LOG_TO_FILE,
            'log_level': settings.LOG_LEVEL,
            'cors_origins': settings.get_cors_origins()
        },
        'request_history': {
            'recent_times_ms': request_times[-10:] if request_times else [],
            'total_requests': request_count,
            'total_errors': error_count
        }
    }
    
    return jsonify(debug_data)


# Metrics collection middleware functions
def before_request_metrics():
    """Record request start time"""
    request.start_time = time.time()


def after_request_metrics(response):
    """Record request completion metrics"""
    if hasattr(request, 'start_time'):
        duration_ms = (time.time() - request.start_time) * 1000
        record_request(duration_ms, response.status_code)
    return response