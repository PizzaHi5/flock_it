import asyncio
import logging
from decimal import Decimal

import dotenv
from alphaswarm.config import Config

from trading_agents import StrategyManager
from trading_agents.agent_types import get_strategy_agents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    dotenv.load_dotenv()
    config = Config(network_env="test")  # Use testnet for safety
    
    # Create strategy agents using the new factory function
    strategies = get_strategy_agents(config)

    # Start the manager
    manager = StrategyManager(strategies)
    try:
        await manager.start()
    except KeyboardInterrupt:
        logger.info("Shutting down strategy manager")

if __name__ == "__main__":
    asyncio.run(main()) 