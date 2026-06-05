from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import ipaddress
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str:
        ...


@dataclass
class LLMSettings:
    provider: str = "openai"
    model: str = "configured-model"
    base_url: str | None = None
    api_key: str | None = None
    temperature: float = 0.2
    timeout: int = 60
    max_retries: int = 1


class ProviderConfigError(RuntimeError):
    pass


class ExternalModelCallError(RuntimeError):
    pass


class ProviderHTTPStatusError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"LLM provider returned HTTP {status_code}: {detail}")


TRANSIENT_HTTP_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


@dataclass
class ProviderTrace:
    mode: str
    provider: str
    model: str
    external_call_required: bool = False
    external_call_attempted: bool = False
    call_count: int = 0
    elapsed_ms: int = 0
    status: str = "not_started"
    errors: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "external_call_required": self.external_call_required,
            "external_call_attempted": self.external_call_attempted,
            "call_count": self.call_count,
            "elapsed_ms": self.elapsed_ms,
            "status": self.status,
            "errors": list(self.errors or []),
        }


class TracingLLMClient:
    def __init__(self, client: LLMClient, trace: ProviderTrace):
        self.client = client
        self.trace = trace

    def complete(self, messages: list[dict[str, str]]) -> str:
        started = time.perf_counter()
        self.trace.call_count += 1
        if self.trace.external_call_required:
            self.trace.external_call_attempted = True
        try:
            result = self.client.complete(messages)
            if self.trace.status != "failed":
                self.trace.status = "success"
            return result
        except Exception as exc:
            self.trace.status = "failed"
            errors = self.trace.errors if self.trace.errors is not None else []
            errors.append(_sanitize_trace_error(str(exc)))
            self.trace.errors = errors
            raise
        finally:
            self.trace.elapsed_ms += int((time.perf_counter() - started) * 1000)

    def to_trace_payload(self) -> dict:
        if self.trace.status == "not_started":
            self.trace.status = "success" if not self.trace.external_call_required else "not_called"
        return self.trace.to_dict()


class MockLLMClient:
    """Deterministic local provider for tests, demos, and no-key smoke runs."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        content = messages[-1]["content"]
        if "BEGIN_ANALYSIS_DRAFT" in content:
            return _mock_analysis_response(_extract_analysis_text(content))
        text = _extract_draft_text(content)
        replacements = {
            "此外，": "",
            "此外": "",
            "因此，": "",
            "因此": "",
            "综上所述，": "",
            "综上所述": "",
            "值得注意的是，": "",
            "不可忽视的是，": "",
            "影响": "构成约束",
            "需要": "仍需",
            "完善": "进一步精细化",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        if "法益" not in text and "数据" in text:
            text = text.replace("数据安全", "数据安全的法益完整性")
        return text


def _extract_analysis_text(content: str) -> str:
    match = re.search(r"BEGIN_ANALYSIS_DRAFT\s*(.*?)\s*END_ANALYSIS_DRAFT", content, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.split("\n\n", 1)[-1].strip()


def _mock_analysis_response(text: str) -> str:
    paragraph_count = len([part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]) or 1
    has_citation = bool(re.search(r"\[\d+|{{REF_", text))
    payload = {
        "overview": f"当前草稿包含 {paragraph_count} 个正文段落，主题相对集中，可从论证层次、术语稳定性和引用位置三个方面继续复核。",
        "strengths": ["主题聚焦", "正文结构可识别"],
        "issues": ["模板化连接词需要压缩", "部分论断仍需补足依据"],
        "suggestions": ["优先核对核心概念与引用位置", "逐段检查是否存在新增事实"],
    }
    if has_citation:
        payload["strengths"].append("引用线索已保留")
    return json.dumps(payload, ensure_ascii=False)


def _extract_draft_text(content: str) -> str:
    match = re.search(r"BEGIN_DRAFT\s*(.*?)\s*END_DRAFT", content, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.split("\n\n", 1)[-1].strip()


def _sanitize_trace_error(message: str) -> str:
    sanitized = re.sub(r"Bearer\s+[^\s,;]+", "Bearer <hidden>", message, flags=re.IGNORECASE)
    sanitized = re.sub(
        r"((?:api[_-]?key|x-api-key|authorization)['\"]?\s*[:=]\s*)['\"]?[^,'\"\s;}]+",
        r"\1<hidden>",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r"\b(sk-[A-Za-z0-9._-]{4,})\b", "<hidden>", sanitized)
    return sanitized[:500]


class OpenAICompatibleClient:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        if not settings.api_key:
            raise ProviderConfigError("Missing API key for OpenAI-compatible provider. Set OPENAI_API_KEY or PAPERSHIELD_API_KEY.")
        self.base_url = _normalize_provider_base_url(settings.base_url or "https://api.openai.com/v1")

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": self.settings.temperature,
        }
        return _with_retries(
            lambda: _post_chat_completion(
                _build_json_request(
                    f"{self.base_url}/chat/completions",
                    payload,
                    {
                        "Authorization": f"Bearer {self.settings.api_key}",
                        "Content-Type": "application/json",
                    },
                ),
                self.settings.timeout,
            ),
            self.settings.max_retries,
        )


class AnthropicClient:
    def __init__(self, settings: LLMSettings):
        self.settings = settings
        if not settings.api_key:
            raise ProviderConfigError("Missing API key for Anthropic provider. Set ANTHROPIC_API_KEY or PAPERSHIELD_API_KEY.")
        self.base_url = _normalize_provider_base_url(settings.base_url or "https://api.anthropic.com/v1")

    def complete(self, messages: list[dict[str, str]]) -> str:
        system = "\n".join(message["content"] for message in messages if message["role"] == "system")
        user_messages = [message for message in messages if message["role"] != "system"]
        payload = {
            "model": self.settings.model,
            "system": system,
            "messages": user_messages,
            "temperature": self.settings.temperature,
            "max_tokens": 2000,
        }
        body = _with_retries(
            lambda: _post_json(
                _build_json_request(
                    f"{self.base_url}/messages",
                    payload,
                    {
                        "x-api-key": self.settings.api_key or "",
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                ),
                self.settings.timeout,
            ),
            self.settings.max_retries,
        )
        parts = body.get("content", [])
        text_parts = [part.get("text", "") for part in parts if part.get("type") == "text"]
        return "\n".join(text_parts).strip()


def _build_json_request(url: str, payload: dict, headers: dict[str, str]) -> urllib.request.Request:
    data = json.dumps(payload).encode("utf-8")
    return urllib.request.Request(url, data=data, headers=headers, method="POST")


def _post_chat_completion(request: urllib.request.Request, timeout: int) -> str:
    body = _post_json(request, timeout)
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("LLM provider returned no choices")
    content = _extract_chat_message_content(choices[0])
    if not content:
        raise RuntimeError("LLM provider returned empty message content")
    return content


def _extract_chat_message_content(choice: dict) -> str:
    message = choice.get("message") if isinstance(choice, dict) else None
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif isinstance(part, str):
                    parts.append(part)
            return "\n".join(parts).strip()
    text = choice.get("text") if isinstance(choice, dict) else None
    return text.strip() if isinstance(text, str) else ""


def _post_json(request: urllib.request.Request, timeout: int) -> dict:
    try:
        # Provider URLs are HTTPS-only and private hosts are rejected before request construction.
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            raw_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ProviderHTTPStatusError(exc.code, detail) from exc
    if not raw_body.strip():
        raise RuntimeError("LLM provider returned an empty response body")
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM provider returned a non-JSON response body") from exc


def _normalize_provider_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https":
        raise ProviderConfigError("Provider base URL must use https.")
    if not parsed.hostname:
        raise ProviderConfigError("Provider base URL must include a hostname.")
    host = parsed.hostname.strip().lower()
    if _is_blocked_host(host):
        raise ProviderConfigError("Provider base URL cannot target localhost, private, link-local, or metadata hosts.")
    return normalized


def _is_blocked_host(host: str) -> bool:
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        return True
    if host == "169.254.169.254":
        return True
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return any([
        address.is_loopback,
        address.is_private,
        address.is_link_local,
        address.is_multicast,
        address.is_reserved,
        address.is_unspecified,
    ])


def _with_retries(operation, max_retries: int):
    attempts = max(0, max_retries) + 1
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except ProviderHTTPStatusError as exc:
            if exc.status_code not in TRANSIENT_HTTP_STATUS_CODES:
                raise
            last_exc = exc
            if attempt >= attempts - 1:
                break
            time.sleep(min(0.25 * (attempt + 1), 1.0))
        except urllib.error.URLError as exc:
            last_exc = exc
            if attempt >= attempts - 1:
                break
            time.sleep(min(0.25 * (attempt + 1), 1.0))
    if last_exc is not None:
        raise RuntimeError(f"LLM provider request failed after {attempts} attempt(s): {last_exc}") from last_exc
    raise RuntimeError("LLM provider request failed")


def settings_from_env() -> LLMSettings:
    provider = os.environ.get("PAPERSHIELD_LLM_PROVIDER", "openai").lower()
    model = os.environ.get("PAPERSHIELD_LLM_MODEL") or ("mock" if provider == "mock" else "configured-model")
    base_url = os.environ.get("PAPERSHIELD_LLM_BASE_URL")
    api_key = os.environ.get("PAPERSHIELD_API_KEY")
    if provider == "openai":
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
    elif provider == "anthropic":
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    return LLMSettings(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout=_env_int("PAPERSHIELD_LLM_TIMEOUT", 60),
        max_retries=_env_int("PAPERSHIELD_LLM_MAX_RETRIES", 1),
    )


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ProviderConfigError(f"{name} must be an integer") from exc


def client_from_env() -> LLMClient:
    settings = settings_from_env()
    return client_from_settings(settings)


def client_from_settings(settings: LLMSettings) -> LLMClient:
    provider = re.sub(r"[^a-z0-9_-]", "", settings.provider)
    if provider == "mock":
        return MockLLMClient()
    if provider == "anthropic":
        return AnthropicClient(settings)
    if provider in {"openai", "openai-compatible", "compatible"}:
        return OpenAICompatibleClient(settings)
    raise ProviderConfigError(f"Unknown LLM provider: {settings.provider}")
