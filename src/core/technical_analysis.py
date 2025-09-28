# src/core/technical_analysis.py - 深度技术分析模块
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class AdvancedTechnicalIndicators:
    """高级技术指标"""
    # 基础指标
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    
    # 趋势指标
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    
    # 震荡指标
    rsi: Optional[float] = None
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None
    
    # 布林带
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    bb_percent: Optional[float] = None
    
    # 威廉指标
    williams_r: Optional[float] = None
    
    # CCI商品通道指数
    cci: Optional[float] = None
    
    # DMI趋向指标
    dmi_pdi: Optional[float] = None  # +DI
    dmi_mdi: Optional[float] = None  # -DI
    dmi_adx: Optional[float] = None  # ADX
    
    # 成交量指标
    obv: Optional[float] = None  # 能量潮
    volume_ma: Optional[float] = None
    volume_ratio: Optional[float] = None
    
    # 支撑阻力
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Optional[float]]:
        """转换为字典"""
        return {k: v for k, v in self.__dict__.items()}


class AdvancedTechnicalAnalyzer:
    """高级技术分析器"""
    
    def __init__(self):
        self.default_periods = {
            'ma_short': 5,
            'ma_medium': 20,
            'ma_long': 60,
            'rsi': 14,
            'kdj': 9,
            'bb': 20,
            'williams': 14,
            'cci': 14,
            'dmi': 14
        }
    
    def calculate_comprehensive_indicators(self, 
                                        prices: List[float], 
                                        volumes: List[float] = None,
                                        highs: List[float] = None,
                                        lows: List[float] = None,
                                        current_price: float = None) -> AdvancedTechnicalIndicators:
        """计算综合技术指标"""
        if not prices:
            return AdvancedTechnicalIndicators()
        
        # 转换为numpy数组便于计算
        price_array = np.array(prices)
        current_price = current_price or prices[-1]
        
        # 如果没有提供高低价，使用收盘价代替
        if highs is None:
            highs = prices
        if lows is None:
            lows = prices
        if volumes is None:
            volumes = [1000000] * len(prices)  # 默认成交量
        
        high_array = np.array(highs)
        low_array = np.array(lows)
        volume_array = np.array(volumes)
        
        indicators = AdvancedTechnicalIndicators()
        
        try:
            # 1. 移动平均线
            indicators.ma5 = self._calculate_ma(price_array, 5)
            indicators.ma10 = self._calculate_ma(price_array, 10)
            indicators.ma20 = self._calculate_ma(price_array, 20)
            indicators.ma60 = self._calculate_ma(price_array, 60)
            
            # 2. MACD指标
            macd, signal, histogram = self._calculate_macd(price_array)
            indicators.macd = macd
            indicators.macd_signal = signal
            indicators.macd_histogram = histogram
            
            # 3. RSI指标
            indicators.rsi = self._calculate_rsi(price_array)
            
            # 4. KDJ指标
            k, d, j = self._calculate_kdj(high_array, low_array, price_array)
            indicators.kdj_k = k
            indicators.kdj_d = d
            indicators.kdj_j = j
            
            # 5. 布林带
            bb_upper, bb_middle, bb_lower, bb_width, bb_percent = self._calculate_bollinger_bands(
                price_array, current_price
            )
            indicators.bb_upper = bb_upper
            indicators.bb_middle = bb_middle
            indicators.bb_lower = bb_lower
            indicators.bb_width = bb_width
            indicators.bb_percent = bb_percent
            
            # 6. 威廉指标
            indicators.williams_r = self._calculate_williams_r(high_array, low_array, price_array)
            
            # 7. CCI指标
            indicators.cci = self._calculate_cci(high_array, low_array, price_array)
            
            # 8. DMI指标
            pdi, mdi, adx = self._calculate_dmi(high_array, low_array, price_array)
            indicators.dmi_pdi = pdi
            indicators.dmi_mdi = mdi
            indicators.dmi_adx = adx
            
            # 9. 成交量指标
            indicators.obv = self._calculate_obv(price_array, volume_array)
            indicators.volume_ma = self._calculate_ma(volume_array, 5)
            indicators.volume_ratio = volume_array[-1] / indicators.volume_ma if indicators.volume_ma else 1.0
            
            # 10. 支撑阻力位
            support, resistance = self._calculate_support_resistance(high_array, low_array, price_array)
            indicators.support_level = support
            indicators.resistance_level = resistance
            
        except Exception as e:
            print(f"计算技术指标时发生错误: {e}")
        
        return indicators
    
    def _calculate_ma(self, prices: np.ndarray, period: int) -> Optional[float]:
        """计算移动平均线"""
        if len(prices) < period:
            return None
        return float(np.mean(prices[-period:]))
    
    def _calculate_macd(self, prices: np.ndarray, fast=12, slow=26, signal=9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """计算MACD指标"""
        if len(prices) < slow:
            return None, None, None
        
        # 计算EMA
        ema_fast = self._calculate_ema(prices, fast)
        ema_slow = self._calculate_ema(prices, slow)
        
        if ema_fast is None or ema_slow is None:
            return None, None, None
        
        macd_line = ema_fast - ema_slow
        
        # 计算MACD信号线
        if len(prices) >= slow + signal:
            macd_values = []
            for i in range(slow-1, len(prices)):
                fast_ema = self._calculate_ema(prices[:i+1], fast)
                slow_ema = self._calculate_ema(prices[:i+1], slow)
                if fast_ema and slow_ema:
                    macd_values.append(fast_ema - slow_ema)
            
            if len(macd_values) >= signal:
                signal_line = np.mean(macd_values[-signal:])
                histogram = macd_line - signal_line
                return float(macd_line), float(signal_line), float(histogram)
        
        return float(macd_line), None, None
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> Optional[float]:
        """计算指数移动平均"""
        if len(prices) < period:
            return None
        
        alpha = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return float(ema)
    
    def _calculate_rsi(self, prices: np.ndarray, period=14) -> Optional[float]:
        """计算RSI相对强弱指标"""
        if len(prices) < period + 1:
            return None
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _calculate_kdj(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period=9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """计算KDJ随机指标"""
        if len(closes) < period:
            return None, None, None
        
        # 计算最近period天的最高价和最低价
        recent_highs = highs[-period:]
        recent_lows = lows[-period:]
        current_close = closes[-1]
        
        highest = np.max(recent_highs)
        lowest = np.min(recent_lows)
        
        if highest == lowest:
            rsv = 50
        else:
            rsv = (current_close - lowest) / (highest - lowest) * 100
        
        # 计算K、D、J值（简化版本）
        # 实际应用中需要用前一天的K、D值，这里使用简化计算
        k = rsv * 0.333 + 50 * 0.667  # 简化的K值
        d = k * 0.333 + 50 * 0.667    # 简化的D值
        j = 3 * k - 2 * d              # J值
        
        return float(k), float(d), float(j)
    
    def _calculate_bollinger_bands(self, prices: np.ndarray, current_price: float, period=20, std_multiplier=2) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
        """计算布林带"""
        if len(prices) < period:
            return None, None, None, None, None
        
        recent_prices = prices[-period:]
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        upper = middle + (std_multiplier * std)
        lower = middle - (std_multiplier * std)
        
        # 计算布林带宽度和位置百分比
        width = (upper - lower) / middle * 100
        percent_b = (current_price - lower) / (upper - lower) * 100 if upper != lower else 50
        
        return float(upper), float(middle), float(lower), float(width), float(percent_b)
    
    def _calculate_williams_r(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period=14) -> Optional[float]:
        """计算威廉指标 %R"""
        if len(closes) < period:
            return None
        
        recent_highs = highs[-period:]
        recent_lows = lows[-period:]
        current_close = closes[-1]
        
        highest = np.max(recent_highs)
        lowest = np.min(recent_lows)
        
        if highest == lowest:
            return -50.0
        
        williams_r = (highest - current_close) / (highest - lowest) * (-100)
        
        return float(williams_r)
    
    def _calculate_cci(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period=14) -> Optional[float]:
        """计算CCI商品通道指数"""
        if len(closes) < period:
            return None
        
        # 计算典型价格
        typical_prices = (highs + lows + closes) / 3
        recent_tp = typical_prices[-period:]
        
        sma_tp = np.mean(recent_tp)
        mean_deviation = np.mean(np.abs(recent_tp - sma_tp))
        
        if mean_deviation == 0:
            return 0.0
        
        current_tp = typical_prices[-1]
        cci = (current_tp - sma_tp) / (0.015 * mean_deviation)
        
        return float(cci)
    
    def _calculate_dmi(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period=14) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """计算DMI趋向指标"""
        if len(closes) < period + 1:
            return None, None, None
        
        # 计算TR（真实波幅）
        tr_list = []
        for i in range(1, len(closes)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            tr = max(tr1, tr2, tr3)
            tr_list.append(tr)
        
        if len(tr_list) < period:
            return None, None, None
        
        # 计算DM（方向性移动）
        dm_plus = []
        dm_minus = []
        
        for i in range(1, len(highs)):
            move_up = highs[i] - highs[i-1]
            move_down = lows[i-1] - lows[i]
            
            if move_up > move_down and move_up > 0:
                dm_plus.append(move_up)
            else:
                dm_plus.append(0)
            
            if move_down > move_up and move_down > 0:
                dm_minus.append(move_down)
            else:
                dm_minus.append(0)
        
        # 计算DI
        if len(tr_list) >= period and len(dm_plus) >= period:
            tr_sum = sum(tr_list[-period:])
            dm_plus_sum = sum(dm_plus[-period:])
            dm_minus_sum = sum(dm_minus[-period:])
            
            if tr_sum > 0:
                pdi = (dm_plus_sum / tr_sum) * 100
                mdi = (dm_minus_sum / tr_sum) * 100
                
                # 计算ADX
                dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
                adx = dx  # 简化计算，实际需要多期平均
                
                return float(pdi), float(mdi), float(adx)
        
        return None, None, None
    
    def _calculate_obv(self, prices: np.ndarray, volumes: np.ndarray) -> Optional[float]:
        """计算OBV能量潮指标"""
        if len(prices) < 2:
            return None
        
        obv = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv += volumes[i]
            elif prices[i] < prices[i-1]:
                obv -= volumes[i]
            # 价格相等时OBV不变
        
        return float(obv)
    
    def _calculate_support_resistance(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, lookback=20) -> Tuple[Optional[float], Optional[float]]:
        """计算支撑阻力位"""
        if len(closes) < lookback:
            return None, None
        
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        
        # 简化算法：最近期间的最高价作为阻力位，最低价作为支撑位
        resistance = float(np.max(recent_highs))
        support = float(np.min(recent_lows))
        
        return support, resistance
    
    def analyze_technical_strength(self, indicators: AdvancedTechnicalIndicators, current_price: float) -> Dict[str, Any]:
        """分析技术面强弱"""
        signals = []
        strength_score = 0
        max_score = 0
        
        # 1. 趋势分析
        if indicators.ma5 and indicators.ma20 and indicators.ma60:
            max_score += 3
            if indicators.ma5 > indicators.ma20 > indicators.ma60:
                signals.append("多头排列")
                strength_score += 3
            elif indicators.ma5 > indicators.ma20:
                signals.append("短期趋势向上")
                strength_score += 1
            elif indicators.ma5 < indicators.ma20 < indicators.ma60:
                signals.append("空头排列")
                strength_score -= 3
        
        # 2. MACD分析
        if indicators.macd and indicators.macd_signal:
            max_score += 2
            if indicators.macd > indicators.macd_signal and indicators.macd > 0:
                signals.append("MACD金叉向上")
                strength_score += 2
            elif indicators.macd < indicators.macd_signal and indicators.macd < 0:
                signals.append("MACD死叉向下")
                strength_score -= 2
        
        # 3. RSI分析
        if indicators.rsi:
            max_score += 2
            if indicators.rsi < 30:
                signals.append("RSI超卖")
                strength_score += 1
            elif indicators.rsi > 70:
                signals.append("RSI超买")
                strength_score -= 1
            elif 40 <= indicators.rsi <= 60:
                signals.append("RSI中性区间")
        
        # 4. KDJ分析
        if indicators.kdj_k and indicators.kdj_d:
            max_score += 2
            if indicators.kdj_k > indicators.kdj_d and indicators.kdj_k < 80:
                signals.append("KDJ金叉")
                strength_score += 1
            elif indicators.kdj_k < indicators.kdj_d and indicators.kdj_k > 20:
                signals.append("KDJ死叉")
                strength_score -= 1
        
        # 5. 布林带分析
        if indicators.bb_upper and indicators.bb_lower and indicators.bb_percent:
            max_score += 2
            if indicators.bb_percent > 80:
                signals.append("价格接近布林带上轨")
                strength_score -= 1
            elif indicators.bb_percent < 20:
                signals.append("价格接近布林带下轨")
                strength_score += 1
            elif 40 <= indicators.bb_percent <= 60:
                signals.append("价格在布林带中轨附近")
        
        # 6. 成交量分析
        if indicators.volume_ratio:
            max_score += 1
            if indicators.volume_ratio > 2:
                signals.append("成交量显著放大")
                strength_score += 1
            elif indicators.volume_ratio < 0.5:
                signals.append("成交量萎缩")
                strength_score -= 1
        
        # 计算强度百分比
        if max_score > 0:
            strength_percentage = (strength_score + max_score) / (2 * max_score) * 100
        else:
            strength_percentage = 50
        
        # 判断总体技术面
        if strength_percentage >= 70:
            overall_trend = "强势"
        elif strength_percentage >= 55:
            overall_trend = "偏强"
        elif strength_percentage >= 45:
            overall_trend = "中性"
        elif strength_percentage >= 30:
            overall_trend = "偏弱"
        else:
            overall_trend = "弱势"
        
        return {
            'signals': signals,
            'strength_score': strength_score,
            'max_score': max_score,
            'strength_percentage': strength_percentage,
            'overall_trend': overall_trend,
            'technical_summary': f"技术面{overall_trend}，强度{strength_percentage:.1f}%"
        }


# 全局技术分析器实例
advanced_analyzer = AdvancedTechnicalAnalyzer()


def calculate_advanced_indicators(prices: List[float], 
                                volumes: List[float] = None,
                                highs: List[float] = None,
                                lows: List[float] = None,
                                current_price: float = None) -> AdvancedTechnicalIndicators:
    """便捷函数：计算高级技术指标"""
    return advanced_analyzer.calculate_comprehensive_indicators(
        prices, volumes, highs, lows, current_price
    )


def analyze_technical_strength(indicators: AdvancedTechnicalIndicators, current_price: float) -> Dict[str, Any]:
    """便捷函数：分析技术强度"""
    return advanced_analyzer.analyze_technical_strength(indicators, current_price)


if __name__ == "__main__":
    # 测试技术分析
    print("=== 高级技术分析测试 ===")
    
    # 模拟价格数据
    test_prices = [100, 102, 101, 105, 107, 106, 108, 110, 109, 112, 115, 113, 116, 118, 120,
                   119, 121, 123, 122, 125, 127, 126, 128, 130, 129, 132, 134, 133, 135, 137]
    test_volumes = [1000000 + i * 50000 for i in range(len(test_prices))]
    
    indicators = calculate_advanced_indicators(
        prices=test_prices,
        volumes=test_volumes,
        current_price=137
    )
    
    print("技术指标结果:")
    for key, value in indicators.to_dict().items():
        if value is not None:
            print(f"  {key}: {value:.2f}")
    
    print("\n技术强度分析:")
    strength = analyze_technical_strength(indicators, 137)
    print(f"  技术面: {strength['overall_trend']}")
    print(f"  强度: {strength['strength_percentage']:.1f}%")
    print(f"  信号: {', '.join(strength['signals'])}")