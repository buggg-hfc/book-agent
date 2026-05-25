from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path = Path("data")
    warning_threshold: int = 3
    checkpoint_keep_recent: int = 5
    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1/chat/completions"
    openai_model: str = "gpt-4o-mini"
    job_timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            data_dir=Path(os.getenv("BOOK_AGENT_DATA_DIR", "data")),
            warning_threshold=int(os.getenv("BOOK_AGENT_WARNING_THRESHOLD", "3")),
            checkpoint_keep_recent=int(os.getenv("BOOK_AGENT_CHECKPOINT_KEEP_RECENT", "5")),
            llm_provider=os.getenv("BOOK_AGENT_LLM_PROVIDER", "mock"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            job_timeout_seconds=int(os.getenv("BOOK_AGENT_JOB_TIMEOUT_SECONDS", "120")),
        )
