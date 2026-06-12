"""
Centralized configuration management using Pydantic-Settings.
All tunables in one place — no magic strings scattered across the codebase.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OllamaConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OLLAMA_")

    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 120
    max_retries: int = 3

    # Use base model names — Ollama resolves :latest automatically
    planner_model:   str = "mistral"
    analyst_model:   str = "mistral"
    drafter_model:   str = "mistral"
    critic_model:    str = "mistral"
    hermes_model:    str = "mistral"
    embedding_model: str = "nomic-embed-text"


class ChromaConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHROMA_")

    persist_directory: Path = Path("./data/chroma")
    collection_name: str = "gov_policy_memory"
    distance_metric: Literal["cosine", "l2", "ip"] = "cosine"
    top_k_results: int = 5


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_")

    max_negotiation_rounds: int = 3
    compliance_threshold: float = 75.0   # Score below this triggers re-draft
    max_replanning_attempts: int = 2
    temperature: float = 0.1             # Low for determinism in gov docs
    seed: int = 42


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Gov AI Multi-Agent Assistant"
    version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    data_dir: Path = Path("./data")

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    chroma: ChromaConfig = Field(default_factory=ChromaConfig)
    agent:  AgentConfig  = Field(default_factory=AgentConfig)

    @field_validator("data_dir")
    @classmethod
    def create_data_dir(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Singleton config accessor — import and call this everywhere."""
    return AppConfig()