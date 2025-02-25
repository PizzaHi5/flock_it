from decimal import Decimal
from typing import List, Tuple, Optional
import numpy as np
from datetime import datetime, timedelta

from ..base.base_strategy import BaseStrategyAgent, TradingStrategy

class AlgorithmicTradingAgent(BaseStrategyAgent):
    def __init__(
        self,
        ma_periods: List[int] = [10, 20, 50],
        volatility_window: int = 20,
        volume_window: int = 12,
        signal_threshold: float = 2.0,
        strategy: TradingStrategy = None,
        **kwargs
    ):
        """
        Initialize Algorithmic Trading Strategy Agent.
        
        Args:
            ma_periods: List of periods for multiple moving averages
            volatility_window: Periods for volatility calculation
            volume_window: Periods for volume analysis
            signal_threshold: Threshold for signal generation
            strategy: Trading strategy configuration
        """
        super().__init__(strategy=strategy, **kwargs)
        self.ma_periods = sorted(ma_periods)
        self.volatility_window = volatility_window
        self.volume_window = volume_window
        self.signal_threshold = Decimal(str(signal_threshold))

    async def analyze_market_conditions(self) -> str:
        """Analyze market conditions using multiple technical indicators"""
        conditions = []
        
        for token in self.strategy.tokens:
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            
            # Calculate technical indicators
            moving_averages = self._calculate_moving_averages(prices)
            volatility = self._calculate_volatility(prices)
            volume_profile = self._analyze_volume_profile(token)
            price_momentum = self._calculate_momentum(prices)
            
            conditions.append(
                f"Token: {token}\n"
                f"- Current Price: {prices[-1]:.2f}\n"
                f"- Moving Averages:\n"
                f"  {self._format_moving_averages(moving_averages)}\n"
                f"- Volatility: {volatility:.2f}%\n"
                f"- Volume Profile: {volume_profile}\n"
                f"- Price Momentum: {price_momentum:.2f}"
            )
            
        return "=== Market Conditions ===\n" + "\n\n".join(conditions)

    async def generate_trading_signals(self) -> str:
        """Generate algorithmic trading signals"""
        signals = []
        
        for token in self.strategy.tokens:
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            algo_signal = self._generate_algorithmic_signal(prices, token)
            
            if algo_signal:
                direction, probability, details = algo_signal
                signals.append(
                    f"{direction} signal generated for {token}:\n"
                    f"- Probability: {probability:.1f}%\n"
                    f"- Analysis:\n{details}"
                )
        
        if not signals:
            return "No trading signals generated"
        
        return "=== Trading Signals ===\n" + "\n\n".join(signals)

    def _calculate_moving_averages(
        self,
        prices: List[float]
    ) -> List[Tuple[int, float]]:
        """Calculate multiple moving averages"""
        mas = []
        for period in self.ma_periods:
            if len(prices) >= period:
                ma = np.mean(prices[-period:])
                mas.append((period, float(ma)))
        return mas

    def _calculate_volatility(self, prices: List[float]) -> float:
        """Calculate price volatility"""
        if len(prices) < self.volatility_window:
            return 0.0
            
        returns = np.diff(prices[-self.volatility_window:]) / prices[-self.volatility_window:-1]
        return float(np.std(returns) * 100)

    def _analyze_volume_profile(self, token: str) -> str:
        """Analyze trading volume profile"""
        try:
            metrics = self.tools["GetCookieMetricsBySymbol"].forward(
                symbol=token,
                interval="_3Days"
            )
            
            volume_change = metrics.volume_24_hours_delta_percent
            if volume_change > 50:
                return "High"
            elif volume_change < -50:
                return "Low"
            else:
                return "Normal"
        except Exception:
            return "Unknown"

    def _calculate_momentum(self, prices: List[float]) -> float:
        """Calculate price momentum"""
        if len(prices) < self.volume_window:
            return 0.0
            
        returns = np.diff(prices[-self.volume_window:]) / prices[-self.volume_window:-1]
        return float(np.sum(returns) * 100)

    def _format_moving_averages(
        self,
        moving_averages: List[Tuple[int, float]]
    ) -> str:
        """Format moving averages for display"""
        return "\n  ".join(
            f"{period}-period: {value:.2f}" 
            for period, value in moving_averages
        )

    def _generate_algorithmic_signal(
        self,
        prices: List[float],
        token: str
    ) -> Optional[Tuple[str, float, str]]:
        """
        Generate trading signal based on multiple indicators
        
        Returns:
            Tuple of (direction, probability, details) if signal generated,
            None otherwise
        """
        if len(prices) < max(self.ma_periods):
            return None
            
        # Calculate all indicators
        mas = self._calculate_moving_averages(prices)
        volatility = self._calculate_volatility(prices)
        volume_profile = self._analyze_volume_profile(token)
        momentum = self._calculate_momentum(prices)
        current_price = prices[-1]
        
        # Score different aspects (-1 to 1 range)
        ma_scores = []
        for period, ma_value in mas:
            score = 1 if current_price > ma_value else -1
            ma_scores.append(score)
        
        ma_consensus = np.mean(ma_scores)
        vol_score = 1 if volatility < 2.0 else (-1 if volatility > 5.0 else 0)
        momentum_score = np.clip(momentum / 5.0, -1, 1)
        volume_score = {
            "High": 1,
            "Normal": 0,
            "Low": -1,
            "Unknown": 0
        }[volume_profile]
        
        # Weighted scoring system
        weights = {
            "ma": 0.4,
            "momentum": 0.3,
            "volatility": 0.2,
            "volume": 0.1
        }
        
        total_score = (
            ma_consensus * weights["ma"] +
            momentum_score * weights["momentum"] +
            vol_score * weights["volatility"] +
            volume_score * weights["volume"]
        )
        
        # Convert to probability and check threshold
        probability = (total_score + 1) * 50  # Convert -1 to 1 range to 0-100%
        
        if abs(total_score) > float(self.signal_threshold) / 10:
            direction = "Upward" if total_score > 0 else "Downward"
            
            details = (
                f"  Moving Average Analysis:\n"
                f"    {self._format_moving_averages(mas)}\n"
                f"  Momentum: {momentum:.2f}%\n"
                f"  Volatility: {volatility:.2f}%\n"
                f"  Volume Profile: {volume_profile}"
            )
            
            return direction, probability, details
            
        return None
