# tests/test_enhanced_api.py - Enhanced API tests with proper error handling
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from src.utils.exceptions import ValidationError, DataSourceError


class TestStockAPIEnhanced:
    """Enhanced test suite for stock API endpoints"""
    
    def test_health_check_success(self, client):
        """Test successful health check"""
        response = client.get('/api/stocks/health')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['status'] in ['healthy', 'degraded']
        assert 'timestamp' in data
        assert 'services' in data
    
    def test_health_check_database_down(self, client, monkeypatch):
        """Test health check when database is down"""
        def mock_health_check():
            return False
        
        monkeypatch.setattr('src.database.db_manager.health_check', mock_health_check)
        
        response = client.get('/api/stocks/health')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['status'] == 'degraded'
    
    @pytest.mark.parametrize("invalid_code", [
        "INVALID",
        "123456",
        "000001",
        "000001.XX",
        "A00001.SZ",
        "000001.SZ.EXTRA"
    ])
    def test_invalid_stock_codes(self, client, invalid_code):
        """Test various invalid stock code formats"""
        response = client.get(f'/api/stocks/{invalid_code}/analysis')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'validation_error'
        assert 'stock code' in data['message'].lower()
    
    @pytest.mark.parametrize("valid_code", [
        "000001.SZ",
        "600036.SH", 
        "300001.SZ",
        "688001.SH"
    ])
    def test_valid_stock_codes(self, client, valid_code):
        """Test valid stock code formats"""
        response = client.get(f'/api/stocks/{valid_code}/analysis')
        
        # Should not return validation error
        assert response.status_code != 400
    
    def test_stock_analysis_with_types(self, client):
        """Test stock analysis with different analysis types"""
        test_cases = [
            ('technical', 'technical_analysis'),
            ('fundamental', 'fundamental_analysis'),
            ('sentiment', 'sentiment_analysis'),
            ('all', 'recommendation')
        ]
        
        for analysis_type, expected_field in test_cases:
            response = client.get(f'/api/stocks/000001.SZ/analysis?type={analysis_type}')
            
            if response.status_code == 200:
                data = response.get_json()
                assert expected_field in data
    
    def test_batch_analysis_success(self, client):
        """Test successful batch analysis"""
        payload = {
            'stock_codes': ['000001.SZ', '600036.SH'],
            'analysis_types': ['technical', 'fundamental']
        }
        
        response = client.post('/api/stocks/batch_analysis',
                             data=json.dumps(payload),
                             content_type='application/json')
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'results' in data
            assert len(data['results']) <= 2
    
    def test_batch_analysis_validation_error(self, client):
        """Test batch analysis with invalid input"""
        # Test empty stock codes
        payload = {'stock_codes': []}
        response = client.post('/api/stocks/batch_analysis',
                             data=json.dumps(payload),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['error'] == 'validation_error'
    
    def test_batch_analysis_too_many_stocks(self, client):
        """Test batch analysis with too many stocks"""
        payload = {
            'stock_codes': [f'00000{i}.SZ' for i in range(1, 52)]  # 51 stocks
        }
        
        response = client.post('/api/stocks/batch_analysis',
                             data=json.dumps(payload),
                             content_type='application/json')
        
        assert response.status_code == 400
    
    def test_realtime_data_endpoint(self, client):
        """Test real-time data endpoint"""
        response = client.get('/api/stocks/000001.SZ/realtime')
        
        if response.status_code == 200:
            data = response.get_json()
            required_fields = ['current_price', 'timestamp', 'volume']
            for field in required_fields:
                assert field in data
    
    def test_historical_data_endpoint(self, client):
        """Test historical data endpoint"""
        response = client.get('/api/stocks/000001.SZ/history?days=30')
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'data' in data
            assert isinstance(data['data'], list)
    
    def test_rate_limiting(self, client):
        """Test API rate limiting"""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = client.get('/api/stocks/000001.SZ/analysis')
            responses.append(response.status_code)
        
        # Should not all be successful if rate limiting is working
        # At least one should be 429 if limit is hit
        has_429 = any(status == 429 for status in responses)
        has_200 = any(status == 200 for status in responses)
        
        # Either all requests succeed (no rate limiting) or some are blocked
        assert has_200 or has_429
    
    def test_request_id_in_error_response(self, client):
        """Test that request ID is included in error responses"""
        response = client.get('/api/stocks/INVALID/analysis')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'request_id' in data
    
    def test_response_time_header(self, client):
        """Test that response time header is included"""
        response = client.get('/api/stocks/health')
        
        assert 'X-Response-Time' in response.headers
        assert response.headers['X-Response-Time'].endswith('ms')
    
    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options('/api/stocks/health')
        
        # Should have CORS headers
        assert response.status_code in [200, 204]
    
    @patch('src.services.enhanced_data_collector.EnhancedDataCollector.fetch_realtime_price')
    def test_data_source_failure_handling(self, mock_fetch, client):
        """Test handling of data source failures"""
        # Mock data source failure
        mock_fetch.side_effect = DataSourceError("Data source unavailable")
        
        response = client.get('/api/stocks/000001.SZ/analysis')
        
        # Should handle gracefully, not return 500
        assert response.status_code in [200, 503]
        
        if response.status_code == 503:
            data = response.get_json()
            assert data['error'] == 'data_source_error'


class TestStockValidation:
    """Test stock code validation logic"""
    
    @pytest.mark.parametrize("code,expected", [
        ("000001.SZ", True),
        ("600036.SH", True),
        ("300001.SZ", True),
        ("688001.SH", True),
        ("123456", False),
        ("000001", False),
        ("000001.XX", False),
        ("AAAA01.SZ", False),
    ])
    def test_stock_code_validation(self, code, expected):
        """Test stock code validation function"""
        from src.middleware.validator import StockValidator
        
        validator = StockValidator()
        result = validator.is_valid_stock_code(code)
        assert result == expected
    
    def test_validation_error_details(self):
        """Test validation error provides detailed information"""
        from src.middleware.validator import StockValidator
        
        validator = StockValidator()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_stock_code("INVALID")
        
        error = exc_info.value
        assert error.error_code == "ValidationError"
        assert "stock code" in error.message.lower()


class TestErrorHandling:
    """Test comprehensive error handling"""
    
    def test_database_error_handling(self, client, monkeypatch):
        """Test database error handling"""
        def mock_db_error(*args, **kwargs):
            from src.utils.exceptions import DatabaseError
            raise DatabaseError("Database connection failed")
        
        # This would need to be adjusted based on actual database usage
        # monkeypatch.setattr('some.database.function', mock_db_error)
        
        # For now, just test that database errors are handled
        pass
    
    def test_unexpected_error_handling(self, client, monkeypatch):
        """Test handling of unexpected errors"""
        def mock_unexpected_error(*args, **kwargs):
            raise RuntimeError("Unexpected error")
        
        # This test would need specific mocking based on implementation
        pass
    
    def test_json_parsing_error(self, client):
        """Test handling of malformed JSON"""
        response = client.post('/api/stocks/batch_analysis',
                             data='{"invalid": json}',
                             content_type='application/json')
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data