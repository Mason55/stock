# src/core/sentiment_analysis.py - 情绪分析模块
import asyncio
import aiohttp
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SentimentData:
    """情绪分析数据"""
    # 新闻情绪
    news_sentiment_score: Optional[float] = None  # -1到1，负值悲观，正值乐观
    news_count: Optional[int] = None
    positive_news_ratio: Optional[float] = None
    
    # 社交媒体情绪
    social_sentiment_score: Optional[float] = None
    social_mentions: Optional[int] = None
    
    # 研究报告情绪
    analyst_sentiment: Optional[str] = None  # positive, negative, neutral
    analyst_reports_count: Optional[int] = None
    
    # 市场情绪指标
    market_fear_greed_index: Optional[float] = None  # 0-100
    volatility_sentiment: Optional[str] = None
    
    # 行业情绪
    industry_sentiment: Optional[float] = None
    sector_momentum: Optional[str] = None
    
    # 综合情绪评分
    overall_sentiment_score: Optional[float] = None
    sentiment_trend: Optional[str] = None  # improving, stable, declining
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class SentimentAnalyzer:
    """情绪分析器"""
    
    def __init__(self):
        self.sentiment_keywords = {
            'positive': [
                '利好', '上涨', '增长', '突破', '强势', '买入', '推荐', '看好', '乐观',
                '复苏', '回暖', '向好', '积极', '提升', '改善', '机会', '潜力',
                '创新', '领先', '优势', '成功', '盈利', '收益'
            ],
            'negative': [
                '利空', '下跌', '下滑', '跌破', '弱势', '卖出', '警惕', '看空', '悲观',
                '衰退', '低迷', '疲软', '消极', '下降', '恶化', '风险', '危机',
                '困难', '落后', '劣势', '亏损', '损失', '压力'
            ]
        }
        
        self.news_sources = {
            'sina_finance': 'https://finance.sina.com.cn/',
            'eastmoney': 'https://www.eastmoney.com/',
            'caijing': 'https://www.caijing.com.cn/'
        }
    
    async def fetch_sentiment_data(self, symbol: str, config: Dict[str, Any]) -> Optional[SentimentData]:
        """获取情绪分析数据"""
        try:
            # 并行获取各种情绪数据
            tasks = [
                self._fetch_news_sentiment(symbol, config),
                self._fetch_social_sentiment(symbol, config),
                self._fetch_analyst_sentiment(symbol, config),
                self._fetch_market_sentiment(symbol, config)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 整合结果
            sentiment_data = SentimentData()
            
            # 新闻情绪
            if isinstance(results[0], dict):
                sentiment_data.news_sentiment_score = results[0].get('sentiment_score')
                sentiment_data.news_count = results[0].get('news_count')
                sentiment_data.positive_news_ratio = results[0].get('positive_ratio')
            
            # 社交媒体情绪
            if isinstance(results[1], dict):
                sentiment_data.social_sentiment_score = results[1].get('sentiment_score')
                sentiment_data.social_mentions = results[1].get('mentions')
            
            # 分析师情绪
            if isinstance(results[2], dict):
                sentiment_data.analyst_sentiment = results[2].get('sentiment')
                sentiment_data.analyst_reports_count = results[2].get('reports_count')
            
            # 市场情绪
            if isinstance(results[3], dict):
                sentiment_data.market_fear_greed_index = results[3].get('fear_greed_index')
                sentiment_data.volatility_sentiment = results[3].get('volatility_sentiment')
            
            # 计算综合情绪评分
            sentiment_data.overall_sentiment_score = self._calculate_overall_sentiment(sentiment_data)
            sentiment_data.sentiment_trend = self._determine_sentiment_trend(sentiment_data)
            
            return sentiment_data
            
        except Exception as e:
            print(f"获取情绪数据失败: {e}")
            return None
    
    async def _fetch_news_sentiment(self, symbol: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """获取新闻情绪"""
        try:
            # 模拟新闻情绪分析（实际应用中需要接入真实新闻API）
            company_name = config.get('name', symbol)
            industry = config.get('industry', '未知')
            special_features = config.get('special_features', [])
            
            # 基于股票特性模拟新闻情绪
            base_sentiment = 0.0
            news_count = 15
            
            # 华为概念股通常有较多正面新闻
            if '华为概念' in special_features:
                base_sentiment += 0.3
                news_count += 5
            
            # 新能源汽车行业情绪
            if '新能源汽车' in special_features:
                base_sentiment += 0.2
                news_count += 8
            
            # 汽车制造行业基础情绪
            if '汽车制造' in industry:
                base_sentiment += 0.1
            
            # 添加随机波动
            import random
            sentiment_noise = random.uniform(-0.2, 0.2)
            final_sentiment = max(-1.0, min(1.0, base_sentiment + sentiment_noise))
            
            positive_ratio = max(0.0, min(1.0, (final_sentiment + 1) / 2))
            
            return {
                'sentiment_score': final_sentiment,
                'news_count': news_count,
                'positive_ratio': positive_ratio
            }
            
        except Exception as e:
            print(f"获取新闻情绪失败: {e}")
            return {}
    
    async def _fetch_social_sentiment(self, symbol: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """获取社交媒体情绪"""
        try:
            # 模拟社交媒体情绪分析
            special_features = config.get('special_features', [])
            market = config.get('market', 'A')
            
            base_sentiment = 0.0
            mentions = 500
            
            # 热门概念股通常有更多讨论
            if '华为概念' in special_features or '新能源汽车' in special_features:
                base_sentiment += 0.2
                mentions += 200
            
            # 港股相对讨论较少
            if market == 'HK':
                mentions = int(mentions * 0.7)
            
            # 添加随机性
            import random
            sentiment_noise = random.uniform(-0.3, 0.3)
            final_sentiment = max(-1.0, min(1.0, base_sentiment + sentiment_noise))
            
            return {
                'sentiment_score': final_sentiment,
                'mentions': mentions
            }
            
        except Exception as e:
            print(f"获取社交媒体情绪失败: {e}")
            return {}
    
    async def _fetch_analyst_sentiment(self, symbol: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """获取分析师情绪"""
        try:
            # 模拟分析师报告情绪
            industry = config.get('industry', '未知')
            special_features = config.get('special_features', [])
            
            reports_count = 3
            sentiments = ['positive', 'neutral', 'negative']
            
            # 热门行业通常有更多研报
            if '汽车制造' in industry:
                reports_count += 2
            
            if '华为概念' in special_features or '新能源汽车' in special_features:
                reports_count += 3
                # 倾向于正面评价
                sentiment_weights = [0.5, 0.3, 0.2]
            else:
                sentiment_weights = [0.3, 0.5, 0.2]
            
            import random
            analyst_sentiment = random.choices(sentiments, weights=sentiment_weights)[0]
            
            return {
                'sentiment': analyst_sentiment,
                'reports_count': reports_count
            }
            
        except Exception as e:
            print(f"获取分析师情绪失败: {e}")
            return {}
    
    async def _fetch_market_sentiment(self, symbol: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """获取市场情绪指标"""
        try:
            # 模拟市场恐慌贪婪指数
            import random
            fear_greed_index = random.uniform(20, 80)  # 20-80范围，避免极端值
            
            # 基于当前时间模拟波动率情绪
            hour = datetime.now().hour
            if 9 <= hour <= 15:  # 交易时间
                volatility_sentiment = random.choice(['high', 'moderate', 'low'])
            else:
                volatility_sentiment = 'low'
            
            return {
                'fear_greed_index': fear_greed_index,
                'volatility_sentiment': volatility_sentiment
            }
            
        except Exception as e:
            print(f"获取市场情绪失败: {e}")
            return {}
    
    def _calculate_overall_sentiment(self, sentiment_data: SentimentData) -> float:
        """计算综合情绪评分"""
        scores = []
        weights = []
        
        # 新闻情绪权重
        if sentiment_data.news_sentiment_score is not None:
            scores.append(sentiment_data.news_sentiment_score)
            weights.append(0.4)
        
        # 社交媒体情绪权重
        if sentiment_data.social_sentiment_score is not None:
            scores.append(sentiment_data.social_sentiment_score)
            weights.append(0.3)
        
        # 分析师情绪转数值
        if sentiment_data.analyst_sentiment:
            analyst_score = {'positive': 0.5, 'neutral': 0.0, 'negative': -0.5}.get(
                sentiment_data.analyst_sentiment, 0.0
            )
            scores.append(analyst_score)
            weights.append(0.2)
        
        # 市场恐慌贪婪指数转情绪
        if sentiment_data.market_fear_greed_index is not None:
            # 转换为-1到1的范围
            market_score = (sentiment_data.market_fear_greed_index - 50) / 50
            scores.append(market_score)
            weights.append(0.1)
        
        if not scores:
            return 0.0
        
        # 加权平均
        weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
        total_weight = sum(weights)
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _determine_sentiment_trend(self, sentiment_data: SentimentData) -> str:
        """判断情绪趋势"""
        overall_score = sentiment_data.overall_sentiment_score or 0.0
        
        # 简化的趋势判断逻辑
        if overall_score > 0.2:
            return 'improving'
        elif overall_score < -0.2:
            return 'declining'
        else:
            return 'stable'
    
    def analyze_sentiment_strength(self, sentiment_data: SentimentData) -> Dict[str, Any]:
        """分析情绪强度"""
        signals = []
        strength_score = 0
        max_score = 0
        
        # 1. 新闻情绪分析
        if sentiment_data.news_sentiment_score is not None:
            max_score += 2
            if sentiment_data.news_sentiment_score > 0.3:
                signals.append("新闻情绪积极")
                strength_score += 2
            elif sentiment_data.news_sentiment_score < -0.3:
                signals.append("新闻情绪消极")
                strength_score -= 2
            else:
                signals.append("新闻情绪中性")
        
        # 2. 社交媒体情绪
        if sentiment_data.social_sentiment_score is not None:
            max_score += 2
            if sentiment_data.social_sentiment_score > 0.2:
                signals.append("社交媒体乐观")
                strength_score += 1
            elif sentiment_data.social_sentiment_score < -0.2:
                signals.append("社交媒体悲观")
                strength_score -= 1
        
        # 3. 分析师情绪
        if sentiment_data.analyst_sentiment:
            max_score += 1
            if sentiment_data.analyst_sentiment == 'positive':
                signals.append("分析师看好")
                strength_score += 1
            elif sentiment_data.analyst_sentiment == 'negative':
                signals.append("分析师看空")
                strength_score -= 1
        
        # 4. 市场情绪
        if sentiment_data.market_fear_greed_index is not None:
            max_score += 1
            if sentiment_data.market_fear_greed_index > 70:
                signals.append("市场贪婪情绪高涨")
                strength_score -= 1  # 贪婪可能是负面信号
            elif sentiment_data.market_fear_greed_index < 30:
                signals.append("市场恐慌情绪严重")
                strength_score += 1  # 恐慌可能是买入机会
        
        # 计算强度百分比
        if max_score > 0:
            strength_percentage = (strength_score + max_score) / (2 * max_score) * 100
        else:
            strength_percentage = 50
        
        # 判断总体情绪强度
        if strength_percentage >= 70:
            overall_mood = "乐观"
        elif strength_percentage >= 55:
            overall_mood = "偏乐观"
        elif strength_percentage >= 45:
            overall_mood = "中性"
        elif strength_percentage >= 30:
            overall_mood = "偏悲观"
        else:
            overall_mood = "悲观"
        
        return {
            'signals': signals,
            'strength_score': strength_score,
            'max_score': max_score,
            'strength_percentage': strength_percentage,
            'overall_mood': overall_mood,
            'sentiment_summary': f"市场情绪{overall_mood}，强度{strength_percentage:.1f}%"
        }


# 全局情绪分析器
sentiment_analyzer = SentimentAnalyzer()


async def get_sentiment_data(symbol: str, config: Dict[str, Any]) -> Optional[SentimentData]:
    """便捷函数：获取情绪数据"""
    return await sentiment_analyzer.fetch_sentiment_data(symbol, config)


def analyze_sentiment_strength(sentiment_data: SentimentData) -> Dict[str, Any]:
    """便捷函数：分析情绪强度"""
    return sentiment_analyzer.analyze_sentiment_strength(sentiment_data)


if __name__ == "__main__":
    # 测试情绪分析
    async def test_sentiment():
        print("=== 情绪分析测试 ===")
        
        # 模拟配置
        test_config = {
            'name': '赛力斯',
            'special_features': ['华为概念', '新能源汽车'],
            'industry': '汽车制造',
            'market': 'A'
        }
        
        # 获取情绪数据
        sentiment = await get_sentiment_data("601127.SH", test_config)
        
        if sentiment:
            print("情绪数据:")
            for key, value in sentiment.to_dict().items():
                print(f"  {key}: {value}")
            
            # 分析情绪强度
            strength = analyze_sentiment_strength(sentiment)
            print(f"\n情绪分析:")
            print(f"  情绪: {strength['overall_mood']} ({strength['strength_percentage']:.1f}%)")
            print(f"  信号: {', '.join(strength['signals'])}")
        else:
            print("获取情绪数据失败")
    
    asyncio.run(test_sentiment())