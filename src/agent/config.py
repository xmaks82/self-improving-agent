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
    # Main agent model (can be claude-* or glm-*)
    default: str = "claude-opus-4.5"  # Best Anthropic model
    # Models for improvement pipeline
    analyzer: str = "claude-sonnet"
    versioner: str = "claude-sonnet"
    feedback: str = "claude-haiku"

    def get_provider(self, model: Optional[str] = None) -> str:
        """Get provider name for a model."""
        m = model or self.default
        if m.startswith("glm"):
            return "zhipu"
        return "anthropic"


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
    base: Path = field(default_factory=lambda: Path("/var/www/agent"))

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
                default=os.getenv("DEFAULT_MODEL", "claude-opus-4.5"),
                analyzer=os.getenv("ANALYZER_MODEL", "claude-sonnet"),
                versioner=os.getenv("VERSIONER_MODEL", "claude-sonnet"),
                feedback=os.getenv("FEEDBACK_MODEL", "claude-haiku"),
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
