import numpy as np
from decimal import Decimal
from typing import List, Tuple, Optional

from ..base.base_strategy import BaseStrategyAgent, TradingStrategy

class BreakoutStrategyAgent(BaseStrategyAgent):
    def __init__(
        self,
        lookback_periods: int = 20,
        breakout_threshold: float = 2.0,
        confirmation_periods: int = 3,
        strategy: TradingStrategy = None,
        **kwargs
    ):
        """
        Initialize the Breakout Strategy Agent.
        
        Args:
            lookback_periods: Number of periods to calculate support/resistance
            breakout_threshold: Minimum percentage move to confirm breakout
            confirmation_periods: Number of periods price must remain beyond level
            strategy: Trading strategy configuration
        """
        super().__init__(strategy=strategy, **kwargs)
        self.lookback_periods = lookback_periods
        self.breakout_threshold = Decimal(str(breakout_threshold))
        self.confirmation_periods = confirmation_periods

    async def analyze_market_conditions(self) -> str:
        """Analyze price history and identify support/resistance levels"""
        conditions = []
        
        for token in self.strategy.tokens:
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1  # 1 day of history
            )
            
            prices = [price.value for price in price_history.data]
            support, resistance = self._calculate_support_resistance(
                prices,
                self.lookback_periods
            )
            
            current_price = prices[-1]
            conditions.append(
                f"Token: {token}\n"
                f"- Current Price: {current_price:.2f}\n"
                f"- Support Level: {support:.2f}\n"
                f"- Resistance Level: {resistance:.2f}\n"
                f"- Distance to Support: {((current_price - support) / support * 100):.2f}%\n"
                f"- Distance to Resistance: {((resistance - current_price) / current_price * 100):.2f}%"
            )
            
        return "=== Market Conditions ===\n" + "\n\n".join(conditions)

    async def generate_trading_signals(self) -> str:
        """Generate breakout trading signals"""
        signals = []
        
        for token in self.strategy.tokens:
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            breakout_signal = self._detect_breakout(prices)
            
            if breakout_signal:
                direction, level, price_move = breakout_signal
                signals.append(
                    f"{direction} breakout detected for {token}:\n"
                    f"- Breakout Level: {level:.2f}\n"
                    f"- Current Price: {prices[-1]:.2f}\n"
                    f"- Price Move: {price_move:.2f}%"
                )
        
        if not signals:
            return "No trading signals generated"
        
        return "=== Trading Signals ===\n" + "\n\n".join(signals)

    def _calculate_support_resistance(
        self,
        prices: List[float],
        lookback: int
    ) -> Tuple[float, float]:
        """Calculate support and resistance levels using price action"""
        if len(prices) < lookback:
            return 0.0, 0.0
            
        price_window = prices[-lookback:]
        
        # Use rolling min/max for support/resistance
        support = np.min(price_window)
        resistance = np.max(price_window)
        
        return support, resistance

    def _detect_breakout(
        self,
        prices: List[float]
    ) -> Optional[Tuple[str, float, float]]:
        """
        Detect if price has broken out of support/resistance levels
        
        Returns:
            Tuple of (direction, level, price_move) if breakout detected,
            None otherwise
        """
        if len(prices) < self.lookback_periods + self.confirmation_periods:
            return None
            
        # Calculate levels using price window before confirmation period
        analysis_window = prices[:-self.confirmation_periods]
        support, resistance = self._calculate_support_resistance(
            analysis_window,
            self.lookback_periods
        )
        
        # Check confirmation period prices
        confirmation_prices = prices[-self.confirmation_periods:]
        current_price = confirmation_prices[-1]
        
        # Calculate average price move during confirmation
        avg_confirmation_price = np.mean(confirmation_prices)
        
        # Check for breakouts
        if all(p > resistance for p in confirmation_prices):
            price_move = (current_price - resistance) / resistance * 100
            if price_move > float(self.breakout_threshold):
                return "Upward", resistance, price_move
                
        if all(p < support for p in confirmation_prices):
            price_move = (support - current_price) / support * 100
            if price_move > float(self.breakout_threshold):
                return "Downward", support, price_move
                
        return None
