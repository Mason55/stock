# src/middleware/validator.py
import re
from typing import Optional
from functools import wraps
from flask import request, jsonify
from src.utils.exceptions import ValidationError


class InputValidator:
    
    # A-share pattern: 6-digit code + .SH/.SZ
    A_SHARE_PATTERN = re.compile(r'^[0-9]{6}\.(SH|SZ)$')
    # Hong Kong pattern: 1-5 digit code + .HK
    HK_PATTERN = re.compile(r'^[0-9]{1,5}\.HK$')
    
    @staticmethod
    def validate_stock_code(code: str) -> bool:
        """Validate stock code format (A-share and HK)"""
        if not code or not isinstance(code, str):
            return False
        
        code_upper = code.upper()
        return (InputValidator.A_SHARE_PATTERN.match(code_upper) is not None or
                InputValidator.HK_PATTERN.match(code_upper) is not None)
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 100) -> str:
        """Sanitize string input to prevent injection"""
        if not isinstance(value, str):
            return ""
        
        value = value.strip()[:max_length]
        value = re.sub(r'[<>"\'%;()&+/]', '', value)
        return value
    
    @staticmethod
    def validate_pagination(page: Optional[int], per_page: Optional[int]) -> tuple[int, int]:
        """Validate and normalize pagination parameters"""
        try:
            page = max(1, int(page) if page else 1)
            per_page = max(1, min(100, int(per_page) if per_page else 20))
            return page, per_page
        except (ValueError, TypeError):
            return 1, 20
    
    @staticmethod
    def validate_numeric_range(value: Optional[float], min_val: float = None, max_val: float = None) -> Optional[float]:
        """Validate numeric value within range"""
        if value is None:
            return None
        
        try:
            num = float(value)
            if min_val is not None and num < min_val:
                return min_val
            if max_val is not None and num > max_val:
                return max_val
            return num
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def validate_time_range(range_param: str) -> str:
        """Validate time range parameter"""
        valid_ranges = ['1D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '3Y', '5Y']
        return range_param if range_param in valid_ranges else '1M'


class StockValidator:
    """Adapter for legacy tests expecting StockValidator interface"""
    def is_valid_stock_code(self, code: str) -> bool:
        return InputValidator.validate_stock_code(code)

    def validate_stock_code(self, code: str) -> None:
        if not self.is_valid_stock_code(code):
            raise ValidationError("Invalid stock code format; expected XXXXXX.SH/SZ or XXXX.HK")


def require_stock_code(f):
    """Decorator to validate stock code parameter"""
    @wraps(f)
    def wrapped(stock_code, *args, **kwargs):
        if not InputValidator.validate_stock_code(stock_code):
            # 统一走全局错误处理，便于携带 request_id 与一致的错误结构
            raise ValidationError('Invalid stock code format: expected XXXXXX.SH or XXXXXX.SZ')
        
        return f(stock_code.upper(), *args, **kwargs)
    return wrapped


def validate_request_params(schema: dict):
    """Decorator to validate request parameters against schema"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            errors = []
            
            for param, rules in schema.items():
                value = request.args.get(param)
                
                if rules.get('required') and not value:
                    errors.append(f"Missing required parameter: {param}")
                    continue
                
                if value and rules.get('type') == 'int':
                    try:
                        int(value)
                    except ValueError:
                        errors.append(f"Parameter {param} must be an integer")
                
                if value and rules.get('type') == 'float':
                    try:
                        float(value)
                    except ValueError:
                        errors.append(f"Parameter {param} must be a number")
                
                if value and 'choices' in rules and value not in rules['choices']:
                    errors.append(f"Parameter {param} must be one of: {', '.join(rules['choices'])}")
            
            if errors:
                return jsonify({'error': 'Validation failed', 'details': errors}), 400
            
            return f(*args, **kwargs)
        return wrapped
    return decorator
