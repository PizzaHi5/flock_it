from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Sequence
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
from alphaswarm.core.tool import AlphaSwarmToolBase

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
        strategy: Optional[TradingStrategy] = None,
        config: Optional[Config] = None,
        tools: Sequence[AlphaSwarmToolBase] = None,
        model_id: str = "anthropic/claude-3-5-sonnet-20241022",
        system_prompt: Optional[str] = None,
        hints: Optional[str] = None,
    ) -> None:
        """
        Initialize the BaseStrategyAgent.

        Args:
            strategy: Trading strategy configuration.
            config: Configuration object.
            tools: A sequence of tools to use.
            model_id: The LiteLLM model ID of the LLM to use.
            system_prompt: System prompt defining the agent's expertise and role.
            hints: Additional hints to guide the agent's decision making.
        """
        # Initialize strategy and config first
        self.strategy = strategy or TradingStrategy(
            name="",
            description="",
            rules="",
            tokens=[],
            chain="",
            interval_minutes=5,
            max_position_size=Decimal("0")
        )
        self.config = config
        self.portfolio = Portfolio.from_config(self.config) if config else None
        self.threshold = 1.0  # Default threshold for signal generation
        
        # Initialize tools
        base_tools = []
        if config:
            base_tools: List[AlphaSwarmToolBase] = [
                GetTokenAddress(config),
                GetTokenPrice(config),
                GetAlchemyPriceHistoryBySymbol(),
                ExecuteTokenSwap(config),
                GetCookieMetricsBySymbol()
            ]
        
        # Combine base tools with provided tools if any
        if tools:
            if isinstance(tools, dict):
                base_tools.extend(list(tools.values()))
            else:
                base_tools.extend(tools)
                
        self.tools = base_tools
        
        # Format system prompt to include required placeholders
        formatted_system_prompt = (
            "{{authorized_imports}}\n\n" +  # Required by smolagents
            (system_prompt or (
                "You are a trading expert. Analyze market conditions and "
                "generate trading signals based on your strategy. "
            )) +
            "\n\n{{managed_agents_descriptions}}\n\n" +  # Required by smolagents
            (hints or "Consider market conditions and risk management") +
            "\n\n{{available_tools}}"  # Required by smolagents
        )
        
        # Call parent class constructor with all parameters
        super().__init__(
            tools=self.tools,  # Convert back to list for parent class
            model_id=model_id,
            system_prompt=formatted_system_prompt,
            hints=hints or None
        )

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
            price_history_tool = self.tools["GetAlchemyPriceHistoryBySymbol"]
            price_history = await price_history_tool(  # Direct call, not .forward()
                symbol=token,
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
                cookie_metrics_tool = self.tools["GetCookieMetricsBySymbol"]
                market_data = await cookie_metrics_tool(  # Direct call, not .forward()
                    symbol=token,
                    interval="_3Days"
                )
                volume_change = market_data.get('volume_change_24h', 0)
            except Exception:
                volume_change = 0
            
            # Calculate strategy-specific adjustment
            strategy_adjustment = self._calculate_strategy_adjustment(
                volatility=volatility,
                volume_change=volume_change,
                strategy_rules=self.strategy.rules
            )
            
            # Apply risk management bounds
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
        """
        Calculate strategy-specific threshold adjustment based on market conditions.
        
        Args:
            volatility: Price volatility as percentage
            volume_change: Volume change percentage
            strategy_rules: Strategy type and rules description
            
        Returns:
            float: Adjustment multiplier between 0.5 and 1.5
        """
        base_adjustment = 1.0
        rules = strategy_rules.lower()
        
        # Momentum strategy adjustments
        if "momentum" in rules:
            if volatility > 5.0:
                base_adjustment *= 0.9  # More aggressive in high volatility
            elif volatility < 1.0:
                base_adjustment *= 1.1  # More conservative in low volatility
                
        # Mean reversion strategy adjustments    
        elif "reversion" in rules:
            if volatility > 5.0:
                base_adjustment *= 1.1  # More conservative in high volatility
            elif volatility < 1.0:
                base_adjustment *= 0.9  # More aggressive in low volatility
                
        # Breakout strategy adjustments
        elif "breakout" in rules:
            if volatility > 3.0:
                base_adjustment *= 0.95  # More aggressive for clear breakouts
            if abs(volume_change) > 100:
                base_adjustment *= 0.9  # More aggressive on volume spikes
                
        # Swing trading adjustments
        elif "swing" in rules:
            if 2.0 <= volatility <= 4.0:
                base_adjustment *= 0.95  # Sweet spot for swing trading
            else:
                base_adjustment *= 1.1  # More conservative outside range
                
        # Trend following adjustments
        elif "trend" in rules:
            if volatility < 2.0:
                base_adjustment *= 1.1  # More conservative in low volatility
            elif volume_change > 50:
                base_adjustment *= 0.95  # More aggressive with trend confirmation
                
        # News event trading adjustments
        elif "news" in rules:
            if abs(volume_change) > 200:
                base_adjustment *= 0.9  # More aggressive on major news
            elif volatility > 5.0:
                base_adjustment *= 0.95  # More aggressive in high impact events
                
        # Algorithmic trading adjustments
        elif "algorithmic" in rules:
            if 1.0 <= volatility <= 3.0:
                base_adjustment *= 0.95  # Optimal algorithmic conditions
            elif abs(volume_change) > 150:
                base_adjustment *= 1.1  # More conservative on unusual volume
        
        # Volume-based adjustments for all strategies
        if abs(volume_change) > 50:
            volume_factor = 1.05 if volume_change > 0 else 0.95
            base_adjustment *= volume_factor
            
        # Ensure adjustment stays within reasonable bounds
        return max(0.5, min(1.5, base_adjustment))

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