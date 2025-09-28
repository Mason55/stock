# src/backtest/cost_model.py - Trading cost model for Chinese markets
from decimal import Decimal
from typing import Dict
from src.models.trading import OrderSide


class CostModel:
    """Trading cost model for Chinese stock markets"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Default cost structure for Chinese A-shares
        self.commission_rate = Decimal(str(self.config.get('commission_rate', 0.0003)))  # 0.03%
        self.min_commission = Decimal(str(self.config.get('min_commission', 5.0)))       # 5 RMB minimum
        
        # Stamp tax (only on sells)
        self.stamp_tax_rate = Decimal(str(self.config.get('stamp_tax_rate', 0.001)))     # 0.1%
        
        # Transfer fee
        self.transfer_fee_rate = Decimal(str(self.config.get('transfer_fee_rate', 0.00002)))  # 0.002%
        
        # Market impact (slippage)
        self.market_impact_rate = Decimal(str(self.config.get('market_impact_rate', 0.0005)))  # 0.05%
    
    def calculate_commission(self, symbol: str, quantity: int, price: Decimal) -> Decimal:
        """Calculate brokerage commission"""
        amount = Decimal(quantity) * price
        commission = amount * self.commission_rate
        
        # Apply minimum commission
        commission = max(commission, self.min_commission)
        
        return commission.quantize(Decimal('0.01'))
    
    def calculate_stamp_tax(self, symbol: str, quantity: int, price: Decimal, side: OrderSide) -> Decimal:
        """Calculate stamp tax (only for sells)"""
        if side == OrderSide.SELL:
            amount = Decimal(quantity) * price
            tax = amount * self.stamp_tax_rate
            return tax.quantize(Decimal('0.01'))
        
        return Decimal('0.00')
    
    def calculate_transfer_fee(self, symbol: str, quantity: int, price: Decimal) -> Decimal:
        """Calculate transfer fee"""
        amount = Decimal(quantity) * price
        fee = amount * self.transfer_fee_rate
        
        # Different exchanges may have different fee structures
        if symbol.endswith('.SH'):
            # Shanghai Stock Exchange
            fee = fee
        elif symbol.endswith('.SZ'):
            # Shenzhen Stock Exchange 
            fee = fee
        
        return fee.quantize(Decimal('0.01'))
    
    def calculate_market_impact(self, symbol: str, quantity: int, price: Decimal, side: OrderSide) -> Decimal:
        """Calculate market impact (slippage)"""
        amount = Decimal(quantity) * price
        impact = amount * self.market_impact_rate
        
        # Impact is always a cost (reduces proceeds for sells, increases cost for buys)
        return impact.quantize(Decimal('0.01'))
    
    def calculate_total_cost(self, symbol: str, quantity: int, price: Decimal, side: OrderSide) -> Dict[str, Decimal]:
        """Calculate all trading costs"""
        
        commission = self.calculate_commission(symbol, quantity, price)
        stamp_tax = self.calculate_stamp_tax(symbol, quantity, price, side)
        transfer_fee = self.calculate_transfer_fee(symbol, quantity, price)
        market_impact = self.calculate_market_impact(symbol, quantity, price, side)
        
        total_cost = commission + stamp_tax + transfer_fee + market_impact
        
        return {
            'commission': commission,
            'stamp_tax': stamp_tax,
            'transfer_fee': transfer_fee,
            'market_impact': market_impact,
            'total_cost': total_cost
        }
    
    def calculate_net_amount(self, symbol: str, quantity: int, price: Decimal, side: OrderSide) -> Decimal:
        """Calculate net amount after all costs"""
        gross_amount = Decimal(quantity) * price
        costs = self.calculate_total_cost(symbol, quantity, price, side)
        total_cost = costs['total_cost']
        
        if side == OrderSide.BUY:
            # For buys, costs are added to the amount paid
            net_amount = gross_amount + total_cost
        else:
            # For sells, costs are deducted from proceeds
            net_amount = gross_amount - total_cost
        
        return net_amount.quantize(Decimal('0.01'))