from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal
import random
import pandas as pd
import numpy as np

from alphaswarm.agent.agent import AlphaSwarmAgent
from alphaswarm.config import Config
from alphaswarm.tools.core import GetTokenAddress
from alphaswarm.tools.exchanges import ExecuteTokenSwap, GetTokenPrice
from alphaswarm.tools.alchemy import GetAlchemyPriceHistoryBySymbol
from alphaswarm.services.portfolio import Portfolio
from alphaswarm.tools.cookie.cookie_metrics import GetCookieMetricsBySymbol

@dataclass
class TradingStrategy:
    name: str
    description: str
    rules: str
    tokens: List[str]
    chain: str
    interval_minutes: int
    max_position_size: Decimal
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None

class BaseStrategyAgent(AlphaSwarmAgent):
    def __init__(
        self,
        strategy: TradingStrategy,
        config: Config,
        model_id: str = "anthropic/claude-3-5-sonnet-20241022"
    ) -> None:
        self.strategy = strategy
        self.config = config
        self.portfolio = Portfolio.from_config(config)
        
        # Initialize common tools
        tools = [
            GetTokenAddress(config),
            GetTokenPrice(config),
            GetAlchemyPriceHistoryBySymbol(),
            ExecuteTokenSwap(config),
            GetCookieMetricsBySymbol()
        ]
        
        super().__init__(tools=tools, model_id=model_id)

    async def get_portfolio_balance(self) -> str:
        """Get current portfolio balance information"""
        portfolio_balance = self.portfolio.get_token_balances(chain=self.strategy.chain)
        timestamp = portfolio_balance.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        tokens = portfolio_balance.get_non_zero_balances()
        
        balance_info = [
            f"=== Portfolio Balance at {timestamp} ===",
            "```csv",
            "symbol,address,amount",
            *[f"{token.token_info.symbol},{token.token_info.address},{token.value}" 
              for token in tokens],
            "```"
        ]
        return "\n".join(balance_info)

    async def get_trading_task(self) -> str:
        """Generate the trading task prompt"""
        market_conditions = await self.analyze_market_conditions()
        portfolio_balance = await self.get_portfolio_balance()
        signals = await self.generate_trading_signals()

        task_prompt = (
            f"{portfolio_balance}\n\n"
            f"{market_conditions}\n\n"
            f"{signals}\n\n"
            "=== Trading Strategy Requirements ===\n"
            f"1. Maximum position size: {self.strategy.max_position_size}\n"
            f"2. Strategy rules: {self.strategy.rules}\n"
            f"3. Stop loss: {self.strategy.stop_loss if self.strategy.stop_loss else 'None'}\n"
            f"4. Take profit: {self.strategy.take_profit if self.strategy.take_profit else 'None'}\n\n"
            "Please analyze the above information and decide whether to trade.\n"
            "If you decide to trade, specify the token pair and amount.\n"
            "Provide detailed reasoning for your decision."
        )
        return task_prompt

    async def analyze_market_conditions(self) -> str:
        """Override this method in specific strategy implementations"""
        raise NotImplementedError()

    async def generate_trading_signals(self) -> str:
        """Override this method in specific strategy implementations"""
        raise NotImplementedError()

    async def optimize_parameters(self) -> None:
        """Allow the agent to tune strategy parameters within safe bounds"""
        # Example parameter optimization while keeping the core strategy logic
            # Let the agent optimize thresholds within a safe range
        self.threshold = max(1.0, min(5.0, 
            await self._suggest_optimal_threshold()))
        
    async def _suggest_optimal_threshold(self) -> float:
        """
        Suggests optimal threshold based on recent performance and market conditions.
        Adapts to any trading strategy type while maintaining safety bounds.
        
        Returns:
            float: Suggested threshold value between 1.0 and 5.0
        """
        adjustments = []
        
        for token in self.strategy.tokens:
            # Get price history using existing tool
            price_history = self.tools["GetAlchemyPriceHistoryBySymbol"].forward(
                symbol=token,
                chain=self.strategy.chain,
                interval="5m",
                history=1  # 1 day of history
            )
            
            prices = [price.value for price in price_history.data]
            
            # Calculate base volatility using price changes
            returns = [
                (prices[i] - prices[i-1]) / prices[i-1] 
                for i in range(1, len(prices))
            ]
            volatility = float(np.std(returns) * 100)  # Convert to percentage
            
            # Get market metrics
            try:
                market_data = self.tools["GetCookieMetricsBySymbol"].forward(
                    symbol=token,
                    interval="_3Days"
                )
                volume_change = market_data.get('volume_change_24h', 0)
            except Exception:
                # Handle case where Cookie metrics are unavailable
                volume_change = 0
            
            # Calculate strategy-specific adjustment
            strategy_adjustment = self._calculate_strategy_adjustment(
                volatility=volatility,
                volume_change=volume_change,
                strategy_rules=self.strategy.rules
            )
            
            # Apply risk management bounds based on strategy parameters
            risk_bounds = self._apply_risk_bounds(
                adjustment=strategy_adjustment,
                stop_loss=self.strategy.stop_loss,
                take_profit=self.strategy.take_profit
            )
            
            adjustments.append(risk_bounds)
        
        # Average all token-specific adjustments
        avg_adjustment = sum(adjustments) / len(adjustments) if adjustments else 1.0
        
        # Apply adjustment to current threshold with bounds
        new_threshold = float(self.threshold) * avg_adjustment
        base_threshold = max(1.0, min(5.0, new_threshold))
        
        # Add small random noise for exploration
        return base_threshold * random.uniform(0.98, 1.02)

    def _calculate_strategy_adjustment(
        self,
        volatility: float,
        volume_change: float,
        strategy_rules: str
    ) -> float:
        """Calculate strategy-specific threshold adjustment"""
        base_adjustment = 1.0
        
        # Adjust based on volatility relative to strategy type
        if "momentum" in strategy_rules.lower():
            # More aggressive in high volatility for momentum
            if volatility > 5.0:
                base_adjustment *= 0.9  # More aggressive
            elif volatility < 1.0:
                base_adjustment *= 1.1  # More conservative
        elif "reversion" in strategy_rules.lower():
            # More conservative in high volatility for mean reversion
            if volatility > 5.0:
                base_adjustment *= 1.1  # More conservative
            elif volatility < 1.0:
                base_adjustment *= 0.9  # More aggressive
                
        # Consider volume changes if available
        if abs(volume_change) > 50:
            # High volume changes suggest need for adjustment
            base_adjustment *= 1.05 if volume_change > 0 else 0.95
            
        return base_adjustment

    def _apply_risk_bounds(
        self,
        adjustment: float,
        stop_loss: Optional[Decimal],
        take_profit: Optional[Decimal]
    ) -> float:
        """Apply risk management bounds to threshold adjustment"""
        if stop_loss and take_profit:
            # More conservative adjustment when tight stops are in place
            risk_ratio = float(take_profit / stop_loss)
            if risk_ratio < 2.0:
                adjustment *= 1.1  # More conservative
            elif risk_ratio > 5.0:
                adjustment *= 0.9  # More aggressive
                
        return max(0.5, min(2.0, adjustment))  # Limit adjustment range