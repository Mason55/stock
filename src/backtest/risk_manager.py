# src/backtest/risk_manager.py - Risk management for backtest
from typing import Dict, Optional
from decimal import Decimal
from src.models.trading import Order, OrderSide


class BacktestRiskManager:
    """Risk manager for backtest engine"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Position limits
        self.max_position_pct = self.config.get('max_position_pct', 0.1)  # 10% max per position
        self.max_total_exposure = self.config.get('max_total_exposure', 0.95)  # 95% max total exposure
        
        # Order limits
        self.max_order_value = self.config.get('max_order_value', 1000000)  # 1M RMB max order
        self.min_order_value = self.config.get('min_order_value', 1000)     # 1K RMB min order
        
        # Concentration limits
        self.max_sector_exposure = self.config.get('max_sector_exposure', 0.3)  # 30% per sector
        
        # Daily limits
        self.max_daily_loss = self.config.get('max_daily_loss', 0.05)  # 5% daily loss limit
        
    async def check_order(self, order: Order, portfolio) -> bool:
        """
        Check if order passes all risk controls
        
        Args:
            order: Order to check
            portfolio: Current portfolio state
            
        Returns:
            True if order passes risk checks
        """
        
        # Check order value limits
        if not self._check_order_value_limits(order):
            return False
        
        # Check position limits
        if not self._check_position_limits(order, portfolio):
            return False
        
        # Check cash availability for buy orders
        if not self._check_cash_availability(order, portfolio):
            return False
        
        # Check position availability for sell orders
        if not self._check_position_availability(order, portfolio):
            return False
        
        # Check total portfolio exposure
        if not self._check_total_exposure(order, portfolio):
            return False
        
        return True
    
    def _check_order_value_limits(self, order: Order) -> bool:
        """Check order value against limits"""
        if order.price is None:
            # Market order - assume reasonable price for check
            estimated_price = Decimal('50.0')  # This should come from market data
        else:
            estimated_price = order.price
        
        order_value = Decimal(order.quantity) * estimated_price
        
        if order_value > self.max_order_value:
            return False
        
        if order_value < self.min_order_value:
            return False
        
        return True
    
    def _check_position_limits(self, order: Order, portfolio) -> bool:
        """Check position size limits"""
        if order.side == OrderSide.SELL:
            return True  # Selling reduces position, no limit check needed
        
        # For buy orders, check if new position would exceed limits
        current_position = portfolio.positions.get(order.symbol, 0)
        new_position = current_position + order.quantity
        
        # Estimate position value
        if order.price is None:
            estimated_price = Decimal('50.0')  # Should come from market data
        else:
            estimated_price = order.price
        
        position_value = Decimal(new_position) * estimated_price
        max_position_value = portfolio.total_value * self.max_position_pct
        
        return position_value <= max_position_value
    
    def _check_cash_availability(self, order: Order, portfolio) -> bool:
        """Check if sufficient cash available for buy orders"""
        if order.side == OrderSide.SELL:
            return True
        
        # Estimate order cost
        if order.price is None:
            estimated_price = Decimal('50.0')  # Should come from market data
        else:
            estimated_price = order.price
        
        estimated_cost = Decimal(order.quantity) * estimated_price * Decimal('1.01')  # Add 1% buffer for costs
        
        return portfolio.cash >= float(estimated_cost)
    
    def _check_position_availability(self, order: Order, portfolio) -> bool:
        """Check if sufficient position available for sell orders"""
        if order.side == OrderSide.BUY:
            return True
        
        current_position = portfolio.positions.get(order.symbol, 0)
        return current_position >= order.quantity
    
    def _check_total_exposure(self, order: Order, portfolio) -> bool:
        """Check total portfolio exposure"""
        if order.side == OrderSide.SELL:
            return True  # Selling reduces exposure
        
        # Calculate current exposure
        total_holdings = sum(portfolio.holdings.values())
        current_exposure = total_holdings / portfolio.total_value if portfolio.total_value > 0 else 0
        
        # Estimate new exposure after order
        if order.price is None:
            estimated_price = Decimal('50.0')
        else:
            estimated_price = order.price
        
        order_value = float(Decimal(order.quantity) * estimated_price)
        new_exposure = (total_holdings + order_value) / portfolio.total_value
        
        return new_exposure <= self.max_total_exposure
    
    def calculate_risk_metrics(self, portfolio) -> Dict:
        """Calculate current portfolio risk metrics"""
        if portfolio.total_value <= 0:
            return {}
        
        total_holdings = sum(portfolio.holdings.values())
        exposure = total_holdings / portfolio.total_value
        
        # Calculate concentration by position
        position_concentrations = {}
        for symbol, value in portfolio.holdings.items():
            position_concentrations[symbol] = value / portfolio.total_value
        
        # Find largest position
        max_position_pct = max(position_concentrations.values()) if position_concentrations else 0
        
        # Calculate number of positions
        num_positions = len([pos for pos in portfolio.positions.values() if pos > 0])
        
        return {
            'total_exposure': exposure,
            'max_position_pct': max_position_pct,
            'num_positions': num_positions,
            'cash_ratio': portfolio.cash / portfolio.total_value,
            'position_concentrations': position_concentrations
        }