import numpy as np
from decimal import Decimal
from typing import List, Tuple

from ..base.base_strategy import BaseStrategyAgent, TradingStrategy

class MeanReversionStrategyAgent(BaseStrategyAgent):
    def __init__(
        self,
        lookback_periods: int = 20,
        std_dev_threshold: float = 2.0,
        strategy: TradingStrategy = None,
        **kwargs
    ):
        super().__init__(strategy=strategy, **kwargs)
        self.lookback_periods = lookback_periods
        self.std_dev_threshold = std_dev_threshold

    async def analyze_market_conditions(self) -> str:
        """Analyze price history and mean reversion metrics"""
        conditions = []
        
        for token in self.strategy.tokens:
            price_history = self.tools.get("GetAlchemyPriceHistoryBySymbol").forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            mean, std_dev, z_score = self._calculate_statistics(
                prices,
                self.lookback_periods
            )
            
            conditions.append(
                f"Token: {token}\n"
                f"- Current Price: {prices[-1]:.2f}\n"
                f"- Moving Average: {mean:.2f}\n"
                f"- Standard Deviation: {std_dev:.2f}\n"
                f"- Z-Score: {z_score:.2f}"
            )
            
        return "=== Market Conditions ===\n" + "\n\n".join(conditions)

    async def generate_trading_signals(self) -> str:
        """Generate mean reversion trading signals"""
        signals = []
        
        for token in self.strategy.tokens:
            price_history = self.tools.get("GetAlchemyPriceHistoryBySymbol").forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            mean, std_dev, z_score = self._calculate_statistics(
                prices,
                self.lookback_periods
            )
            
            # Check if price has deviated significantly from mean
            if abs(z_score) > self.std_dev_threshold:
                direction = "Buy" if z_score < 0 else "Sell"
                signals.append(
                    f"{direction} signal for {token}:\n"
                    f"- Price deviation: {z_score:.2f} standard deviations\n"
                    f"- Current price: {prices[-1]:.2f}\n"
                    f"- Moving average: {mean:.2f}"
                )
        
        if not signals:
            return "No trading signals generated"
        
        return "=== Trading Signals ===\n" + "\n\n".join(signals)

    def _calculate_statistics(
        self,
        prices: List[float],
        lookback: int
    ) -> Tuple[float, float, float]:
        """Calculate mean, standard deviation, and z-score"""
        if len(prices) < lookback:
            return 0.0, 0.0, 0.0
            
        price_window = prices[-lookback:]
        current_price = prices[-1]
        
        mean = np.mean(price_window)
        std_dev = np.std(price_window)
        z_score = (current_price - mean) / std_dev if std_dev > 0 else 0
        
        return mean, std_dev, z_score 