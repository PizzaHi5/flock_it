import asyncio
import logging
from typing import List
from decimal import Decimal

from alphaswarm.agent.clients import CronJobClient
from alphaswarm.config import Config

from .base.base_strategy import BaseStrategyAgent, TradingStrategy
from .momentum.momentum import MomentumStrategyAgent
from .mean_reversion.mean_reversion import MeanReversionStrategyAgent
from .breakout.breakout import BreakoutStrategyAgent
from .algorithmic.algorithmic import AlgorithmicTradingAgent
from .news.news import NewsEventTradingAgent
from .swing.swing import SwingTradingAgent
from .trend.trend import TrendFollowingAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StrategyManager:
    def __init__(self, strategies: List[BaseStrategyAgent]):
        self.strategies = strategies
        self.cron_clients: List[CronJobClient] = []

    def initialize_cron_clients(self):
        for strategy in self.strategies:
            client = CronJobClient(
                agent=strategy,
                client_id=f"{strategy.strategy.name}_client",
                interval_seconds=strategy.strategy.interval_minutes * 60,
                message_generator=strategy.get_trading_task,
                response_handler=self.handle_strategy_response
            )
            self.cron_clients.append(client)

    async def start(self):
        self.initialize_cron_clients()
        logger.info(f"Starting {len(self.cron_clients)} strategy clients")
        await asyncio.gather(
            *[client.start() for client in self.cron_clients]
        )

    def handle_strategy_response(self, response: str):
        logger.info(f"Strategy Response: {response}")
        # Add additional handling like notifications or trade execution logging

async def main():
    config = Config(network_env="test")  # Use testnet for safety
    
    # Define strategies
    momentum_strategy = TradingStrategy(
        name="eth_momentum",
        description="ETH/USDC momentum trading strategy",
        rules="Buy when short-term and long-term momentum exceed thresholds",
        tokens=["ETH", "USDC"],
        chain="ethereum_sepolia",
        interval_minutes=5,
        max_position_size=Decimal("0.1"),
        stop_loss=Decimal("0.05"),
        take_profit=Decimal("0.1")
    )

    mean_rev_strategy = TradingStrategy(
        name="eth_mean_reversion",
        description="ETH/USDC mean reversion strategy",
        rules="Buy when price is 2 standard deviations below mean, sell when 2 above",
        tokens=["ETH", "USDC"],
        chain="ethereum_sepolia",
        interval_minutes=15,
        max_position_size=Decimal("0.1"),
        stop_loss=Decimal("0.05"),
        take_profit=Decimal("0.1")
    )

    breakout_strategy = TradingStrategy(
        name="eth_breakout",
        description="ETH/USDC breakout trading strategy",
        rules="Buy on upward breakouts above resistance, sell on downward breakouts below support",
        tokens=["ETH", "USDC"],
        chain="ethereum_sepolia",
        interval_minutes=5,
        max_position_size=Decimal("0.1"),
        stop_loss=Decimal("0.05"),
        take_profit=Decimal("0.15")
    )

    algorithmic_strategy = TradingStrategy(
        name="eth_algorithmic",
        description="ETH/USDC algorithmic trading strategy",
        rules="Trade based on multiple technical indicators and weighted scoring system",
        tokens=["ETH", "USDC"],
        chain="ethereum_sepolia",
        interval_minutes=5,
        max_position_size=Decimal("0.1"),
        stop_loss=Decimal("0.05"),
        take_profit=Decimal("0.12")
    )

    news_strategy = TradingStrategy(
        name="eth_news",
        description="ETH/USDC news event trading strategy",
        rules="Trade based on significant news events and market reactions",
        tokens=["ETH", "USDC"],
        chain="ethereum_sepolia",
        interval_minutes=5,
        max_position_size=Decimal("0.15"),
        stop_loss=Decimal("0.05"),
        take_profit=Decimal("0.2")
    )

    swing_strategy = TradingStrategy(
        name="eth_swing",
        description="ETH/USDC swing trading strategy",
        rules="Trade price swings between support and resistance levels",
        tokens=["ETH", "USDC"],
        chain="ethereum_sepolia",
        interval_minutes=15,
        max_position_size=Decimal("0.1"),
        stop_loss=Decimal("0.05"),
        take_profit=Decimal("0.15")
    )

    trend_strategy = TradingStrategy(
        name="eth_trend",
        description="ETH/USDC trend following strategy",
        rules="Follow established trends using multiple technical indicators",
        tokens=["ETH", "USDC"],
        chain="ethereum_sepolia",
        interval_minutes=15,
        max_position_size=Decimal("0.1"),
        stop_loss=Decimal("0.05"),
        take_profit=Decimal("0.15")
    )

    # Create strategy agents
    strategies = [
        MomentumStrategyAgent(
            strategy=momentum_strategy,
            config=config,
            short_term_minutes=5,
            long_term_minutes=60,
            threshold=2.0
        ),
        MeanReversionStrategyAgent(
            strategy=mean_rev_strategy,
            config=config,
            lookback_periods=20,
            std_dev_threshold=2.0
        ),
        BreakoutStrategyAgent(
            strategy=breakout_strategy,
            config=config,
            lookback_periods=20,
            breakout_threshold=2.0,
            confirmation_periods=3
        ),
        AlgorithmicTradingAgent(
            strategy=algorithmic_strategy,
            config=config,
            ma_periods=[10, 20, 50],
            volatility_window=20,
            volume_window=12,
            signal_threshold=2.0
        ),
        NewsEventTradingAgent(
            strategy=news_strategy,
            config=config,
            price_impact_threshold=2.0,
            volume_surge_threshold=3.0,
            sentiment_periods=12
        ),
        SwingTradingAgent(
            strategy=swing_strategy,
            config=config,
            lookback_periods=20,
            volatility_window=14,
            support_resistance_periods=30,
            swing_threshold=2.0
        ),
        TrendFollowingAgent(
            strategy=trend_strategy,
            config=config,
            short_ma_periods=20,
            long_ma_periods=50,
            rsi_periods=14,
            rsi_threshold=30.0,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9
        )
    ]

    # Start the manager
    manager = StrategyManager(strategies)
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Shutting down strategy manager")

if __name__ == "__main__":
    asyncio.run(main()) 