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
        strategy.__init__(
            config=self.config,
            tools=[
                GetTokenAddress(self.config),
                GetTokenPrice(self.config),
                ExecuteTokenSwap(self.config),
            ],
            model_id="anthropic/claude-3-5-sonnet-20241022"
        
        )
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
            "ACTIVATE: [comma-separated list of strategies to activate]\n"
            "TRADE: [trade recommendations]\n"
        )
        
        strategy_decision = await self.base_agent.process_message(analysis_prompt)
        
        # Parse strategies to activate
        activate_line = next((line for line in strategy_decision.split('\n') 
                            if line.startswith('ACTIVATE:')), '')
        strategies_to_activate = [
            s.strip() for s in activate_line.replace('ACTIVATE:', '').strip().split(',')
            if s.strip() in self.strategies
        ]
        
        return strategies_to_activate

    async def start(self, initial_message: str = "Analyze WETH/USDC trading opportunities"):
        """Start the strategy manager with an initial message."""
        try:
            # Get initial response from base agent
            response = await self.base_agent.process_message(initial_message)
            strategies_to_activate = await self.process_strategy_response("base_agent", response)
            
            # Continuous feedback loop
            while strategies_to_activate:
                # Activate new strategies
                for strategy_name in strategies_to_activate:
                    if strategy_name not in self.active_strategies:
                        strategy = self.strategies[strategy_name]
                        agent = self.initialize_agent(strategy)
                        self.active_strategies[strategy_name] = agent
                        
                        # Get strategy's analysis
                        strategy_response = await agent.process_message(
                            "Analyze current market conditions and generate trading signals"
                        )
                        self.strategy_responses[strategy_name] = strategy_response
                        
                        # Process response to determine if more strategies needed
                        new_strategies = await self.process_strategy_response(
                            strategy_name, 
                            strategy_response
                        )
                        strategies_to_activate = [s for s in new_strategies 
                                               if s not in self.active_strategies]
                
                if not strategies_to_activate:
                    # Final analysis of all active strategies
                    combined_analysis = (
                        "=== Active Strategy Responses ===\n" +
                        "\n\n".join(f"{name}:\n{response}" 
                                  for name, response in self.strategy_responses.items())
                    )
                    await self.base_agent.process_message(combined_analysis)
                    break

        except Exception as e:
            logger.error(f"Error in strategy manager: {e}")
            raise

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