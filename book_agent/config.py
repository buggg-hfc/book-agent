from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path = Path("data")
    database_url: str = "json://data/projects"
    vector_store_path: Path = Path("data/vector_index")
    checkpoint_dir: Path = Path("data/checkpoints")
    warning_threshold: int = 3
    fail_threshold: int = 1
    checkpoint_keep_recent: int = 5
    queue_max_workers: int = 1
    queue_poll_interval_ms: int = 250
    llm_provider: str = "openai_compatible"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1/chat/completions"
    openai_model: str = "gpt-4o-mini"
    llm_system_prompt: str = "你是一个严谨的长篇小说写作助手，输出必须可被后续审计和追踪。"
    llm_temperature: float = 0.4
    llm_max_tokens: int | None = None
    llm_max_retries: int = 2
    llm_prompt_token_cost: float = 0.0
    llm_completion_token_cost: float = 0.0
    llm_no_proxy: bool = False
    job_timeout_seconds: int = 120

    # Fields that the GUI settings modal is allowed to override
    SETTINGS_FIELDS = frozenset({
        "llm_provider", "openai_api_key", "openai_base_url", "openai_model",
        "llm_system_prompt", "llm_temperature", "llm_max_tokens",
        "llm_max_retries", "llm_prompt_token_cost", "llm_completion_token_cost",
        "llm_no_proxy",
    })

    @classmethod
    def from_env_and_file(cls, file_settings: dict) -> "AppConfig":
        """Build config from env vars, then overlay with GUI-saved settings."""
        base = cls.from_env()
        if not file_settings:
            return base
        kwargs = {
            k: getattr(base, k)
            for k in base.__dataclass_fields__  # type: ignore[attr-defined]
        }
        for key, value in file_settings.items():
            if key not in cls.SETTINGS_FIELDS:
                continue
            if value is None or value == "":
                if key == "openai_api_key":
                    kwargs[key] = None
                elif key == "llm_max_tokens":
                    kwargs[key] = None
            elif key == "llm_temperature":
                kwargs[key] = float(value)
            elif key in {"llm_max_retries"}:
                kwargs[key] = int(value)
            elif key in {"llm_max_tokens"}:
                kwargs[key] = int(value)
            elif key in {"llm_prompt_token_cost", "llm_completion_token_cost"}:
                kwargs[key] = float(value)
            elif key == "llm_no_proxy":
                kwargs[key] = bool(value)
            else:
                kwargs[key] = value
        return cls(**kwargs)

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            data_dir=Path(os.getenv("BOOK_AGENT_DATA_DIR", "data")),
            database_url=os.getenv("BOOK_AGENT_DATABASE_URL", "json://data/projects"),
            vector_store_path=Path(os.getenv("BOOK_AGENT_VECTOR_STORE_PATH", "data/vector_index")),
            checkpoint_dir=Path(os.getenv("BOOK_AGENT_CHECKPOINT_DIR", "data/checkpoints")),
            warning_threshold=int(os.getenv("BOOK_AGENT_WARNING_THRESHOLD", "3")),
            fail_threshold=int(os.getenv("BOOK_AGENT_FAIL_THRESHOLD", "1")),
            checkpoint_keep_recent=int(os.getenv("BOOK_AGENT_CHECKPOINT_KEEP_RECENT", "5")),
            queue_max_workers=int(os.getenv("BOOK_AGENT_QUEUE_MAX_WORKERS", "1")),
            queue_poll_interval_ms=int(os.getenv("BOOK_AGENT_QUEUE_POLL_INTERVAL_MS", "250")),
            llm_provider=os.getenv("BOOK_AGENT_LLM_PROVIDER", "openai_compatible"),
            openai_api_key=os.getenv("BOOK_AGENT_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv(
                "BOOK_AGENT_LLM_BASE_URL",
                os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
            ),
            openai_model=os.getenv("BOOK_AGENT_LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
            llm_system_prompt=os.getenv(
                "BOOK_AGENT_LLM_SYSTEM_PROMPT",
                "你是一个严谨的长篇小说写作助手，输出必须可被后续审计和追踪。",
            ),
            llm_temperature=float(os.getenv("BOOK_AGENT_LLM_TEMPERATURE", "0.4")),
            llm_max_tokens=(
                int(os.getenv("BOOK_AGENT_LLM_MAX_TOKENS"))
                if os.getenv("BOOK_AGENT_LLM_MAX_TOKENS")
                else None
            ),
            llm_max_retries=int(os.getenv("BOOK_AGENT_LLM_MAX_RETRIES", "2")),
            llm_prompt_token_cost=float(os.getenv("BOOK_AGENT_LLM_PROMPT_TOKEN_COST", "0")),
            llm_completion_token_cost=float(os.getenv("BOOK_AGENT_LLM_COMPLETION_TOKEN_COST", "0")),
            llm_no_proxy=os.getenv("BOOK_AGENT_LLM_NO_PROXY", "").lower() in {"1", "true", "yes"},
            job_timeout_seconds=int(os.getenv("BOOK_AGENT_JOB_TIMEOUT_SECONDS", "120")),
        )
