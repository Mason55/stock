# src/middleware/enhanced_validator.py - Enhanced input validation with security features
import re
import json
import logging
from typing import Optional, Any, Dict, List, Union
from functools import wraps
from flask import request, jsonify
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """自定义验证错误"""
    
    def __init__(self, message: str, field: str = None, code: str = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


class EnhancedInputValidator:
    """增强的输入验证器，包含安全特性"""
    
    # 股票代码模式
    STOCK_CODE_PATTERNS = {
        'A_SHARE': re.compile(r'^[0-9]{6}\.(SH|SZ)$'),
        'HK_SHARE': re.compile(r'^[0-9]{1,5}\.HK$'),
        'US_SHARE': re.compile(r'^[A-Z]{1,5}$'),  # 简化的美股模式
        'ALL': re.compile(r'^([0-9]{6}\.(SH|SZ)|[0-9]{1,5}\.HK|[A-Z]{1,5})$')
    }
    
    # 危险字符模式
    DANGEROUS_PATTERNS = [
        re.compile(r'[<>"\'\%;()&+]'),  # XSS和注入字符
        re.compile(r'\b(script|javascript|vbscript)\b', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),  # 事件处理器
        re.compile(r'(union|select|insert|update|delete|drop|exec)\b', re.IGNORECASE),
        re.compile(r'(eval|function|setTimeout|setInterval)\s*\(', re.IGNORECASE)
    ]
    
    # 有效的时间范围
    VALID_TIME_RANGES = ['1D', '5D', '1W', '1M', '3M', '6M', 'YTD', '1Y', '2Y', '5Y', 'MAX']
    
    # 有效的行业列表
    VALID_INDUSTRIES = [
        'Technology', 'Finance', 'Healthcare', 'Energy', 'Materials', 
        'Industrials', 'Consumer Discretionary', 'Consumer Staples',
        'Real Estate', 'Telecommunications', 'Utilities'
    ]
    
    @classmethod
    def validate_stock_code(cls, code: str, market: str = 'ALL') -> Dict[str, Any]:
        """增强的股票代码验证"""
        
        result = {
            'is_valid': False,
            'normalized_code': None,
            'market_type': None,
            'errors': []
        }
        
        if not code or not isinstance(code, str):
            result['errors'].append('Stock code cannot be empty')
            return result
        
        # 基础清理
        code = code.strip().upper()
        
        # 长度检查
        if len(code) > 20:
            result['errors'].append('Stock code too long')
            return result
        
        # 危险字符检查
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(code):
                result['errors'].append('Stock code contains invalid characters')
                logger.warning(f"Suspicious stock code input: {code}")
                return result
        
        # 格式验证
        pattern = cls.STOCK_CODE_PATTERNS.get(market, cls.STOCK_CODE_PATTERNS['ALL'])
        
        if pattern.match(code):
            result['is_valid'] = True
            result['normalized_code'] = code
            
            # 确定市场类型
            if cls.STOCK_CODE_PATTERNS['A_SHARE'].match(code):
                result['market_type'] = 'A_SHARE'
            elif cls.STOCK_CODE_PATTERNS['HK_SHARE'].match(code):
                result['market_type'] = 'HK_SHARE'
            elif cls.STOCK_CODE_PATTERNS['US_SHARE'].match(code):
                result['market_type'] = 'US_SHARE'
        else:
            result['errors'].append(f'Invalid stock code format for market: {market}')
        
        return result
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 100, 
                       allow_special_chars: bool = False) -> str:
        """增强的字符串清理"""
        
        if not isinstance(value, str):
            return ""
        
        # 基础清理
        value = value.strip()[:max_length]
        
        # 移除危险字符
        if not allow_special_chars:
            for pattern in cls.DANGEROUS_PATTERNS:
                value = pattern.sub('', value)
        
        # 移除控制字符
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')
        
        return value
    
    @classmethod
    def validate_numeric_value(cls, value: Any, min_val: float = None, 
                              max_val: float = None, decimal_places: int = None) -> Dict[str, Any]:
        """增强的数值验证"""
        
        result = {
            'is_valid': False,
            'value': None,
            'errors': []
        }
        
        if value is None or value == '':
            result['is_valid'] = True  # None值是允许的
            return result
        
        try:
            # 转换为Decimal以避免浮点精度问题
            if isinstance(value, str):
                # 移除空格和货币符号
                cleaned_value = re.sub(r'[^\d.-]', '', value)
                num = Decimal(cleaned_value)
            else:
                num = Decimal(str(value))
            
            # 范围检查
            if min_val is not None and num < Decimal(str(min_val)):
                result['errors'].append(f'Value must be >= {min_val}')
                return result
            
            if max_val is not None and num > Decimal(str(max_val)):
                result['errors'].append(f'Value must be <= {max_val}')
                return result
            
            # 小数位检查
            if decimal_places is not None:
                if num.as_tuple().exponent < -decimal_places:
                    result['errors'].append(f'Maximum {decimal_places} decimal places allowed')
                    return result
            
            result['is_valid'] = True
            result['value'] = float(num)
            
        except (InvalidOperation, ValueError, TypeError) as e:
            result['errors'].append(f'Invalid numeric value: {str(e)}')
        
        return result
    
    @classmethod
    def validate_date_range(cls, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """验证日期范围"""
        
        result = {
            'is_valid': False,
            'start_date': None,
            'end_date': None,
            'errors': []
        }
        
        try:
            # 解析开始日期
            if start_date:
                result['start_date'] = datetime.strptime(start_date, '%Y-%m-%d').date()
            
            # 解析结束日期
            if end_date:
                result['end_date'] = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # 逻辑检查
            if result['start_date'] and result['end_date']:
                if result['start_date'] > result['end_date']:
                    result['errors'].append('Start date must be before end date')
                    return result
                
                # 检查日期范围是否合理（不超过10年）
                date_diff = result['end_date'] - result['start_date']
                if date_diff.days > 3650:  # 10年
                    result['errors'].append('Date range cannot exceed 10 years')
                    return result
            
            # 检查日期是否过于遥远的将来
            today = date.today()
            if result['end_date'] and result['end_date'] > today:
                result['end_date'] = today
            
            result['is_valid'] = True
            
        except ValueError as e:
            result['errors'].append(f'Invalid date format. Use YYYY-MM-DD: {str(e)}')
        
        return result
    
    @classmethod
    def validate_pagination(cls, page: Any = None, per_page: Any = None, 
                           max_per_page: int = 100) -> Dict[str, Any]:
        """增强的分页验证"""
        
        result = {
            'is_valid': False,
            'page': 1,
            'per_page': 20,
            'errors': []
        }
        
        try:
            # 验证页码
            if page is not None:
                page_num = int(page)
                if page_num < 1:
                    result['errors'].append('Page must be >= 1')
                elif page_num > 10000:  # 防止过大的页码
                    result['errors'].append('Page number too large')
                else:
                    result['page'] = page_num
            
            # 验证每页条目数
            if per_page is not None:
                per_page_num = int(per_page)
                if per_page_num < 1:
                    result['errors'].append('Per page must be >= 1')
                elif per_page_num > max_per_page:
                    result['errors'].append(f'Per page cannot exceed {max_per_page}')
                else:
                    result['per_page'] = per_page_num
            
            if not result['errors']:
                result['is_valid'] = True
                
        except (ValueError, TypeError):
            result['errors'].append('Page and per_page must be integers')
        
        return result
    
    @classmethod
    def validate_industry(cls, industry: str) -> Dict[str, Any]:
        """验证行业参数"""
        
        result = {
            'is_valid': False,
            'normalized_industry': None,
            'errors': []
        }
        
        if not industry:
            result['is_valid'] = True  # 空值是允许的
            return result
        
        # 清理输入
        cleaned_industry = cls.sanitize_string(industry, 50)
        
        # 模糊匹配行业名称
        industry_lower = cleaned_industry.lower()
        for valid_industry in cls.VALID_INDUSTRIES:
            if industry_lower in valid_industry.lower() or valid_industry.lower() in industry_lower:
                result['is_valid'] = True
                result['normalized_industry'] = valid_industry
                break
        
        if not result['is_valid']:
            result['errors'].append(f'Invalid industry. Valid options: {", ".join(cls.VALID_INDUSTRIES)}')
        
        return result


class RequestValidator:
    """请求验证器"""
    
    def __init__(self):
        self.validator = EnhancedInputValidator()
    
    def validate_stock_query_params(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """验证股票查询参数"""
        
        result = {
            'is_valid': True,
            'cleaned_params': {},
            'errors': []
        }
        
        # 验证股票代码
        if 'stock_code' in args:
            code_result = self.validator.validate_stock_code(args['stock_code'])
            if not code_result['is_valid']:
                result['is_valid'] = False
                result['errors'].extend(code_result['errors'])
            else:
                result['cleaned_params']['stock_code'] = code_result['normalized_code']
        
        # 验证价格范围
        for price_param in ['min_price', 'max_price']:
            if price_param in args:
                price_result = self.validator.validate_numeric_value(
                    args[price_param], min_val=0, max_val=10000, decimal_places=2
                )
                if not price_result['is_valid']:
                    result['is_valid'] = False
                    result['errors'].extend([f"{price_param}: {err}" for err in price_result['errors']])
                else:
                    result['cleaned_params'][price_param] = price_result['value']
        
        # 验证成交量
        if 'min_volume' in args:
            volume_result = self.validator.validate_numeric_value(
                args['min_volume'], min_val=0, decimal_places=0
            )
            if not volume_result['is_valid']:
                result['is_valid'] = False
                result['errors'].extend([f"min_volume: {err}" for err in volume_result['errors']])
            else:
                result['cleaned_params']['min_volume'] = int(volume_result['value'] or 0)
        
        # 验证行业
        if 'industry' in args:
            industry_result = self.validator.validate_industry(args['industry'])
            if not industry_result['is_valid']:
                result['is_valid'] = False
                result['errors'].extend(industry_result['errors'])
            else:
                result['cleaned_params']['industry'] = industry_result['normalized_industry']
        
        # 验证分页
        if 'page' in args or 'per_page' in args:
            pagination_result = self.validator.validate_pagination(
                args.get('page'), args.get('per_page')
            )
            if not pagination_result['is_valid']:
                result['is_valid'] = False
                result['errors'].extend(pagination_result['errors'])
            else:
                result['cleaned_params']['page'] = pagination_result['page']
                result['cleaned_params']['per_page'] = pagination_result['per_page']
        
        return result


# 装饰器
def enhanced_validation(validation_rules: Dict[str, Any] = None):
    """增强的验证装饰器"""
    
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            validator = RequestValidator()
            
            # 执行验证
            validation_result = validator.validate_stock_query_params(request.args.to_dict())
            
            if not validation_result['is_valid']:
                return jsonify({
                    'error': 'Validation failed',
                    'details': validation_result['errors']
                }), 400
            
            # 将清理后的参数添加到request对象
            request.validated_params = validation_result['cleaned_params']
            
            return f(*args, **kwargs)
        
        wrapped.__name__ = f.__name__
        return wrapped
    
    return decorator


def require_enhanced_stock_code(f):
    """增强的股票代码验证装饰器"""
    
    @wraps(f)
    def wrapped(stock_code, *args, **kwargs):
        validator = EnhancedInputValidator()
        
        # 验证股票代码
        validation_result = validator.validate_stock_code(stock_code)
        
        if not validation_result['is_valid']:
            return jsonify({
                'error': 'Invalid stock code',
                'details': validation_result['errors'],
                'valid_formats': [
                    '6-digit number + .SH/.SZ for A-shares (e.g., 600036.SH)',
                    '1-5 digit number + .HK for Hong Kong shares (e.g., 700.HK)',
                    '1-5 letter symbol for US shares (e.g., AAPL)'
                ]
            }), 400
        
        # 使用标准化的代码
        normalized_code = validation_result['normalized_code']
        
        return f(normalized_code, *args, **kwargs)
    
    return wrapped