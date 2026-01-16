# src/strategies/strategy_loader.py - Strategy configuration loader
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional

from src.strategies.moving_average import MovingAverageCrossover
from src.strategies.mean_reversion import MeanReversion
from src.strategies.momentum import Momentum
from src.strategies.hs300_etf_rotation import HS300EtfRotation

logger = logging.getLogger(__name__)


class StrategyLoader:
    """Load and instantiate strategies from configuration."""

    # Strategy class registry
    STRATEGY_REGISTRY = {
        'moving_average_crossover': MovingAverageCrossover,
        'mean_reversion': MeanReversion,
        'momentum': Momentum,
        'hs300_etf_rotation': HS300EtfRotation,
    }

    def __init__(self, config_path: str = None):
        """Initialize strategy loader.

        Args:
            config_path: Path to strategies.yaml config file
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()

    def _get_default_config_path(self) -> str:
        """Get default configuration path."""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "config" / "strategies.yaml")

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded strategy config from {self.config_path}")
            return config or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def load_strategy(self, strategy_name: str) -> Optional[object]:
        """Load a single strategy by name.

        Args:
            strategy_name: Strategy name (e.g., 'moving_average_crossover')

        Returns:
            Strategy instance or None if not found/disabled
        """
        if strategy_name not in self.config:
            logger.error(f"Strategy config not found: {strategy_name}")
            return None

        strategy_config = self.config[strategy_name]

        # Check if enabled
        if not strategy_config.get('enabled', True):
            logger.info(f"Strategy disabled: {strategy_name}")
            return None

        # Get strategy class
        strategy_class = self.STRATEGY_REGISTRY.get(strategy_name)
        if not strategy_class:
            logger.error(f"Strategy class not found: {strategy_name}")
            return None

        # Instantiate strategy with config
        try:
            strategy = strategy_class(config=strategy_config)
            logger.info(f"Loaded strategy: {strategy_name}")
            return strategy
        except Exception as e:
            logger.error(f"Failed to instantiate strategy {strategy_name}: {e}")
            return None

    def load_strategies(self, strategy_names: List[str] = None) -> List[object]:
        """Load multiple strategies.

        Args:
            strategy_names: List of strategy names. If None, load all enabled strategies.

        Returns:
            List of strategy instances
        """
        if strategy_names is None:
            # Load all enabled strategies
            strategy_names = [
                name for name, config in self.config.items()
                if isinstance(config, dict) and config.get('enabled', True)
                and name in self.STRATEGY_REGISTRY
            ]

        strategies = []
        for name in strategy_names:
            strategy = self.load_strategy(name)
            if strategy:
                strategies.append(strategy)

        logger.info(f"Loaded {len(strategies)} strategies")
        return strategies

    def load_combination(self, combination_name: str) -> List[object]:
        """Load a predefined strategy combination.

        Args:
            combination_name: Combination name (e.g., 'conservative', 'aggressive')

        Returns:
            List of strategy instances
        """
        combinations = self.config.get('combinations', {})

        if combination_name not in combinations:
            logger.error(f"Combination not found: {combination_name}")
            return []

        strategy_names = combinations[combination_name]
        logger.info(f"Loading combination '{combination_name}': {strategy_names}")

        return self.load_strategies(strategy_names)

    def get_strategy_config(self, strategy_name: str) -> Dict:
        """Get configuration for a strategy.

        Args:
            strategy_name: Strategy name

        Returns:
            Configuration dict
        """
        return self.config.get(strategy_name, {})

    def list_available_strategies(self) -> List[str]:
        """List all available strategy names."""
        return list(self.STRATEGY_REGISTRY.keys())

    def list_enabled_strategies(self) -> List[str]:
        """List enabled strategy names from config."""
        return [
            name for name, config in self.config.items()
            if isinstance(config, dict) and config.get('enabled', True)
            and name in self.STRATEGY_REGISTRY
        ]

    def list_combinations(self) -> List[str]:
        """List available strategy combinations."""
        combinations = self.config.get('combinations', {})
        return list(combinations.keys())
