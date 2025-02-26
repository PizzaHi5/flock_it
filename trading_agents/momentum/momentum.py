import logging
from decimal import Decimal
from datetime import datetime
from typing import List, Tuple

from ..base.base_strategy import BaseStrategyAgent, TradingStrategy

class MomentumStrategyAgent(BaseStrategyAgent):
    def __init__(
        self,
        short_term_minutes: int = 5,
        long_term_minutes: int = 60,
        threshold: float = 2.0,
        strategy: TradingStrategy = None,
        **kwargs
    ):
        super().__init__(strategy=strategy, **kwargs)
        self.short_term_minutes = short_term_minutes
        self.long_term_minutes = long_term_minutes
        self.threshold = Decimal(str(threshold))

    async def analyze_market_conditions(self) -> str:
        """Analyze price history and momentum for strategy tokens"""
        conditions = []
        
        for token in self.strategy.tokens:
            # Access tools using their class name as the key
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1  # 1 day of history
            )
            
            prices = [price.value for price in price_history.data]
            short_term_change, long_term_change = self._calculate_price_changes(
                prices, 
                self.short_term_minutes // 5,
                self.long_term_minutes // 5
            )
            
            conditions.append(
                f"Token: {token}\n"
                f"- {self.short_term_minutes}min change: {short_term_change:.2f}%\n"
                f"- {self.long_term_minutes}min change: {long_term_change:.2f}%"
            )
            
        return "=== Market Conditions ===\n" + "\n\n".join(conditions)

    async def generate_trading_signals(self) -> str:
        """Generate momentum-based trading signals"""
        signals = []
        
        for token in self.strategy.tokens:
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            short_term_change, long_term_change = self._calculate_price_changes(
                prices,
                self.short_term_minutes // 5,
                self.long_term_minutes // 5
            )
            
            # Check if momentum threshold is met
            if abs(short_term_change) > self.threshold and abs(long_term_change) > self.threshold:
                direction = "Upward" if short_term_change > 0 else "Downward"
                signals.append(
                    f"{direction} momentum detected for {token}:\n"
                    f"- Short-term change: {short_term_change:.2f}%\n"
                    f"- Long-term change: {long_term_change:.2f}%"
                )
        
        if not signals:
            return "No trading signals generated"
        
        return "=== Trading Signals ===\n" + "\n\n".join(signals)

    def _calculate_price_changes(
        self, 
        prices: List[float], 
        short_term_periods: int, 
        long_term_periods: int
    ) -> Tuple[Decimal, Decimal]:
        """Calculate price changes over different time periods"""
        if len(prices) < long_term_periods:
            return Decimal("0"), Decimal("0")
            
        current_price = prices[-1]
        short_term_price = prices[-short_term_periods]
        long_term_price = prices[-long_term_periods]
        
        short_term_change = Decimal(str((current_price - short_term_price) / short_term_price * 100))
        long_term_change = Decimal(str((current_price - long_term_price) / long_term_price * 100))
        
        return short_term_change, long_term_change 