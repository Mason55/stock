#!/usr/bin/env python3
# scripts/verify_improvements.py - Verify all improvements are working
"""
Quick verification script for 2025 improvements.
Run this after deploying the improvements to verify everything works.
"""
import asyncio
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def verify_indicators_model():
    """Verify indicators model can be imported"""
    print("\n📊 Testing: Indicators Model")
    try:
        from src.models.indicators import TechnicalIndicators, IndicatorSignals
        print("✅ Indicators model imported successfully")
        print(f"   - TechnicalIndicators: {TechnicalIndicators.__tablename__}")
        print(f"   - IndicatorSignals: {IndicatorSignals.__tablename__}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def verify_indicators_calculator():
    """Verify indicators calculator"""
    print("\n🧮 Testing: Indicators Calculator")
    try:
        from src.services.indicators_calculator import IndicatorsCalculator
        import pandas as pd
        import numpy as np

        # Create test data
        dates = pd.date_range("2025-01-01", periods=30)
        prices = np.random.randn(30).cumsum() + 100
        df = pd.DataFrame(
            {
                "date": dates,
                "open": prices,
                "high": prices + np.random.rand(30),
                "low": prices - np.random.rand(30),
                "close": prices,
                "volume": np.random.randint(1000000, 10000000, 30),
            }
        )

        calc = IndicatorsCalculator(None)
        indicators = calc.calculate_all_indicators(df)

        print("✅ Calculator working")
        print(f"   - Calculated indicators: {len(indicators.columns)}")
        print(f"   - Sample MA20: {indicators['ma_20'].iloc[-1]:.2f}")
        print(f"   - Sample RSI: {indicators['rsi_12'].iloc[-1]:.2f}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def verify_etl_tasks():
    """Verify ETL tasks module"""
    print("\n🔄 Testing: ETL Tasks")
    try:
        from src.services.etl_tasks import ETLTasks, CacheWarmer

        print("✅ ETL tasks module loaded")
        print(f"   - ETLTasks: {ETLTasks.__name__}")
        print(f"   - CacheWarmer: {CacheWarmer.__name__}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def verify_strategies():
    """Verify new strategies"""
    print("\n🎯 Testing: Strategy Library")
    try:
        from src.strategies import STRATEGY_REGISTRY

        expected_strategies = [
            "moving_average",
            "mean_reversion",
            "momentum",
            "bollinger_breakout",
            "rsi_reversal",
            "boll_rsi_combo",
            "grid_trading",
        ]

        print(f"✅ Strategy registry loaded: {len(STRATEGY_REGISTRY)} strategies")
        for name in expected_strategies:
            if name in STRATEGY_REGISTRY:
                print(f"   ✓ {name}")
            else:
                print(f"   ✗ {name} (missing)")
                return False

        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def verify_enhanced_metrics():
    """Verify enhanced metrics"""
    print("\n📈 Testing: Enhanced Metrics")
    try:
        from src.monitoring.enhanced_metrics import (
            EnhancedMetricsCollector,
            metrics_collector,
            track_analysis,
        )

        print("✅ Metrics collector loaded")
        print(f"   - Collector: {type(metrics_collector).__name__}")

        # Test recording metrics
        metrics_collector.record_http_request("GET", "/test", 200, 0.1)
        metrics_collector.record_stock_analysis("technical", 0.5, True)
        print("   ✓ Metric recording works")

        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def verify_batch_optimizer():
    """Verify batch optimizer"""
    print("\n⚡ Testing: Batch Query Optimizer")
    try:
        from src.services.batch_optimizer import BatchQueryOptimizer, QueryOptimizationMixin

        print("✅ Batch optimizer loaded")
        print(f"   - BatchQueryOptimizer: {BatchQueryOptimizer.__name__}")
        print(f"   - QueryOptimizationMixin: {QueryOptimizationMixin.__name__}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def verify_indicators_api():
    """Verify indicators API"""
    print("\n🌐 Testing: Indicators API")
    try:
        from src.api.indicators_api import indicators_bp

        print("✅ Indicators API loaded")
        print(f"   - Blueprint: {indicators_bp.name}")
        print(f"   - URL prefix: {indicators_bp.url_prefix}")

        # Check endpoints (Blueprint doesn't have url_map until registered)
        print(f"   ✓ Blueprint ready for registration")

        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all verification tests"""
    print("=" * 60)
    print("🔍 System Improvements Verification")
    print("=" * 60)

    tests = [
        verify_indicators_model,
        verify_indicators_calculator,
        verify_etl_tasks,
        verify_strategies,
        verify_enhanced_metrics,
        verify_batch_optimizer,
        verify_indicators_api,
    ]

    results = []
    for test in tests:
        result = await test()
        results.append(result)
        time.sleep(0.5)

    print("\n" + "=" * 60)
    print("📊 Verification Summary")
    print("=" * 60)

    passed = sum(results)
    total = len(results)
    success_rate = passed / total * 100

    print(f"\nTests Passed: {passed}/{total} ({success_rate:.1f}%)")

    if passed == total:
        print("\n🎉 All improvements verified successfully!")
        print("✅ System is ready for deployment")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        print("❌ Fix the issues before deployment")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)