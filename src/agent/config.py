"""Configuration management for the self-improving agent."""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class ModelConfig:
    """Model configuration."""
    default: str = "llama-4-maverick"
    # Models for improvement pipeline
    analyzer: str = "llama-3.3-70b"
    versioner: str = "llama-3.3-70b"
    feedback: str = "llama-4-scout"


@dataclass
class APIConfig:
    """API keys and endpoints configuration."""
    anthropic_api_key: Optional[str] = None
    zhipu_api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> "APIConfig":
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            zhipu_api_key=os.getenv("ZHIPU_API_KEY"),
        )


@dataclass
class ThresholdConfig:
    """Threshold configuration for feedback and improvements."""
    feedback_confidence: float = 0.8
    improvement_confidence: float = 0.6


@dataclass
class PathConfig:
    """Path configuration."""
    base: Path = field(default_factory=lambda: Path(os.getenv("AGENT_BASE_PATH", "/var/www/agent")))

    @property
    def data(self) -> Path:
        return self.base / "data"

    @property
    def prompts(self) -> Path:
        return self.data / "prompts"

    @property
    def logs(self) -> Path:
        return self.data / "logs"

    @property
    def conversations(self) -> Path:
        return self.logs / "conversations"

    @property
    def improvements(self) -> Path:
        return self.logs / "improvements"


@dataclass
class Config:
    """Main configuration class."""
    models: ModelConfig = field(default_factory=ModelConfig)
    api: APIConfig = field(default_factory=APIConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            models=ModelConfig(
                default=os.getenv("DEFAULT_MODEL", "llama-4-maverick"),
                analyzer=os.getenv("ANALYZER_MODEL", "llama-3.3-70b"),
                versioner=os.getenv("VERSIONER_MODEL", "llama-3.3-70b"),
                feedback=os.getenv("FEEDBACK_MODEL", "llama-4-scout"),
            ),
            api=APIConfig.from_env(),
            thresholds=ThresholdConfig(
                feedback_confidence=float(os.getenv("FEEDBACK_CONFIDENCE_THRESHOLD", "0.8")),
                improvement_confidence=float(os.getenv("IMPROVEMENT_CONFIDENCE_THRESHOLD", "0.6")),
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Global config instance
config = Config.from_env()
