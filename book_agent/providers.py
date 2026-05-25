from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .utils import stable_hash


@dataclass
class LLMCallRecord:
    provider: str
    model: str
    prompt_hash: str
    output_hash: str
    prompt_tokens_estimate: int
    output_tokens_estimate: int
    cost_estimate: float
    latency_ms: int
    retry_count: int


class LLMProvider(Protocol):
    name: str
    model: str

    def generate_text(self, prompt: str) -> tuple[str, LLMCallRecord]:
        ...

    def generate_structured(self, prompt: str, schema: type | None = None) -> tuple[dict[str, Any], LLMCallRecord]:
        ...


class MockLLMProvider:
    name = "mock"
    model = "mock-local"

    def generate_text(self, prompt: str) -> tuple[str, LLMCallRecord]:
        start = time.perf_counter()
        text = "这是 mock LLM 生成的可替换文本，用于本地验证工程流程。"
        return text, self._record(prompt, text, start, 0)

    def generate_structured(self, prompt: str, schema: type | None = None) -> tuple[dict[str, Any], LLMCallRecord]:
        start = time.perf_counter()
        data = {"status": "pass", "summary": "mock structured output"}
        validate_structured_output(data, schema)
        return data, self._record(prompt, json.dumps(data, ensure_ascii=False), start, 0)

    def _record(self, prompt: str, output: str, start: float, retries: int) -> LLMCallRecord:
        return LLMCallRecord(
            provider=self.name,
            model=self.model,
            prompt_hash=stable_hash(prompt),
            output_hash=stable_hash(output),
            prompt_tokens_estimate=max(1, len(prompt) // 4),
            output_tokens_estimate=max(1, len(output) // 4),
            cost_estimate=0.0,
            latency_ms=int((time.perf_counter() - start) * 1000),
            retry_count=retries,
        )


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, api_key: str, model: str, base_url: str, timeout: int = 60, max_retries: int = 2) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries

    def generate_text(self, prompt: str) -> tuple[str, LLMCallRecord]:
        start = time.perf_counter()
        retries = 0
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        }).encode("utf-8")
        while True:
            try:
                req = urllib.request.Request(
                    self.base_url,
                    data=payload,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    body = json.loads(response.read().decode("utf-8"))
                text = body["choices"][0]["message"]["content"]
                return text, self._record(prompt, text, start, retries)
            except (urllib.error.URLError, KeyError, TimeoutError) as exc:
                if retries >= self.max_retries:
                    raise RuntimeError(f"LLM call failed after retries: {exc}") from exc
                retries += 1
                time.sleep(0.5 * retries)

    def generate_structured(self, prompt: str, schema: type | None = None) -> tuple[dict[str, Any], LLMCallRecord]:
        text, record = self.generate_text(prompt + "\n\n请只输出 JSON。")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"raw_text": text, "status": "warning"}
        validate_structured_output(data, schema)
        return data, record

    def _record(self, prompt: str, output: str, start: float, retries: int) -> LLMCallRecord:
        return LLMCallRecord(
            provider=self.name,
            model=self.model,
            prompt_hash=stable_hash(prompt),
            output_hash=stable_hash(output),
            prompt_tokens_estimate=max(1, len(prompt) // 4),
            output_tokens_estimate=max(1, len(output) // 4),
            cost_estimate=0.0,
            latency_ms=int((time.perf_counter() - start) * 1000),
            retry_count=retries,
        )


def provider_from_config(config) -> LLMProvider:
    if config.llm_provider.lower() in {"openai", "openai_compatible"} and config.openai_api_key:
        return OpenAICompatibleProvider(
            api_key=config.openai_api_key,
            model=config.openai_model,
            base_url=config.openai_base_url,
            timeout=config.job_timeout_seconds,
        )
    return MockLLMProvider()


def validate_structured_output(data: dict[str, Any], schema: Any | None = None) -> None:
    status = data.get("status")
    if status is not None and status not in {"pass", "warning", "fail"}:
        raise ValueError(f"invalid structured output status: {status}")
    if isinstance(schema, dict):
        for field in schema.get("required", []):
            if field not in data:
                data[field] = schema.get("defaults", {}).get(field)
        enums = schema.get("enums", {})
        for field, values in enums.items():
            if field in data and data[field] not in values:
                raise ValueError(f"invalid structured output enum for {field}: {data[field]}")
