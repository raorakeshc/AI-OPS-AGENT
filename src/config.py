"""Configuration management for AI-OPS Agent application."""

import os
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, validator
import yaml


class LLMConfig(BaseModel):
    """LLM configuration model."""
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.0
    timeout: int = 30
    max_retries: int = 3

    @validator("temperature")
    def validate_temperature(cls, v: float) -> float:
        """Ensure temperature is between 0 and 2."""
        if not 0 <= v <= 2:
            raise ValueError("temperature must be between 0 and 2")
        return v


class RAGConfig(BaseModel):
    """RAG (Retrieval-Augmented Generation) configuration."""
    kb_filepath: str = "data/kb.txt"
    chunk_size: int = 200
    chunk_overlap: int = 50
    embeddings_model: str = "models/gemini-embedding-2"
    retriever_k: int = 4

    @validator("chunk_size", "chunk_overlap", "retriever_k")
    def validate_positive(cls, v: int) -> int:
        """Ensure positive integer values."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class AgentConfig(BaseModel):
    """Agent-specific configuration."""
    recursion_limit: int = 10
    feedback_filepath: str = "data/feedback.json"
    log_filepath: str = "logs/agent.log"
    thread_ttl_seconds: int = 3600

    @validator("recursion_limit", "thread_ttl_seconds")
    def validate_positive_int(cls, v: int) -> int:
        """Ensure positive integers."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class IntentConfig(BaseModel):
    """Intent detection configuration."""
    status_keywords: List[str] = Field(default_factory=list)
    kb_keywords: List[str] = Field(default_factory=list)
    order_id_pattern: str = r"\b\d{3,10}\b"
    order_id_max_length: int = 10


class ToolConfig(BaseModel):
    """Tool configuration."""
    enabled: bool = True
    timeout: int = 10


class ToolsConfig(BaseModel):
    """All tools configuration."""
    get_order_status: ToolConfig = Field(default_factory=ToolConfig)
    search_knowledge_base: ToolConfig = Field(default_factory=ToolConfig)


class AppConfig(BaseModel):
    """Application-level configuration."""
    name: str = "AI-OPS Support Agent"
    version: str = "1.0.0"
    environment: str = "production"
    debug: bool = False
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class SecurityConfig(BaseModel):
    """Security configuration."""
    sanitize_input: bool = True
    max_input_length: int = 2000
    rate_limit_per_minute: int = 60


class PerformanceConfig(BaseModel):
    """Performance tuning configuration."""
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    connection_pool_size: int = 10


class Config(BaseModel):
    """Main configuration model."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    intent: IntentConfig = Field(default_factory=IntentConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    app: AppConfig = Field(default_factory=AppConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    class Config:
        """Pydantic config."""
        validate_assignment = True


class ConfigLoader:
    """Load and manage configuration from YAML or environment."""

    _instance: Optional[Config] = None

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> Config:
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml. If None, uses default path.

        Returns:
            Loaded Config instance.

        Raises:
            FileNotFoundError: If config file not found.
            yaml.YAMLError: If YAML parsing fails.
        """
        if cls._instance is not None:
            return cls._instance

        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        try:
            with open(config_path, "r") as f:
                config_dict = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse YAML config: {e}") from e

        # Override with environment variables if present
        cls._apply_env_overrides(config_dict)

        try:
            config = Config(**config_dict)
        except ValueError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

        cls._instance = config
        return config

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None

    @classmethod
    def _apply_env_overrides(cls, config_dict: Dict[str, Any]) -> None:
        """Apply environment variable overrides to config dict."""
        env_mapping = {
            "OPENAI_API_KEY": None,  # Not stored in config
            "AGENT_ENV": ("app", "environment"),
            "AGENT_DEBUG": ("app", "debug"),
            "LLM_MODEL": ("llm", "model"),
            "LOG_LEVEL": ("logging", "level"),
        }

        for env_key, config_path in env_mapping.items():
            if env_key not in os.environ or config_path is None:
                continue

            value = os.environ[env_key]
            if len(config_path) == 2:
                section, key = config_path
                if section not in config_dict:
                    config_dict[section] = {}
                # Type conversion based on expected type
                if key == "debug":
                    value = value.lower() in ("true", "1", "yes")
                config_dict[section][key] = value


def get_config() -> Config:
    """Get or load the configuration singleton."""
    return ConfigLoader.load()
