# src/utils/logger.py
import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime


def setup_logger(name: str, log_file: str = None, level=logging.INFO) -> logging.Logger:
    """Configure logger with file and console handlers"""
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        try:
            log_path = Path('logs')
            log_path.mkdir(exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_path / log_file,
                maxBytes=10*1024*1024,
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            # Fallback to console only if file logging fails
            console_handler.warning(f"Failed to setup file logging: {e}, using console only")
    
    return logger


class RequestLogger:
    """Log API requests and responses"""
    
    @staticmethod
    def log_request(logger: logging.Logger, request):
        """Log incoming request"""
        logger.info(f"Request: {request.method} {request.path} | IP: {request.remote_addr}")
    
    @staticmethod
    def log_response(logger: logging.Logger, response, duration_ms: float):
        """Log response with timing"""
        logger.info(f"Response: {response.status_code} | Duration: {duration_ms:.2f}ms")