# src/utils/sql_security.py - SQL injection protection utilities
import re
import logging
from typing import Any, Dict, List, Union
from sqlalchemy.sql import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SQLInjectionDetector:
    """SQL injection detection and prevention"""
    
    # 常见SQL注入模式
    INJECTION_PATTERNS = [
        r"(['\";])",                           # quotes and statement separators
        r"(--|\#|/\*|\*/)",                    # comments
        r"(\bor\b\s+\b\d+\s*=\s*\d+)",    # tautology
        r"(\bunion\b\s+\bselect\b)",         # UNION SELECT
        r"(\b(exec|execute|sp_executesql)\b)",  # execution functions
        r"(\binto\b\s+\boutfile\b)",
        r"(\bload_file\b|\binto\b\s+\bdumpfile\b)",
        r"(\bsleep\b\s*\(\s*\d+\s*\))",
        r"(\bbenchmark\b\s*\()",
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]
    
    def detect_injection(self, input_string: str) -> Dict[str, Any]:
        """检测SQL注入尝试"""
        
        if not input_string:
            return {'is_malicious': False, 'patterns': []}
        
        detected_patterns = []
        
        for pattern in self.compiled_patterns:
            matches = pattern.findall(input_string)
            if matches:
                detected_patterns.extend(matches)
        
        is_malicious = len(detected_patterns) > 0
        
        if is_malicious:
            logger.warning(f"SQL injection attempt detected: {input_string[:100]}")
            logger.warning(f"Detected patterns: {detected_patterns}")
        
        return {
            'is_malicious': is_malicious,
            'patterns': detected_patterns,
            'input': input_string[:100] + "..." if len(input_string) > 100 else input_string
        }
    
    def sanitize_input(self, input_string: str) -> str:
        """基础输入清理"""
        
        if not input_string:
            return ""
        
        # 移除危险字符
        sanitized = input_string.replace("'", "").replace('"', '').replace(";", "")
        sanitized = re.sub(r'--.*$', '', sanitized)  # 移除SQL注释
        sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)  # 移除块注释
        
        return sanitized.strip()


class SafeQueryBuilder:
    """安全的查询构建器"""
    
    def __init__(self, session: Session):
        self.session = session
        self.detector = SQLInjectionDetector()
    
    def safe_filter_by_code(self, model_class, stock_code: str):
        """安全的股票代码过滤"""
        
        # 检测注入
        detection_result = self.detector.detect_injection(stock_code)
        if detection_result['is_malicious']:
            raise ValueError(f"Malicious input detected: {detection_result}")
        
        # 验证股票代码格式
        if not self._validate_stock_code(stock_code):
            raise ValueError(f"Invalid stock code format: {stock_code}")
        
        # 使用参数化查询
        return self.session.query(model_class).filter(model_class.code == stock_code)
    
    def safe_text_query(self, query_template: str, **params):
        """安全的原生SQL查询"""
        
        # 检查查询模板中是否有危险模式
        detection_result = self.detector.detect_injection(query_template)
        if detection_result['is_malicious']:
            raise ValueError(f"Malicious query template: {detection_result}")
        
        # 检查所有参数
        for key, value in params.items():
            if isinstance(value, str):
                param_detection = self.detector.detect_injection(value)
                if param_detection['is_malicious']:
                    raise ValueError(f"Malicious parameter {key}: {param_detection}")
        
        # 使用SQLAlchemy的text()和参数化查询
        return self.session.execute(text(query_template), params)
    
    def _validate_stock_code(self, stock_code: str) -> bool:
        """验证股票代码格式"""
        
        # 中国股票代码格式: 6位数字.交易所
        pattern = r'^[0-9]{6}\.(SH|SZ|HK)$'
        return re.match(pattern, stock_code) is not None


class SQLSecurityMiddleware:
    """SQL安全中间件"""
    
    def __init__(self):
        self.detector = SQLInjectionDetector()
        self.blocked_ips = set()
        self.suspicious_attempts = {}  # IP -> count
    
    def check_request_params(self, request_args: Dict[str, Any], client_ip: str = None) -> bool:
        """检查请求参数是否包含SQL注入"""
        
        suspicious_count = 0
        
        for key, value in request_args.items():
            if isinstance(value, str):
                detection_result = self.detector.detect_injection(value)
                if detection_result['is_malicious']:
                    suspicious_count += 1
                    
                    if client_ip:
                        self._track_suspicious_activity(client_ip)
                    
                    logger.warning(f"SQL injection attempt in parameter {key}: {value[:50]}")
        
        return suspicious_count == 0
    
    def _track_suspicious_activity(self, client_ip: str):
        """跟踪可疑活动"""
        
        self.suspicious_attempts[client_ip] = self.suspicious_attempts.get(client_ip, 0) + 1
        
        # 如果某个IP多次尝试注入，则加入黑名单
        if self.suspicious_attempts[client_ip] >= 5:
            self.blocked_ips.add(client_ip)
            logger.error(f"IP {client_ip} blocked due to repeated SQL injection attempts")
    
    def is_ip_blocked(self, client_ip: str) -> bool:
        """检查IP是否被阻止"""
        return client_ip in self.blocked_ips


def validate_query_safety(query: str) -> bool:
    """验证查询安全性的便捷函数"""
    
    detector = SQLInjectionDetector()
    result = detector.detect_injection(query)
    return not result['is_malicious']


def sanitize_user_input(user_input: str) -> str:
    """清理用户输入的便捷函数"""
    
    detector = SQLInjectionDetector()
    return detector.sanitize_input(user_input)


# 全局安全中间件实例
sql_security_middleware = SQLSecurityMiddleware()


# 装饰器用于保护API端点
def sql_injection_protection(func):
    """SQL注入保护装饰器"""
    
    def wrapper(*args, **kwargs):
        from flask import request, jsonify
        
        # 获取客户端IP
        
        try:
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
        except Exception:
            client_ip = None

        
        # 检查IP是否被阻止
        if sql_security_middleware.is_ip_blocked(client_ip):
            logger.warning(f"Blocked IP {client_ip} attempted to access {request.endpoint}")
            return jsonify({'error': 'Access denied'}), 403
        
        # 检查请求参数
        # 检查请求参数
        try:
            args_dict = request.args.to_dict()
        except Exception:
            args_dict = {}
        if not sql_security_middleware.check_request_params(args_dict, client_ip or ''):
            logger.warning(f"SQL injection attempt blocked from {client_ip}")
            return jsonify({'error': 'Invalid request parameters'}), 400
        
        return func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    return wrapper
