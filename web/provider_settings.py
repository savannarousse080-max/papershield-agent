from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent.llm import LLMSettings, settings_from_env
from agent.prompts.profiles import get_prompt_profile
from web.security import provider_config_enabled, validate_provider_base_url


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = APP_ROOT / "config" / "provider.local.json"
ALLOWED_PROVIDERS = {"mock", "openai", "anthropic", "openai-compatible", "compatible"}


@dataclass
class ProviderPreset:
    id: str
    label: str
    group: str
    provider: str
    base_url: str
    default_model: str
    note: str = ""


@dataclass
class WebProviderConfig:
    preset_id: str = "mock"
    provider: str = "mock"
    base_url: str = ""
    model: str = "mock"
    prompt_profile: str = "default"
    timeout: int = 120
    max_retries: int = 0


PRESET_GROUPS = [
    {
        "id": "mainland",
        "label": "国内主流",
        "presets": [
            ProviderPreset("deepseek", "DeepSeek", "mainland", "openai-compatible", "https://api.deepseek.com", "deepseek-chat"),
            ProviderPreset("qwen", "通义千问", "mainland", "openai-compatible", "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
            ProviderPreset("zhipu", "智谱 GLM", "mainland", "openai-compatible", "https://open.bigmodel.cn/api/paas/v4", "glm-4-flash"),
            ProviderPreset("kimi", "Kimi", "mainland", "openai-compatible", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
            ProviderPreset("baidu_qianfan", "百度千帆", "mainland", "openai-compatible", "https://qianfan.baidubce.com/v2", "ernie-4.0-turbo-8k"),
            ProviderPreset("tencent_hunyuan", "腾讯混元", "mainland", "openai-compatible", "https://api.hunyuan.cloud.tencent.com/v1", "hunyuan-turbos-latest"),
            ProviderPreset("volcengine_ark", "火山方舟/豆包", "mainland", "openai-compatible", "https://ark.cn-beijing.volces.com/api/v3", "your-endpoint-id", "模型字段通常填写方舟 endpoint id。"),
            ProviderPreset("minimax", "MiniMax", "mainland", "openai-compatible", "https://api.minimax.chat/v1", "MiniMax-Text-01"),
            ProviderPreset("iflytek_spark", "讯飞星火", "mainland", "openai-compatible", "https://spark-api-open.xf-yun.com/v1", "x1"),
            ProviderPreset("baichuan", "百川智能", "mainland", "openai-compatible", "https://api.baichuan-ai.com/v1", "Baichuan4"),
        ],
    },
    {
        "id": "global",
        "label": "国外御三家",
        "presets": [
            ProviderPreset("openai", "OpenAI", "global", "openai", "https://api.openai.com/v1", "gpt-4o-mini"),
            ProviderPreset("anthropic", "Anthropic", "global", "anthropic", "https://api.anthropic.com/v1", "claude-3-5-sonnet-latest"),
            ProviderPreset("gemini", "Gemini", "global", "openai-compatible", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash"),
        ],
    },
    {
        "id": "local",
        "label": "本地演示",
        "presets": [
            ProviderPreset("mock", "PaperShield Mock", "local", "mock", "", "mock", "无需 API key。"),
        ],
    },
]

PRESETS = {preset.id: preset for group in PRESET_GROUPS for preset in group["presets"]}
PERSISTED_FIELDS = {"preset_id", "provider", "base_url", "model", "prompt_profile", "timeout", "max_retries"}

_runtime_config: WebProviderConfig | None = None
_runtime_api_key: str | None = None


def presets_payload() -> dict[str, Any]:
    return {
        "groups": [
            {
                "id": group["id"],
                "label": group["label"],
                "presets": [asdict(preset) for preset in group["presets"]],
            }
            for group in PRESET_GROUPS
        ]
    }


def get_provider_config_payload() -> dict[str, Any]:
    config = _current_config()
    return _sanitized_payload(config)


def save_provider_config(payload: dict[str, Any]) -> dict[str, Any]:
    global _runtime_api_key, _runtime_config
    config = _config_from_payload(payload)
    if "api_key" in payload:
        api_key = str(payload.get("api_key") or "").strip()
        _runtime_api_key = api_key or None
    if payload.get("clear_api_key"):
        _runtime_api_key = None
    _runtime_config = config
    _persist_non_secret_config(config)
    return _sanitized_payload(config)


def current_provider_settings() -> LLMSettings:
    config = _current_config()
    api_key = _runtime_api_key or _api_key_from_env(config.provider)
    return LLMSettings(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url or None,
        api_key=api_key,
        timeout=config.timeout,
        max_retries=config.max_retries,
    )


def current_prompt_profile() -> str:
    return _current_config().prompt_profile


def reset_provider_runtime_for_tests() -> None:
    global _runtime_api_key, _runtime_config
    _runtime_api_key = None
    _runtime_config = None


def _current_config() -> WebProviderConfig:
    global _runtime_config
    if _runtime_config is None:
        if not provider_config_enabled():
            _runtime_config = _config_from_env() if _has_provider_env() else WebProviderConfig()
            return _runtime_config
        _runtime_config = _load_persisted_config() or _config_from_env()
    return _runtime_config


def _config_from_payload(payload: dict[str, Any]) -> WebProviderConfig:
    preset_id = str(payload.get("preset_id") or "custom").strip()
    preset = PRESETS.get(preset_id)
    provider = str(payload.get("provider") or (preset.provider if preset else "openai-compatible")).strip()
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    base_url = str(payload.get("base_url") or (preset.base_url if preset else "")).strip()
    if provider == "mock":
        base_url = ""
    elif provider in {"openai-compatible", "compatible"} and not base_url:
        raise ValueError("Provider base URL is required for OpenAI-compatible providers.")
    if base_url:
        base_url = validate_provider_base_url(base_url)
    model = str(payload.get("model") or (preset.default_model if preset else "")).strip()
    prompt_profile = str(payload.get("prompt_profile") or "default").strip()
    get_prompt_profile(prompt_profile)
    return WebProviderConfig(
        preset_id=preset_id,
        provider=provider,
        base_url=base_url,
        model=model,
        prompt_profile=prompt_profile,
        timeout=_bounded_int(payload.get("timeout"), 120, minimum=1, maximum=300),
        max_retries=_bounded_int(payload.get("max_retries"), 0, minimum=0, maximum=3),
    )


def _config_from_env() -> WebProviderConfig:
    if not _has_provider_env():
        return WebProviderConfig()
    settings = settings_from_env()
    prompt_profile = os.environ.get("PAPERSHIELD_PROMPT_PROFILE", "default")
    model = settings.model
    base_url = settings.base_url or ""
    if settings.provider == "mock":
        model = os.environ.get("PAPERSHIELD_LLM_MODEL", "mock")
        base_url = ""
    return WebProviderConfig(
        preset_id=_guess_preset_id(settings.provider, base_url),
        provider=settings.provider,
        base_url=base_url,
        model=model,
        prompt_profile=prompt_profile,
        timeout=settings.timeout,
        max_retries=settings.max_retries,
    )


def _has_provider_env() -> bool:
    env_names = {
        "PAPERSHIELD_LLM_PROVIDER",
        "PAPERSHIELD_LLM_MODEL",
        "PAPERSHIELD_LLM_BASE_URL",
        "PAPERSHIELD_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "PAPERSHIELD_PROMPT_PROFILE",
        "PAPERSHIELD_LLM_TIMEOUT",
        "PAPERSHIELD_LLM_MAX_RETRIES",
    }
    return any(os.environ.get(name) for name in env_names)


def _guess_preset_id(provider: str, base_url: str | None) -> str:
    if provider == "mock":
        return "mock"
    normalized = (base_url or "").rstrip("/")
    for preset in PRESETS.values():
        if preset.provider == provider and preset.base_url.rstrip("/") == normalized:
            return preset.id
    return "custom"


def _load_persisted_config() -> WebProviderConfig | None:
    path = _config_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _config_from_payload({key: value for key, value in payload.items() if key in PERSISTED_FIELDS})


def _persist_non_secret_config(config: WebProviderConfig) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: getattr(config, key) for key in PERSISTED_FIELDS}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _config_path() -> Path:
    return Path(os.environ.get("PAPERSHIELD_PROVIDER_CONFIG_PATH", str(DEFAULT_CONFIG_PATH)))


def _sanitized_payload(config: WebProviderConfig) -> dict[str, Any]:
    api_key_present = bool(_runtime_api_key or _api_key_from_env(config.provider))
    base_url_configured = bool(config.base_url)
    configured = config.provider == "mock" or (api_key_present and (config.provider != "openai-compatible" or base_url_configured))
    return {
        **asdict(config),
        "base_url_configured": base_url_configured,
        "api_key_present": api_key_present,
        "configured": configured,
        "provider_config_enabled": provider_config_enabled(),
    }


def _api_key_from_env(provider: str) -> str | None:
    api_key = os.environ.get("PAPERSHIELD_API_KEY")
    if provider == "openai":
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if provider == "anthropic":
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    return api_key


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if result < minimum:
        return default
    return min(result, maximum)
