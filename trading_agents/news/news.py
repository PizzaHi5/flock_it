from decimal import Decimal
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np

from ..base.base_strategy import BaseStrategyAgent, TradingStrategy

class NewsEventTradingAgent(BaseStrategyAgent):
    def __init__(
        self,
        price_impact_threshold: float = 2.0,
        volume_surge_threshold: float = 3.0,
        sentiment_periods: int = 12,  # 1 hour in 5-min intervals
        strategy: TradingStrategy = None,
        **kwargs
    ):
        """
        Initialize News Event Trading Strategy Agent.
        
        Args:
            price_impact_threshold: Minimum price change % to consider significant
            volume_surge_threshold: Volume increase multiple to identify high impact
            sentiment_periods: Number of periods for sentiment analysis
            strategy: Trading strategy configuration
        """
        super().__init__(strategy=strategy, **kwargs)
        self.price_impact_threshold = Decimal(str(price_impact_threshold))
        self.volume_surge_threshold = Decimal(str(volume_surge_threshold))
        self.sentiment_periods = sentiment_periods

    async def analyze_market_conditions(self) -> str:
        """Analyze market reaction to news events"""
        conditions = []
        
        for token in self.strategy.tokens:
            # Get market metrics
            metrics = self.tools["GetCookieMetricsBySymbol"].forward(
                symbol=token,
                interval="_3Days"
            )
            
            # Get price history
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            
            # Calculate metrics
            price_change = self._calculate_price_change(prices)
            volume_surge = self._calculate_volume_surge(metrics)
            sentiment = self._analyze_market_sentiment(metrics)
            
            conditions.append(
                f"Token: {token}\n"
                f"- Price Change: {price_change:.2f}%\n"
                f"- Volume Change: {volume_surge:.2f}x\n"
                f"- Market Sentiment: {sentiment}\n"
                f"- Recent Tweets: {len(metrics.top_tweets)}\n"
                f"- Avg Engagement: {metrics.average_engagements_count:.0f}"
            )
            
        return "=== Market Conditions ===\n" + "\n\n".join(conditions)

    async def generate_trading_signals(self) -> str:
        """Generate news-based trading signals"""
        signals = []
        
        for token in self.strategy.tokens:
            metrics = self.tools["GetCookieMetricsBySymbol"].forward(
                symbol=token,
                interval="_3Days"
            )
            
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1
            )
            
            prices = [price.value for price in price_history.data]
            news_signal = self._detect_news_opportunity(prices, metrics)
            
            if news_signal:
                direction, confidence, details = news_signal
                signals.append(
                    f"{direction} opportunity detected for {token}:\n"
                    f"- Signal Confidence: {confidence}\n"
                    f"- Analysis:\n{details}"
                )
        
        if not signals:
            return "No trading signals generated"
        
        return "=== Trading Signals ===\n" + "\n\n".join(signals)

    def _calculate_price_change(self, prices: List[float]) -> float:
        """Calculate recent price change percentage"""
        if len(prices) < self.sentiment_periods:
            return 0.0
        
        start_price = prices[-self.sentiment_periods]
        current_price = prices[-1]
        return (current_price - start_price) / start_price * 100

    def _calculate_volume_surge(self, metrics: any) -> float:
        """Calculate volume surge multiple"""
        if not hasattr(metrics, 'volume_24_hours') or not metrics.volume_24_hours:
            return 1.0
        
        avg_volume = metrics.volume_24_hours / 24  # Average hourly volume
        current_volume = metrics.volume_24_hours_delta_percent / 100 * avg_volume
        
        return current_volume / avg_volume if avg_volume > 0 else 1.0

    def _analyze_market_sentiment(self, metrics: any) -> str:
        """Analyze market sentiment from social metrics"""
        if not metrics.average_engagements_count:
            return "Neutral"
            
        engagement_change = metrics.average_engagements_count_delta_percent
        follower_change = metrics.followers_count - metrics.smart_followers_count
        
        if engagement_change > 50 and follower_change > 0:
            return "Very Positive"
        elif engagement_change > 25:
            return "Positive"
        elif engagement_change < -25:
            return "Negative"
        elif engagement_change < -50 and follower_change < 0:
            return "Very Negative"
        else:
            return "Neutral"

    def _detect_news_opportunity(
        self,
        prices: List[float],
        metrics: any
    ) -> Optional[Tuple[str, str, str]]:
        """
        Detect trading opportunities based on news impact
        
        Returns:
            Tuple of (direction, confidence, details) if opportunity detected,
            None otherwise
        """
        if len(prices) < self.sentiment_periods:
            return None
            
        price_change = self._calculate_price_change(prices)
        volume_surge = self._calculate_volume_surge(metrics)
        sentiment = self._analyze_market_sentiment(metrics)
        
        # Check for significant market reaction
        if (abs(price_change) > float(self.price_impact_threshold) and 
            volume_surge > float(self.volume_surge_threshold)):
            
            direction = "Upward" if price_change > 0 else "Downward"
            
            # Determine confidence based on alignment of signals
            sentiment_aligned = (
                (direction == "Upward" and "Positive" in sentiment) or
                (direction == "Downward" and "Negative" in sentiment)
            )
            
            confidence = "High" if sentiment_aligned else "Medium"
            
            details = (
                f"  Price Impact: {price_change:.2f}%\n"
                f"  Volume Surge: {volume_surge:.2f}x\n"
                f"  Market Sentiment: {sentiment}\n"
                f"  Recent Engagement: {metrics.average_engagements_count:.0f}"
            )
            
            return direction, confidence, details
            
        return None
