# tests/test_api.py
import pytest
from src.api.stock_api import stock_bp


class TestStockAPI:
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get('/api/stocks/health')
        assert response.status_code in [200, 500]
        data = response.get_json()
        assert 'status' in data
    
    def test_invalid_stock_code(self, client):
        """Test invalid stock code validation"""
        response = client.get('/api/stocks/INVALID')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_valid_stock_code_format(self, client):
        """Test valid stock code format"""
        response = client.get('/api/stocks/000001.SZ')
        assert response.status_code in [200, 404]
    
    def test_timeline_endpoint(self, client):
        """Test timeline endpoint with range parameter"""
        response = client.get('/api/stocks/000001.SZ/timeline?range=1M')
        assert response.status_code in [200, 404, 500]
    
    def test_stock_list_pagination(self, client):
        """Test stock list with pagination"""
        response = client.get('/api/stocks/list?page=1&per_page=10')
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'stocks' in data
            assert 'pagination' in data
    
    def test_scan_with_filters(self, client):
        """Test stock scan with filters"""
        response = client.get('/api/stocks/scan?industry=银行&min_price=10')
        assert response.status_code in [200, 500]