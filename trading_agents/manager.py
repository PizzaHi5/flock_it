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

from .base.base_strategy import BaseStrategyAgent, TradingStrategy
from .momentum.momentum import MomentumStrategyAgent
from .mean_reversion.mean_reversion import MeanReversionStrategyAgent
from .breakout.breakout import BreakoutStrategyAgent
from .algorithmic.algorithmic import AlgorithmicTradingAgent
from .news.news import NewsEventTradingAgent
from .swing.swing import SwingTradingAgent
from .trend.trend import TrendFollowingAgent
from .agent_types import create_strategy_agents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyManager:
    def __init__(self, agent_strategies: List[BaseStrategyAgent]):
        # Initialize config
        self.config = Config(network_env="test")
        
        # Initialize strategy analysis
        self.strategy = Strategy(
            rules="Multi-strategy trading system using momentum, mean reversion, breakout, and algorithmic signals",
            model_id="anthropic/claude-3-5-sonnet-20241022"
        )
        
        # Initialize all available tools
        self.tools = {
            "GetUsdPrice": GetUsdPrice(),
            "GetTokenAddress": GetTokenAddress(self.config),
            "GetTokenPrice": GetTokenPrice(self.config),
            "ExecuteTokenSwap": ExecuteTokenSwap(self.config),
            "GetAlchemyPriceHistoryBySymbol": GetAlchemyPriceHistoryBySymbol(),
            "GetAlchemyPriceHistoryByAddress": GetAlchemyPriceHistoryByAddress(),
            "GetCookieMetricsBySymbol": GetCookieMetricsBySymbol(),
            "GetCookieMetricsByContract": GetCookieMetricsByContract(),
            "GetCookieMetricsByTwitter": GetCookieMetricsByTwitter(),
            "GetCookieMetricsPaged": GetCookieMetricsPaged(),
            "AnalyzeTradingStrategy": AnalyzeTradingStrategy(self.strategy)
        }
        
        # Initialize each strategy with tools
        self.strategies = []
        for strategy in agent_strategies:
            strategy_with_tools = strategy.__class__(
                strategy=strategy.strategy,
                config=self.config,
                tools=list(self.tools.values()),  # Pass tools as a list
                model_id="anthropic/claude-3-5-sonnet-20241022"
            )
            self.strategies.append(strategy_with_tools)
            
        self.active_strategies = self.strategies
        self.strategy_signals = {}
        
        self.cron_clients: List[CronJobClient] = []

    def initialize_cron_clients(self):
        """Initialize cron clients for active strategies"""
        self.cron_clients = []
        for strategy in self.active_strategies:
            client = CronJobClient(
                agent=strategy,
                client_id=f"{strategy.strategy.name}_client",
                interval_seconds=strategy.strategy.interval_minutes * 60,
                message_generator=lambda s=strategy: s.get_trading_task(),
                response_handler=lambda response, s=strategy: self._handle_strategy_response(response, s)
            )
            self.cron_clients.append(client)

    def _handle_strategy_response(self, response: str, strategy: BaseStrategyAgent):
        """Handle individual strategy responses"""
        self.strategy_signals[strategy.strategy.name] = response
        logger.info(f"Strategy Response from {strategy.strategy.name}: {response}")

    async def evaluate_strategies(self, market_prompt: str) -> List[BaseStrategyAgent]:
        """Use LLM to evaluate which strategies to activate based on market conditions"""
        
        strategy_analysis = self.tools["AnalyzeTradingStrategy"].forward(
            token_data=market_prompt
        )
        
        # Parse strategy recommendations
        selected_strategies = []
        for strategy in self.strategies:
            strategy_name = strategy.strategy.name.lower()
            
            # Check if strategy type is recommended
            if any(strat_type in strategy_name for strat_type in 
                  ["momentum" if "momentum" in strategy_analysis.recommended_strategies else "",
                   "reversion" if "mean_reversion" in strategy_analysis.recommended_strategies else "",
                   "breakout" if "breakout" in strategy_analysis.recommended_strategies else "",
                   "algorithmic" if "algorithmic" in strategy_analysis.recommended_strategies else "",
                   "news" if "news" in strategy_analysis.recommended_strategies else "",
                   "swing" if "swing" in strategy_analysis.recommended_strategies else "",
                   "trend" if "trend" in strategy_analysis.recommended_strategies else ""]):
                selected_strategies.append(strategy)
                
        return selected_strategies

    async def process_strategy_signals(self):
        """Process signals from active strategies and make trading decisions"""
        combined_signals = []
        
        for strategy in self.active_strategies:
            signal = self.strategy_signals.get(strategy.strategy.name)
            if signal:
                combined_signals.append(
                    f"=== {strategy.strategy.name} ===\n{signal}"
                )
                
        if not combined_signals:
            return
            
        # Analyze combined signals with LLM
        analysis_prompt = (
            "=== Combined Strategy Signals ===\n" +
            "\n\n".join(combined_signals) +
            "\n\nAnalyze the above signals and recommend:\n"
            "1. Which strategies to continue monitoring\n"
            "2. Which strategies to deactivate\n"
            "3. Whether to execute any trades\n"
            "4. Risk management considerations"
        )
        
        strategy_decision = self.tools["AnalyzeTradingStrategy"].forward(
            token_data=analysis_prompt
        )
        
        # Update active strategies based on recommendations
        self.active_strategies = await self.evaluate_strategies(strategy_decision.analysis)
        
        # Execute any recommended trades
        trades = getattr(strategy_decision, 'trade_recommendations', None)
        if trades:
            await self._execute_trades(trades)

    async def start(self, initial_market_prompt: str = ""):
        """Start the strategy manager with an optional initial market analysis prompt."""
        if not initial_market_prompt:
            initial_market_prompt = await self._generate_default_market_analysis()
            
        # Initialize strategy signals
        for strategy in self.active_strategies:
            market_conditions = await strategy.analyze_market_conditions()
            self.strategy_signals[strategy.strategy.name] = market_conditions
            
        # Process initial signals
        await self.process_strategy_signals()
        
    async def _generate_default_market_analysis(self) -> str:
        """Generate a default market analysis prompt."""
        conditions = []
        for strategy in self.active_strategies:
            conditions.append(await strategy.analyze_market_conditions())
        return "\n\n".join(conditions)

    async def _execute_trades(self, trade_recommendations: List[dict]):
        """Execute recommended trades"""
        for trade in trade_recommendations:
            try:
                await self.tools["ExecuteTokenSwap"].forward(**trade)
                logger.info(f"Executed trade: {trade}")
            except Exception as e:
                logger.error(f"Trade execution failed: {e}")

async def main():
    config = Config(network_env="test")
    
    # Create strategy agents
    strategies = create_strategy_agents(config)

    # Start the manager with initial analysis
    manager = StrategyManager(strategies)
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Shutting down strategy manager")

if __name__ == "__main__":
    asyncio.run(main()) 