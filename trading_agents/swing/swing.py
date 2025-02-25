from decimal import Decimal
from typing import List, Tuple, Optional
import numpy as np

from ..base.base_strategy import BaseStrategyAgent, TradingStrategy

class SwingTradingAgent(BaseStrategyAgent):
    def __init__(
        self,
        lookback_periods: int = 20,
        volatility_window: int = 14,
        support_resistance_periods: int = 30,
        swing_threshold: float = 2.0,
        strategy: TradingStrategy = None,
        **kwargs
    ):
        """
        Initialize Swing Trading Strategy Agent.
        
        Args:
            lookback_periods: Number of periods for pattern analysis
            volatility_window: Periods for volatility calculation
            support_resistance_periods: Periods for support/resistance levels
            swing_threshold: Minimum percentage for swing identification
            strategy: Trading strategy configuration
        """
        super().__init__(strategy=strategy, **kwargs)
        self.lookback_periods = lookback_periods
        self.volatility_window = volatility_window
        self.support_resistance_periods = support_resistance_periods
        self.swing_threshold = Decimal(str(swing_threshold))

    async def analyze_market_conditions(self) -> str:
        """Analyze price patterns and market conditions"""
        conditions = []
        
        for token in self.strategy.tokens:
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            support, resistance = self._calculate_support_resistance(prices)
            volatility = self._calculate_volatility(prices)
            pattern = self._identify_price_pattern(prices)
            
            conditions.append(
                f"Token: {token}\n"
                f"- Current Price: {prices[-1]:.2f}\n"
                f"- Support Level: {support:.2f}\n"
                f"- Resistance Level: {resistance:.2f}\n"
                f"- Volatility: {volatility:.2f}%\n"
                f"- Price Pattern: {pattern}"
            )
            
        return "=== Market Conditions ===\n" + "\n\n".join(conditions)

    async def generate_trading_signals(self) -> str:
        """Generate swing trading signals"""
        signals = []
        
        for token in self.strategy.tokens:
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            swing_signal = self._detect_swing_opportunity(prices)
            
            if swing_signal:
                direction, confidence, details = swing_signal
                signals.append(
                    f"{direction} swing opportunity detected for {token}:\n"
                    f"- Confidence: {confidence}\n"
                    f"- Details:\n{details}"
                )
        
        if not signals:
            return "No trading signals generated"
        
        return "=== Trading Signals ===\n" + "\n\n".join(signals)

    def _calculate_support_resistance(
        self,
        prices: List[float]
    ) -> Tuple[float, float]:
        """Calculate support and resistance levels"""
        if len(prices) < self.support_resistance_periods:
            return 0.0, 0.0
            
        window = prices[-self.support_resistance_periods:]
        support = float(np.percentile(window, 25))
        resistance = float(np.percentile(window, 75))
        
        return support, resistance

    def _calculate_volatility(self, prices: List[float]) -> float:
        """Calculate price volatility"""
        if len(prices) < self.volatility_window:
            return 0.0
            
        returns = np.diff(prices) / prices[:-1]
        return float(np.std(returns[-self.volatility_window:]) * 100)

    def _identify_price_pattern(self, prices: List[float]) -> str:
        """Identify common price patterns"""
        if len(prices) < self.lookback_periods:
            return "Insufficient data"
            
        window = prices[-self.lookback_periods:]
        highs = np.array([max(window[i:i+5]) for i in range(len(window)-5)])
        lows = np.array([min(window[i:i+5]) for i in range(len(window)-5)])
        
        # Pattern analysis logic
        if np.all(np.diff(highs) > 0) and np.all(np.diff(lows) > 0):
            return "Upward Channel"
        elif np.all(np.diff(highs) < 0) and np.all(np.diff(lows) < 0):
            return "Downward Channel"
        elif np.std(window) < np.mean(window) * 0.01:
            return "Consolidation"
        else:
            return "No Clear Pattern"

    def _detect_swing_opportunity(
        self,
        prices: List[float]
    ) -> Optional[Tuple[str, str, str]]:
        """
        Detect potential swing trading opportunities
        
        Returns:
            Tuple of (direction, confidence, details) if opportunity detected,
            None otherwise
        """
        if len(prices) < self.lookback_periods:
            return None
            
        support, resistance = self._calculate_support_resistance(prices)
        volatility = self._calculate_volatility(prices)
        pattern = self._identify_price_pattern(prices)
        current_price = prices[-1]
        
        # Distance to support/resistance
        support_distance = (current_price - support) / support * 100
        resistance_distance = (resistance - current_price) / current_price * 100
        
        # Analyze swing opportunity
        if support_distance < float(self.swing_threshold):
            confidence = "High" if volatility > 2.0 else "Medium"
            details = (
                f"  Near support level ({support_distance:.2f}% above)\n"
                f"  Volatility: {volatility:.2f}%\n"
                f"  Pattern: {pattern}"
            )
            return "Upward", confidence, details
            
        elif resistance_distance < float(self.swing_threshold):
            confidence = "High" if volatility > 2.0 else "Medium"
            details = (
                f"  Near resistance level ({resistance_distance:.2f}% below)\n"
                f"  Volatility: {volatility:.2f}%\n"
                f"  Pattern: {pattern}"
            )
            return "Downward", confidence, details
            
        return None
