from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .utils import stable_hash


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from LLM output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


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

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[str, LLMCallRecord]:
        ...

    def generate_structured(
        self,
        prompt: str,
        schema: Any | None = None,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[dict[str, Any], LLMCallRecord]:
        ...


class MockLLMProvider:
    name = "mock"
    model = "mock-local"

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[str, LLMCallRecord]:
        start = time.perf_counter()
        text = "这是 mock LLM 生成的可替换文本，用于本地验证工程流程。"
        return text, self._record(prompt, text, start, 0)

    def generate_structured(
        self,
        prompt: str,
        schema: Any | None = None,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[dict[str, Any], LLMCallRecord]:
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

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: int = 60,
        max_retries: int = 2,
        system_prompt: str | None = None,
        temperature: float = 0.4,
        max_tokens: int | None = None,
        prompt_token_cost: float = 0.0,
        completion_token_cost: float = 0.0,
        no_proxy: bool = False,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.prompt_token_cost = prompt_token_cost
        self.completion_token_cost = completion_token_cost
        self.no_proxy = no_proxy

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[str, LLMCallRecord]:
        return self._chat_completion(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
            on_token=on_token,
        )

    def _open_url(self, req: urllib.request.Request):
        if self.no_proxy:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            return opener.open(req, timeout=self.timeout)
        return urllib.request.urlopen(req, timeout=self.timeout)

    def _chat_completion(
        self,
        prompt: str,
        *,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        json_mode: bool,
        on_token: Callable[[str], None] | None = None,
    ) -> tuple[str, LLMCallRecord]:
        start = time.perf_counter()
        retries = 0
        messages = []
        effective_system_prompt = system_prompt if system_prompt is not None else self.system_prompt
        if effective_system_prompt:
            messages.append({"role": "system", "content": effective_system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload_dict: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        effective_max_tokens = self.max_tokens if max_tokens is None else max_tokens
        if effective_max_tokens is not None:
            payload_dict["max_tokens"] = effective_max_tokens
        if json_mode:
            payload_dict["response_format"] = {"type": "json_object"}
        payload = json.dumps(payload_dict).encode("utf-8")
        while True:
            try:
                req = urllib.request.Request(
                    self.base_url,
                    data=payload,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    method="POST",
                )
                chunks: list[str] = []
                usage: dict[str, Any] | None = None
                with self._open_url(req) as response:
                    for raw_line in response:
                        line = raw_line.decode("utf-8").rstrip("\n\r")
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_obj = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if chunk_obj.get("usage"):
                            usage = chunk_obj["usage"]
                        delta = (chunk_obj.get("choices") or [{}])[0].get("delta", {})
                        token = delta.get("content") or ""
                        if token:
                            chunks.append(token)
                            if on_token is not None:
                                try:
                                    on_token(token)
                                except Exception:
                                    pass
                text = strip_think_tags("".join(chunks))
                return text, self._record(prompt, text, start, retries, usage)
            except (urllib.error.URLError, KeyError, TimeoutError) as exc:
                if retries >= self.max_retries:
                    raise RuntimeError(f"LLM call failed after retries: {exc}") from exc
                retries += 1
                time.sleep(0.5 * retries)

    def generate_structured(
        self,
        prompt: str,
        schema: Any | None = None,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[dict[str, Any], LLMCallRecord]:
        text, record = self._chat_completion(
            prompt + "\n\n请只输出 JSON，不要输出 Markdown 代码块。",
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            data = parse_json_output(text)
        except json.JSONDecodeError:
            data = {"raw_text": text, "status": "warning"}
        validate_structured_output(data, schema)
        return data, record

    def _record(self, prompt: str, output: str, start: float, retries: int, usage: dict[str, Any] | None = None) -> LLMCallRecord:
        prompt_tokens = int((usage or {}).get("prompt_tokens") or max(1, len(prompt) // 4))
        output_tokens = int((usage or {}).get("completion_tokens") or max(1, len(output) // 4))
        return LLMCallRecord(
            provider=self.name,
            model=self.model,
            prompt_hash=stable_hash(prompt),
            output_hash=stable_hash(output),
            prompt_tokens_estimate=prompt_tokens,
            output_tokens_estimate=output_tokens,
            cost_estimate=(prompt_tokens / 1000 * self.prompt_token_cost) + (output_tokens / 1000 * self.completion_token_cost),
            latency_ms=int((time.perf_counter() - start) * 1000),
            retry_count=retries,
        )


def provider_from_config(config) -> LLMProvider:
    import warnings as _warnings
    if config.llm_provider.lower() in {"openai", "openai_compatible"}:
        if config.openai_api_key:
            return OpenAICompatibleProvider(
                api_key=config.openai_api_key,
                model=config.openai_model,
                base_url=config.openai_base_url,
                timeout=config.job_timeout_seconds,
                max_retries=config.llm_max_retries,
                system_prompt=config.llm_system_prompt,
                temperature=config.llm_temperature,
                max_tokens=config.llm_max_tokens,
                prompt_token_cost=config.llm_prompt_token_cost,
                completion_token_cost=config.llm_completion_token_cost,
                no_proxy=getattr(config, "llm_no_proxy", False),
            )
        _warnings.warn(
            "BOOK_AGENT_LLM_PROVIDER is set to openai_compatible but no API key found. "
            "Falling back to MockLLMProvider. Set BOOK_AGENT_LLM_API_KEY or OPENAI_API_KEY.",
            RuntimeWarning,
            stacklevel=2,
        )
    return MockLLMProvider()


def parse_json_output(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


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
