"""Tests for ETF analyzer"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.etf_analyzer import ETFAnalyzer


@pytest.fixture
def etf_analyzer():
    """Create ETF analyzer for testing"""
    return ETFAnalyzer(use_cache=False)


def test_is_etf_by_code(etf_analyzer):
    """Test ETF identification by code"""
    # ETF codes
    assert etf_analyzer.is_etf('159920.SZ') == True
    assert etf_analyzer.is_etf('510050.SH') == True
    assert etf_analyzer.is_etf('512760.SH') == True

    # Non-ETF codes
    assert etf_analyzer.is_etf('600036.SH') == False
    assert etf_analyzer.is_etf('000977.SZ') == False


def test_is_etf_by_name(etf_analyzer):
    """Test ETF identification by name"""
    assert etf_analyzer.is_etf('159920.SZ', '恒生ETF') == True
    assert etf_analyzer.is_etf('510050.SH', '50ETF') == True
    assert etf_analyzer.is_etf('600036.SH', '招商银行') == False


def test_get_etf_info_cache(etf_analyzer):
    """Test ETF info caching"""
    analyzer = ETFAnalyzer(use_cache=True)

    # Clean up any existing cache
    analyzer.cache.delete("etf_info:159920.SZ")

    mock_info = {
        'etf_code': '159920.SZ',
        'etf_name': '恒生ETF',
        'fund_company': '华夏基金',
        'source': 'eastmoney'
    }

    # Mock the fetch method
    with patch.object(analyzer, '_fetch_etf_info_from_eastmoney', return_value=mock_info) as mock_fetch:
        with patch.object(analyzer, '_fetch_etf_info_from_jisilu', return_value=None):
            # First call - should fetch
            info1 = analyzer.get_etf_info('159920.SZ')
            assert info1 is not None
            assert info1['etf_name'] == '恒生ETF'
            assert mock_fetch.call_count == 1

            # Second call - should use cache
            info2 = analyzer.get_etf_info('159920.SZ')
            assert info2 == info1
            assert mock_fetch.call_count == 1  # Not called again

    # Clean up cache
    analyzer.cache.delete("etf_info:159920.SZ")


def test_premium_discount_calculation(etf_analyzer):
    """Test premium/discount calculation"""
    with patch('src.api.stock_api.fetch_sina_realtime_sync') as mock_quote:
        mock_quote.return_value = {
            'current_price': 1.62,
            'stock_code': '159920.SZ'
        }

        with patch.object(etf_analyzer, '_fetch_nav_from_eastmoney') as mock_nav:
            mock_nav.return_value = 1.61

            result = etf_analyzer.get_premium_discount('159920.SZ')

            assert result is not None
            assert result['market_price'] == 1.62
            assert result['nav'] == 1.61
            assert abs(result['premium_rate'] - 0.62) < 0.01  # (1.62-1.61)/1.61*100 ≈ 0.62
            assert result['status'] == 'premium'


def test_premium_discount_with_discount(etf_analyzer):
    """Test discount scenario"""
    with patch('src.api.stock_api.fetch_sina_realtime_sync') as mock_quote:
        mock_quote.return_value = {'current_price': 1.60}

        with patch.object(etf_analyzer, '_fetch_nav_from_eastmoney') as mock_nav:
            mock_nav.return_value = 1.62

            result = etf_analyzer.get_premium_discount('159920.SZ')

            assert result is not None
            assert result['premium_rate'] < 0
            assert result['status'] == 'discount'


def test_premium_discount_fair_value(etf_analyzer):
    """Test fair value scenario"""
    with patch('src.api.stock_api.fetch_sina_realtime_sync') as mock_quote:
        mock_quote.return_value = {'current_price': 1.61}

        with patch.object(etf_analyzer, '_fetch_nav_from_eastmoney') as mock_nav:
            mock_nav.return_value = 1.61

            result = etf_analyzer.get_premium_discount('159920.SZ')

            assert result is not None
            assert abs(result['premium_rate']) < 0.5
            assert result['status'] == 'fair'


def test_holdings_structure(etf_analyzer):
    """Test holdings data structure"""
    result = etf_analyzer.get_holdings('159920.SZ', top_n=10)

    assert result is not None
    assert 'etf_code' in result
    assert 'top_holdings' in result
    assert 'sector_distribution' in result
    assert isinstance(result['top_holdings'], list)
    assert isinstance(result['sector_distribution'], dict)


def test_fund_flow_calculation(etf_analyzer):
    """Test fund flow calculation"""
    import pandas as pd

    # Mock historical data
    mock_df = pd.DataFrame({
        'date': pd.date_range('2025-11-13', periods=5),
        'close': [1.60, 1.61, 1.62, 1.61, 1.60],
        'volume': [1000000, 1200000, 1500000, 1100000, 1300000]
    })

    with patch('src.api.stock_api.fetch_history_df') as mock_fetch:
        mock_fetch.return_value = mock_df

        result = etf_analyzer.get_fund_flow('159920.SZ', days=5)

        assert result is not None
        assert 'net_flow' in result
        assert 'daily_flow' in result
        assert 'trend' in result
        assert len(result['daily_flow']) == 5
        assert result['trend'] in ['inflow', 'outflow', 'neutral']


def test_error_handling_no_quote(etf_analyzer):
    """Test error handling when quote is unavailable"""
    with patch('src.api.stock_api.fetch_sina_realtime_sync') as mock_quote:
        mock_quote.return_value = None

        result = etf_analyzer.get_premium_discount('159920.SZ')
        assert result is None


def test_error_handling_no_nav(etf_analyzer):
    """Test handling when NAV is unavailable"""
    with patch('src.api.stock_api.fetch_sina_realtime_sync') as mock_quote:
        mock_quote.return_value = {'current_price': 1.62}

        with patch.object(etf_analyzer, '_fetch_nav_from_eastmoney') as mock_nav1:
            with patch.object(etf_analyzer, '_fetch_nav_from_jisilu') as mock_nav2:
                mock_nav1.return_value = None
                mock_nav2.return_value = None

                result = etf_analyzer.get_premium_discount('159920.SZ')

                assert result is not None
                assert result['nav'] is None
                assert result['premium_rate'] is None
                assert result['status'] == 'unknown'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
