# src/models/stock.py - Stock data models
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, DateTime, Integer, Text, Index, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel

Base = declarative_base()


class Stock(Base):
    __tablename__ = 'stocks'
    
    code = Column(String(15), primary_key=True, index=True)  # Extended for HK stocks
    name = Column(String(100), nullable=False, index=True)
    exchange = Column(String(10), nullable=False, index=True)  # SH, SZ, HK
    industry = Column(String(100), index=True)
    market_cap = Column(Float)
    currency = Column(String(3), default='CNY')  # CNY for A-share, HKD for HK
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StockPrice(Base):
    __tablename__ = 'stock_prices'
    __table_args__ = (
        Index('idx_stock_code_timestamp', 'stock_code', 'timestamp'),
        Index('idx_stock_code_timestamp_desc', 'stock_code', desc('timestamp')),
        Index('idx_timestamp_desc', desc('timestamp')),
        Index('idx_volume_price', 'volume', 'close_price'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(15), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)  # Trading volume in shares
    turnover = Column(Float)
    change_pct = Column(Float)


class StockRecommendation(Base):
    __tablename__ = 'stock_recommendations'
    __table_args__ = (
        Index('idx_recommendations_code_timestamp_desc', 'stock_code', desc('timestamp')),
        Index('idx_recommendations_action_confidence', 'action', 'confidence'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(15), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String(20), nullable=False, index=True)  # buy, hold, sell
    confidence = Column(Float, nullable=False, index=True)  # 0.0 to 1.0
    target_price = Column(Float)
    reasoning = Column(Text)
    factors = Column(Text)  # JSON string of contributing factors


# Pydantic models for API responses
class StockInfo(BaseModel):
    code: str
    name: str
    exchange: str
    industry: Optional[str]
    market_cap: Optional[float]
    current_price: Optional[float]
    change_pct: Optional[float]
    
    class Config:
        orm_mode = True


class RecommendationResponse(BaseModel):
    stock_code: str
    action: str
    confidence: float
    target_price: Optional[float]
    reasoning: str
    timestamp: datetime
    
    class Config:
        orm_mode = True