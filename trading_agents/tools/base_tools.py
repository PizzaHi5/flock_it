from alphaswarm.core.tool import AlphaSwarmToolBase
from alphaswarm.config import Config
from typing import Any, Optional, TYPE_CHECKING
import logging

# Only import BaseStrategyAgent for type checking
if TYPE_CHECKING:
    from trading_agents.base.base_strategy import BaseStrategyAgent

logger = logging.getLogger(__name__)

class AnalyzeMarketConditions(AlphaSwarmToolBase):
    """Analyzes current market conditions"""

    examples = [
        "Here are some sample inputs on when to use this tool:",
        "- Analyze current market conditions for trading strategy",
        "- Get market analysis for active tokens"
    ]

    def __init__(self, strategy_agent: 'BaseStrategyAgent', *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._strategy_agent = strategy_agent

    def forward(self, strategy_name: Optional[str] = None) -> str:
        """
        Analyze current market conditions for the strategy's tokens

        Returns:
            str: Detailed analysis of current market conditions including:
                - Price trends
                - Volume analysis
                - Technical indicators
                - Market sentiment

        Parameters:
            strategy_name: Optional name of strategy to analyze for. If not provided, will analyze for all active tokens.
        """
        logger.debug(f"Analyzing market conditions for strategy: {strategy_name}")
        analysis = self._strategy_agent.analyze_market_conditions()
        logger.debug(f"Market analysis complete: {analysis[:100]}...")
        return analysis

class GenerateTradingSignals(AlphaSwarmToolBase):
    """Generates trading signals based on strategy"""

    examples = [
        "Here are some sample inputs on when to use this tool:",
        "- Generate trading signals for current market conditions",
        "- Get trading recommendations for active tokens"
    ]

    def __init__(self, strategy_agent: 'BaseStrategyAgent', *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._strategy_agent = strategy_agent

    def forward(self, min_confidence: float = 0.7) -> str:
        """
        Generate trading signals based on current market conditions

        Returns:
            str: Generated trading signals including:
                - Buy/Sell recommendations
                - Entry/Exit prices
                - Position sizes
                - Risk parameters
                - Confidence levels

        Parameters:
            min_confidence: Minimum confidence threshold for generating signals (0.0-1.0).Higher values generate more conservative signals. Default: 0.7
        """
        logger.debug(f"Generating trading signals with min_confidence: {min_confidence}")
        signals = self._strategy_agent.generate_trading_signals()
        logger.debug(f"Signal generation complete: {signals[:100]}...")
        return signals

class OptimizeParameters(AlphaSwarmToolBase):
    """Optimizes strategy parameters based on market conditions and performance"""

    examples = [
        "Here are some sample inputs on when to use this tool:",
        "- Optimize strategy parameters for current market conditions",
        "- Adjust thresholds based on volatility",
        "- Fine-tune strategy parameters for risk management"
    ]

    def __init__(self, strategy_agent: 'BaseStrategyAgent', *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._strategy_agent = strategy_agent

    def forward(
        self,
        strategy_name: Optional[str] = None,
        risk_tolerance: float = 1.0,
        market_volatility: str = "normal"
    ) -> str:
        """
        Optimize strategy parameters based on market conditions and performance metrics

        Returns:
            str: Optimization results including:
                - Updated parameter values
                - Adjustment rationale
                - Risk metrics
                - Performance impact estimates

        Parameters:
            strategy_name: Optional name of strategy to optimize. If not provided, will optimize for all active strategies.
            risk_tolerance: Risk tolerance multiplier (0.5-2.0). Higher values allow more aggressive parameters. Default: 1.0
            market_volatility: Market volatility assessment ("low", "normal", "high") used to adjust optimization bounds. Default: "normal"

        """
        logger.debug(
            f"Optimizing parameters for strategy: {strategy_name}, "
            f"risk_tolerance: {risk_tolerance}, "
            f"market_volatility: {market_volatility}"
        )
        
        self._strategy_agent.optimize_parameters()
        
        logger.debug(
            f"Parameter optimization complete. "
            f"New threshold: {self._strategy_agent.threshold}"
        )
        
        return f"Parameters optimized. New threshold: {self._strategy_agent.threshold}"