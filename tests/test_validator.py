# tests/test_validator.py
import pytest
from src.middleware.validator import InputValidator


class TestInputValidator:
    
    def test_valid_stock_codes(self):
        """Test valid stock code formats"""
        # A-share stocks
        assert InputValidator.validate_stock_code('000001.SZ') == True
        assert InputValidator.validate_stock_code('600000.SH') == True
        assert InputValidator.validate_stock_code('300001.sz') == True
        
        # Hong Kong stocks
        assert InputValidator.validate_stock_code('700.HK') == True
        assert InputValidator.validate_stock_code('9988.hk') == True
        assert InputValidator.validate_stock_code('1810.HK') == True
        assert InputValidator.validate_stock_code('3.HK') == True
    
    def test_invalid_stock_codes(self):
        """Test invalid stock code formats"""
        assert InputValidator.validate_stock_code('000001') == False
        assert InputValidator.validate_stock_code('AAPL') == False
        assert InputValidator.validate_stock_code('') == False
        assert InputValidator.validate_stock_code(None) == False
        assert InputValidator.validate_stock_code('000001.XX') == False
    
    def test_sanitize_string(self):
        """Test string sanitization"""
        assert InputValidator.sanitize_string('银行') == '银行'
        assert InputValidator.sanitize_string('  test  ') == 'test'
        assert InputValidator.sanitize_string('<script>alert(1)</script>') == 'scriptalert1script'
        assert InputValidator.sanitize_string("'; DROP TABLE--") == ' DROP TABLE--'
    
    def test_validate_pagination(self):
        """Test pagination validation"""
        page, per_page = InputValidator.validate_pagination(1, 20)
        assert page == 1 and per_page == 20
        
        page, per_page = InputValidator.validate_pagination(0, 200)
        assert page == 1 and per_page == 100
        
        page, per_page = InputValidator.validate_pagination(None, None)
        assert page == 1 and per_page == 20
    
    def test_validate_numeric_range(self):
        """Test numeric range validation"""
        assert InputValidator.validate_numeric_range(50, 0, 100) == 50
        assert InputValidator.validate_numeric_range(-10, 0, 100) == 0
        assert InputValidator.validate_numeric_range(150, 0, 100) == 100
        assert InputValidator.validate_numeric_range(None) == None
    
    def test_validate_time_range(self):
        """Test time range validation"""
        assert InputValidator.validate_time_range('1M') == '1M'
        assert InputValidator.validate_time_range('1Y') == '1Y'
        assert InputValidator.validate_time_range('INVALID') == '1M'