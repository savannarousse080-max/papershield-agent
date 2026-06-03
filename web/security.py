from __future__ import annotations

import ipaddress
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Deque
from urllib.parse import urlparse


DEFAULT_MAX_UPLOAD_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_TEXT_CHARS = 60_000
DEFAULT_MAX_PARAGRAPHS = 80
DEFAULT_OPTIMIZE_REQUESTS_PER_MINUTE = 60
DEFAULT_PROVIDER_REQUESTS_PER_MINUTE = 30

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
}


@dataclass(frozen=True)
class RuntimeLimits:
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS
    max_paragraphs: int = DEFAULT_MAX_PARAGRAPHS
    optimize_requests_per_minute: int = DEFAULT_OPTIMIZE_REQUESTS_PER_MINUTE
    provider_requests_per_minute: int = DEFAULT_PROVIDER_REQUESTS_PER_MINUTE


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        events = self._events[key]
        cutoff = now - window_seconds
        while events and events[0] < cutoff:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True


def runtime_limits() -> RuntimeLimits:
    return RuntimeLimits(
        max_upload_bytes=_env_int("PAPERSHIELD_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES, 1),
        max_text_chars=_env_int("PAPERSHIELD_MAX_TEXT_CHARS", DEFAULT_MAX_TEXT_CHARS, 1),
        max_paragraphs=_env_int("PAPERSHIELD_MAX_PARAGRAPHS", DEFAULT_MAX_PARAGRAPHS, 1),
        optimize_requests_per_minute=_env_int(
            "PAPERSHIELD_OPTIMIZE_RATE_LIMIT_PER_MINUTE",
            DEFAULT_OPTIMIZE_REQUESTS_PER_MINUTE,
            0,
        ),
        provider_requests_per_minute=_env_int(
            "PAPERSHIELD_PROVIDER_RATE_LIMIT_PER_MINUTE",
            DEFAULT_PROVIDER_REQUESTS_PER_MINUTE,
            0,
        ),
    )


def runtime_policy_payload() -> dict:
    return {
        "provider_config_enabled": provider_config_enabled(),
        "admin_token_required": bool(admin_token()),
        "provider_base_url_policy": "https-only; localhost, private, link-local, multicast, and metadata hosts are blocked",
        "limits": asdict(runtime_limits()),
    }


def provider_config_enabled() -> bool:
    return _env_bool("PAPERSHIELD_PROVIDER_CONFIG_ENABLED", True)


def admin_token() -> str | None:
    value = os.environ.get("PAPERSHIELD_ADMIN_TOKEN", "").strip()
    return value or None


def validate_provider_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    if parsed.scheme != "https":
        raise ValueError("Provider base URL must use https.")
    if not parsed.hostname:
        raise ValueError("Provider base URL must include a hostname.")
    host = parsed.hostname.strip().lower()
    if _is_blocked_host(host):
        raise ValueError("Provider base URL cannot target localhost, private, link-local, or metadata hosts.")
    return normalized


def redact_secrets(message: str) -> str:
    redacted = message
    redacted = re.sub(r"Bearer\s+[^\s,;]+", "Bearer <hidden>", redacted, flags=re.IGNORECASE)
    redacted = re.sub(
        r"((?:api[_-]?key|x-api-key|authorization)['\"]?\s*[:=]\s*)['\"]?[^,'\"\s;}]+",
        r"\1<hidden>",
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(r"\b(sk-[A-Za-z0-9._-]{4,})\b", "<hidden>", redacted)
    return redacted


def count_paragraphs(text: str) -> int:
    parts = [part.strip() for part in re.split(r"\n\s*\n+", text or "") if part.strip()]
    return len(parts) or (1 if (text or "").strip() else 0)


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


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int, minimum: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)
