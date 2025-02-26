from decimal import Decimal
from typing import List, Tuple, Optional
import numpy as np

from ..base.base_strategy import BaseStrategyAgent, TradingStrategy

class TrendFollowingAgent(BaseStrategyAgent):
    def __init__(
        self,
        short_ma_periods: int = 20,
        long_ma_periods: int = 50,
        rsi_periods: int = 14,
        rsi_threshold: float = 30.0,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        strategy: TradingStrategy = None,
        **kwargs
    ):
        """
        Initialize Trend Following Strategy Agent.
        
        Args:
            short_ma_periods: Periods for short-term moving average
            long_ma_periods: Periods for long-term moving average
            rsi_periods: Periods for RSI calculation
            rsi_threshold: RSI threshold for oversold/overbought
            macd_fast: Fast period for MACD
            macd_slow: Slow period for MACD
            macd_signal: Signal period for MACD
            strategy: Trading strategy configuration
        """
        super().__init__(strategy=strategy, **kwargs)
        self.short_ma_periods = short_ma_periods
        self.long_ma_periods = long_ma_periods
        self.rsi_periods = rsi_periods
        self.rsi_threshold = rsi_threshold
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

    async def analyze_market_conditions(self) -> str:
        """Analyze price history and trend indicators"""
        conditions = []
        
        for token in self.strategy.tokens:
            price_history = self.tools.get("GetAlchemyPriceHistoryBySymbol").forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1  # 1 day of history
            )
            
            prices = [price.value for price in price_history.data]
            
            # Calculate indicators
            short_ma = self._calculate_ma(prices, self.short_ma_periods)
            long_ma = self._calculate_ma(prices, self.long_ma_periods)
            rsi = self._calculate_rsi(prices, self.rsi_periods)
            macd, signal = self._calculate_macd(prices)
            
            conditions.append(
                f"Token: {token}\n"
                f"- Current Price: {prices[-1]:.2f}\n"
                f"- Short MA ({self.short_ma_periods}): {short_ma:.2f}\n"
                f"- Long MA ({self.long_ma_periods}): {long_ma:.2f}\n"
                f"- RSI ({self.rsi_periods}): {rsi:.2f}\n"
                f"- MACD: {macd:.4f}\n"
                f"- Signal: {signal:.4f}"
            )
            
        return "=== Market Conditions ===\n" + "\n\n".join(conditions)

    async def generate_trading_signals(self) -> str:
        """Generate trend-based trading signals"""
        signals = []
        
        for token in self.strategy.tokens:
            price_history = self.tools.get("GetAlchemyPriceHistoryBySymbol").forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            trend_signal = self._analyze_trend(prices)
            
            if trend_signal:
                direction, strength, indicators = trend_signal
                signals.append(
                    f"{direction} trend detected for {token} (Strength: {strength}):\n"
                    f"- Indicator Signals:\n{indicators}"
                )
        
        if not signals:
            return "No trading signals generated"
        
        return "=== Trading Signals ===\n" + "\n\n".join(signals)

    def _calculate_ma(self, prices: List[float], periods: int) -> float:
        """Calculate moving average"""
        if len(prices) < periods:
            return 0.0
        return float(np.mean(prices[-periods:]))

    def _calculate_rsi(self, prices: List[float], periods: int) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < periods + 1:
            return 50.0
            
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-periods:])
        avg_loss = np.mean(losses[-periods:])
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    def _calculate_macd(self, prices: List[float]) -> Tuple[float, float]:
        """Calculate MACD and signal line"""
        if len(prices) < self.macd_slow:
            return 0.0, 0.0
            
        fast_ma = self._calculate_ma(prices, self.macd_fast)
        slow_ma = self._calculate_ma(prices, self.macd_slow)
        macd = fast_ma - slow_ma
        
        signal = self._calculate_ma(prices[-self.macd_signal:], self.macd_signal)
        return macd, signal

    def _analyze_trend(self, prices: List[float]) -> Optional[Tuple[str, str, str]]:
        """
        Analyze trend direction and strength using multiple indicators
        
        Returns:
            Tuple of (direction, strength, indicators) if trend detected,
            None otherwise
        """
        if len(prices) < self.long_ma_periods:
            return None
            
        short_ma = self._calculate_ma(prices, self.short_ma_periods)
        long_ma = self._calculate_ma(prices, self.long_ma_periods)
        rsi = self._calculate_rsi(prices, self.rsi_periods)
        macd, signal = self._calculate_macd(prices)
        
        # Analyze trend signals
        ma_trend = "Bullish" if short_ma > long_ma else "Bearish"
        rsi_signal = (
            "Oversold" if rsi < self.rsi_threshold 
            else "Overbought" if rsi > (100 - self.rsi_threshold)
            else "Neutral"
        )
        macd_trend = "Bullish" if macd > signal else "Bearish"
        
        # Determine overall trend
        bullish_signals = sum(1 for signal in [ma_trend, rsi_signal, macd_trend] 
                            if "Bullish" in signal or "Oversold" in signal)
        bearish_signals = sum(1 for signal in [ma_trend, rsi_signal, macd_trend]
                            if "Bearish" in signal or "Overbought" in signal)
        
        if abs(bullish_signals - bearish_signals) >= 2:
            direction = "Upward" if bullish_signals > bearish_signals else "Downward"
            strength = "Strong" if abs(bullish_signals - bearish_signals) == 3 else "Moderate"
            
            indicators = (
                f"  MA Trend: {ma_trend}\n"
                f"  RSI ({rsi:.2f}): {rsi_signal}\n"
                f"  MACD: {macd_trend}"
            )
            
            return direction, strength, indicators
            
        return None
