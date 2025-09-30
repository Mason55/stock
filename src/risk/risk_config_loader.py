# src/risk/risk_config_loader.py - Risk configuration loader
import logging
import yaml
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RiskConfigLoader:
    """Load and manage risk management configurations."""

    def __init__(self, config_path: str = None):
        """Initialize risk config loader.

        Args:
            config_path: Path to risk_rules.yaml config file
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()

    def _get_default_config_path(self) -> str:
        """Get default configuration path."""
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "config" / "risk_rules.yaml")

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded risk config from {self.config_path}")
            return config or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def get_risk_monitor_config(self, profile: str = None) -> Dict:
        """Get risk monitor configuration.

        Args:
            profile: Risk profile name ('conservative', 'moderate', 'aggressive')

        Returns:
            Configuration dict
        """
        if profile and profile in self.config.get('profiles', {}):
            return self.config['profiles'][profile].get('risk_monitor', {})

        return self.config.get('risk_monitor', {})

    def get_position_sizer_config(self, profile: str = None) -> Dict:
        """Get position sizer configuration.

        Args:
            profile: Risk profile name

        Returns:
            Configuration dict
        """
        if profile and profile in self.config.get('profiles', {}):
            return self.config['profiles'][profile].get('position_sizer', {})

        return self.config.get('position_sizer', {})

    def get_position_monitor_config(self) -> Dict:
        """Get position monitor configuration."""
        return self.config.get('position_monitor', {})

    def get_profile(self, profile_name: str) -> Dict:
        """Get complete risk profile configuration.

        Args:
            profile_name: Profile name

        Returns:
            Profile configuration dict
        """
        profiles = self.config.get('profiles', {})
        return profiles.get(profile_name, {})

    def list_profiles(self) -> list:
        """List available risk profiles."""
        return list(self.config.get('profiles', {}).keys())