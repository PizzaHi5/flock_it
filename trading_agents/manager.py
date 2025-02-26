import asyncio
import logging
from typing import List, Callable, Awaitable, Dict
from decimal import Decimal

from alphaswarm.agent.clients import CronJobClient
from alphaswarm.config import Config
from alphaswarm.tools.core import GetUsdPrice, GetTokenAddress
from alphaswarm.tools.exchanges import GetTokenPrice, ExecuteTokenSwap
from alphaswarm.tools.alchemy import (
    GetAlchemyPriceHistoryBySymbol,
    GetAlchemyPriceHistoryByAddress
)
from alphaswarm.tools.cookie import (
    GetCookieMetricsBySymbol,
    GetCookieMetricsByContract,
    GetCookieMetricsByTwitter,
    GetCookieMetricsPaged
)
from alphaswarm.tools.strategy_analysis import AnalyzeTradingStrategy, Strategy
from alphaswarm.agent.agent import AlphaSwarmAgent

from trading_agents.base.base_strategy import BaseStrategyAgent
from trading_agents.agent_types import get_strategy_agents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyManager:
    def __init__(self, agent_strategies: Dict[str, BaseStrategyAgent]):
        # Initialize config
        self.config = Config(network_env="test")
        
        # Initialize base agent
        self.base_agent = AlphaSwarmAgent(
            tools=[
                GetTokenAddress(self.config),
                GetTokenPrice(self.config),
                ExecuteTokenSwap(self.config),
            ],
            model_id="anthropic/claude-3-5-sonnet-20241022"
        )
        
        # Store strategies directly
        self.strategies = agent_strategies
        self.active_strategies = {}
        self.strategy_responses = {}

    def initialize_agent(self, strategy: BaseStrategyAgent) -> BaseStrategyAgent:
        """Initialize the given strategy agent."""
        # Get the strategy parameters
        original_params = {
            'strategy': strategy.strategy,
            'config': self.config,
            'system_prompt': strategy.system_prompt,
            'hints': strategy.hints,
            # Add any strategy-specific parameters
            **{k: v for k, v in strategy.__dict__.items() 
               if k not in [
                   'strategy', 'config', 'system_prompt', 'hints', 'portfolio', 'tools',
                   # Base strategy attributes
                   '_agent', '_llm_function', 'model_id',
                   # Momentum strategy attributes
                   'short_term_minutes', 'long_term_minutes', 'threshold',
                   # Mean reversion attributes
                   'lookback_periods', 'std_dev_threshold',
                   # Breakout attributes
                   'breakout_threshold', 'confirmation_periods',
                   # Algorithmic attributes
                   'ma_periods', 'volatility_window', 'volume_window', 'signal_threshold',
                   # News attributes
                   'price_impact_threshold', 'volume_surge_threshold', 'sentiment_periods',
                   # Swing attributes
                   'support_resistance_periods', 'swing_threshold',
                   # Trend attributes
                   'short_ma_periods', 'long_ma_periods', 'rsi_periods', 'rsi_threshold',
                   'macd_fast', 'macd_slow', 'macd_signal'
               ]}
        }
        
        # Reinitialize with original parameters
        strategy.__init__(**original_params)
        return strategy

    async def process_strategy_response(self, strategy_name: str, response: str) -> List[str]:
        """Process a strategy's response and determine if more strategies should be activated"""
        
        analysis_prompt = (
            f"=== Strategy Response ({strategy_name}) ===\n"
            f"{response}\n\n"
            "Available strategies: momentum, mean_reversion, breakout, algorithmic, news, swing, trend\n\n"
            "Based on this response:\n"
            "1. Should additional trading strategies be activated? If so, which ones?\n"
            "2. What trading actions should be taken?\n"
            "Respond in a structured format:\n"
            "ACTIVATE: [comma-separated list of strategies to activate] (Example: ACTIVATE:momentum,mean_reversion,trend)\n"
            "TRADE: [trade recommendations]\n"
            "REASON: [explanation for the activation of the strategies and trade recommendations]\n"
        )
        
        strategy_decision = await self.base_agent.process_message(analysis_prompt)
        
        # Extract strategies from the response
        strategies_to_activate = extract_strategies(strategy_decision)
        
        return strategies_to_activate

    async def start(self, initial_message: str):
        """Start the strategy manager with an initial message."""
        try:
            # Get initial response from base agent
            response = await self.base_agent.process_message(initial_message)
            strategies_to_activate = await self.process_strategy_response("base_agent", response)
            
            print("Strategies to activate:\n", strategies_to_activate)

            # Single pass activation of strategies
            for strategy_name in strategies_to_activate:
                if strategy_name not in self.active_strategies:
                    agent = self.strategies[strategy_name]
                    self.active_strategies[strategy_name] = agent
                    print("Made agent:\n", agent)
                    
                    # Build context-rich message including previous responses
                    strategy_context = (
                        f"=== Previous Analysis ===\n{response}\n\n"
                        f"=== Strategy Configuration ===\n"
                        f"Strategy: {agent.strategy.name}\n"
                        f"Description: {agent.strategy.description}\n"
                        f"Rules: {agent.strategy.rules}\n"
                        f"Tokens: {agent.strategy.tokens}\n"
                        f"Chain: {agent.strategy.chain}\n"
                        f"Interval: {agent.strategy.interval_minutes} minutes\n"
                        f"Max Position Size: {agent.strategy.max_position_size}\n"
                        f"Stop Loss: {agent.strategy.stop_loss}\n"
                        f"Take Profit: {agent.strategy.take_profit}\n\n"
                        """
                        Based on this context, analyze current market conditions 
                        and generate trading signals specific to your strategy.
                        You should respond with a list of trades to make, and the reasoning behind them.
                        TRADE: [comma-separated list of trades to make] (Example: TRADE:SELL 1 WETH for USDC, BUY 0.02 USDC for WETH)
                        REASON: [explanation for the trades and reasoning behind them]
                        """
                    )
                    
                    # Get strategy's analysis with full context
                    strategy_response = await agent.process_message(strategy_context)
                    self.strategy_responses[strategy_name] = strategy_response
            
            # Final analysis of all active strategies
            combined_analysis = (
                "=== Active Strategy Responses ===\n" +
                "\n\n".join(f"{name}:\n{response}" 
                            for name, response in self.strategy_responses.items())
            )

            summary_prompt = (
                f"=== Summary of Active Strategies ===\n"
                f"{combined_analysis}\n\n"
                "Based on this summary, provide a concise overview of the current market conditions and trading opportunities."
                "You should respond with a list of all trades to make from all strategies and the reasoning behind each trade."
                "TRADE: [comma-separated list of trades to make] (Example: TRADE:SELL 1 WETH for USDC, BUY 0.02 USDC for WETH)"
                "REASON: [explanation for the trades and reasoning behind them]"
            )

            await self.base_agent.process_message(summary_prompt)

        except Exception as e:
            logger.error(f"Error in strategy manager: {e}")
            raise

def extract_strategies(text: str) -> list[str]:
    """
    Extract strategies from a string containing 'ACTIVATE:' followed by comma-separated values.
    
    Args:
        text (str): Input text containing 'ACTIVATE:' followed by strategies
        
    Returns:
        list[str]: List of strategy names, cleaned and stripped
    
    Example:
        >>> text = "Some text\nACTIVATE:momentum,mean_reversion,trend\nMore text"
        >>> extract_strategies(text)
        ['momentum', 'mean_reversion', 'trend']
    """
    # Find the line containing ACTIVATE:
    for line in text.split('\n'):
        if line.upper().startswith('ACTIVATE:'):
            # Get everything after ACTIVATE:, strip common delimiters, and split on commas
            strategies = line.split(':', 1)[1].strip('[](){}"\'` \t\n').split(',')
            # Clean up each strategy name
            return [strategy.strip() for strategy in strategies]
    
    return []  # Return empty list if no ACTIVATE: found

async def main():
    config = Config(network_env="test")
    
    # Get strategy agents
    agents_strategies = get_strategy_agents(config)

    # Start the manager with initial analysis
    manager = StrategyManager(agents_strategies)
    try:
        await manager.start("Analyze ETH/USDC trading opportunities on Ethereum Sepolia")
    except KeyboardInterrupt:
        logger.info("Shutting down strategy manager")

if __name__ == "__main__":
    asyncio.run(main())