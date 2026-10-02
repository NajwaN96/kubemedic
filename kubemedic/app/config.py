"""Runtime settings. API keys are read from the environment and never logged."""

import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KUBEMEDIC_",
        env_file=".env",
        extra="ignore",
    )

    namespace: str = "taskflow"
    incident_cooldown_seconds: int = 300
    event_freshness_seconds: int = 300
    recovery_stabilization_seconds: int = 60
    log_tail_lines: int = 100
    max_log_chars: int = 12000
    demo_mode: bool = False
    db_path: str = "data/kubemedic.db"
    watch_enabled: bool = True
    service_name: str = "kubemedic"
    ai_enabled: bool = False
    ai_provider: str = "openai"
    ai_timeout_seconds: float = 20
    ai_max_output_tokens: int = 700
    ai_max_log_lines: int = 40
    ai_max_events: int = 8
    ai_max_payload_bytes: int = 12000
    ai_transient_retries: int = 1
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    remediation_enabled: bool = False
    remediation_max_replicas: int = 5
    remediation_verify_seconds: int = 120
    remediation_poll_seconds: int = 5

    @model_validator(mode="before")
    @classmethod
    def _openai_environment(cls, data):
        """OPENAI_API_KEY and OPENAI_MODEL are unprefixed on purpose."""
        if not isinstance(data, dict):
            return data
        merged = dict(data)
        if "openai_api_key" not in merged and os.environ.get("OPENAI_API_KEY"):
            merged["openai_api_key"] = os.environ["OPENAI_API_KEY"]
        if "openai_model" not in merged and os.environ.get("OPENAI_MODEL"):
            merged["openai_model"] = os.environ["OPENAI_MODEL"]
        return merged
