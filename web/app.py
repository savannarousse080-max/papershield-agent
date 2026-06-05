from __future__ import annotations

import importlib.util
from io import BytesIO
import os
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent.graph import optimize_text, workflow_topology
from agent.llm import (
    ExternalModelCallError,
    LLMSettings,
    MockLLMClient,
    ProviderConfigError,
    ProviderTrace,
    TracingLLMClient,
    client_from_settings,
)
from agent.nodes.assemble import build_report_dict
from agent.prompts.layer2_prompts import get_domain_config
from agent.prompts.profiles import get_prompt_profile
from utils.document_io import read_docx_bytes
from utils.report_docx import DOCX_MIME, build_report_docx_bytes
from web.provider_settings import (
    current_prompt_profile,
    current_provider_settings,
    get_provider_config_payload,
    hosted_provider_ready,
    presets_payload,
    save_provider_config,
)
from web.security import (
    SECURITY_HEADERS,
    SlidingWindowRateLimiter,
    admin_token,
    count_paragraphs,
    hosted_free_run_limit,
    provider_control_token,
    provider_config_enabled,
    redact_secrets,
    runtime_limits,
    runtime_policy_payload,
    require_admin_token_for_provider_use,
)


WEB_ROOT = Path(__file__).resolve().parent
APP_VERSION = "1.14"
_hosted_usage: dict[str, int] = {}


def create_app() -> FastAPI:
    app = FastAPI(title="PaperShield Web Demo", version=APP_VERSION)
    rate_limiter = SlidingWindowRateLimiter()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response

    app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (WEB_ROOT / "static" / "index.html").read_text(encoding="utf-8")

    @app.get("/healthz")
    def healthz() -> dict:
        settings = current_provider_settings()
        return {
            "status": "ok",
            "version": APP_VERSION,
            "provider": settings.provider,
            "prompt_profile": get_prompt_profile(current_prompt_profile()).id,
            "dependencies": {
                "python-docx": _dependency_status("docx"),
                "fastapi": _dependency_status("fastapi"),
                "langgraph": _dependency_status("langgraph"),
                "transformers": _dependency_status("transformers"),
                "torch": _dependency_status("torch"),
            },
            "compliance_mode": "local-demo",
            "security": _runtime_policy_payload(),
        }

    @app.get("/api/runtime/policy")
    def runtime_policy() -> dict:
        return _runtime_policy_payload()

    @app.get("/api/workflow/topology")
    def workflow_topology_endpoint() -> dict:
        return workflow_topology()

    @app.get("/api/provider/status")
    def provider_status() -> dict:
        return get_provider_config_payload()

    @app.get("/api/provider/presets")
    def provider_presets() -> dict:
        return presets_payload()

    @app.get("/api/provider/config")
    def provider_config() -> dict:
        return get_provider_config_payload()

    @app.post("/api/provider/session")
    def provider_session(request: Request) -> dict:
        _authorize_provider_session(request)
        return {
            "authenticated": True,
            "admin_token_required": bool(admin_token()),
            "hosted_access_authenticated": _has_hosted_access(request),
            "provider_control_authenticated": _has_provider_control(request),
            "provider_config_enabled": provider_config_enabled(),
        }

    @app.post("/api/report/docx")
    def report_docx(request: Request, payload: dict = Body(...)):
        _enforce_rate_limit(request, rate_limiter, "optimize")
        report_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
        choices = payload.get("choices") if isinstance(payload.get("choices"), dict) else {}
        try:
            content = build_report_docx_bytes(report_payload, choices)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return StreamingResponse(
            BytesIO(content),
            media_type=DOCX_MIME,
            headers={"Content-Disposition": 'attachment; filename="papershield-review.docx"'},
        )

    @app.post("/api/provider/config")
    def provider_config_save(request: Request, payload: dict = Body(...)) -> dict:
        _authorize_provider_control(request)
        _enforce_rate_limit(request, rate_limiter, "provider")
        try:
            return save_provider_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/provider/check")
    def provider_check(
        request: Request,
        provider_mode: str = Form(default="configured"),
        user_provider: str = Form(default=""),
        user_base_url: str = Form(default=""),
        user_model: str = Form(default=""),
        user_api_key: str = Form(default=""),
        user_timeout: int = Form(default=120),
        user_max_retries: int = Form(default=0),
    ) -> dict:
        normalized = provider_mode.strip().lower()
        if normalized == "mock":
            client = MockLLMClient()
            _check_llm_client(client)
            return {"status": "ready", "provider_mode": "mock", "provider": "mock", "message": "本地演示模型已就绪，无需 API key。"}
        if normalized == "hosted":
            _authorize_provider_use(request, normalized)
            _enforce_rate_limit(request, rate_limiter, "provider")
            try:
                settings = current_provider_settings()
                client = client_from_settings(settings)
                _check_llm_client(client)
                return {
                    "status": "ready",
                    "provider_mode": "hosted",
                    "provider": settings.provider,
                    "message": "Hosted provider connection succeeded.",
                }
            except ProviderConfigError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Provider check failed: {_safe_error_message(exc)}") from exc
        if normalized in {"user", "byok"}:
            _enforce_rate_limit(request, rate_limiter, "provider")
            try:
                client = _client_for_provider_mode(
                    normalized,
                    user_provider=user_provider,
                    user_base_url=user_base_url,
                    user_model=user_model,
                    user_api_key=user_api_key,
                    user_timeout=user_timeout,
                    user_max_retries=user_max_retries,
                )
                _check_llm_client(client)
                return {
                    "status": "ready",
                    "provider_mode": "user",
                    "provider": (user_provider or "openai-compatible").strip(),
                    "message": "User provider connection succeeded.",
                }
            except ProviderConfigError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Provider check failed: {_safe_error_message(exc)}") from exc
        if normalized not in {"configured", "env", "real"}:
            raise HTTPException(status_code=400, detail="provider_mode must be mock, hosted, user, configured, or env.")
        _authorize_provider_control(request)
        _enforce_rate_limit(request, rate_limiter, "provider")
        try:
            settings = current_provider_settings()
            client = client_from_settings(settings)
            _check_llm_client(client)
            return {"status": "ready", "provider_mode": normalized, "provider": settings.provider, "message": "Provider connection succeeded."}
        except ProviderConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Provider check failed: {_safe_error_message(exc)}") from exc

    @app.post("/api/optimize")
    async def optimize_endpoint(
        request: Request,
        text: str | None = Form(default=None),
        domain: str = Form(...),
        provider_mode: str = Form(default="configured"),
        analysis_only: bool = Form(default=False),
        user_provider: str = Form(default=""),
        user_base_url: str = Form(default=""),
        user_model: str = Form(default=""),
        user_api_key: str = Form(default=""),
        user_prompt_profile: str = Form(default=""),
        user_timeout: int = Form(default=120),
        user_max_retries: int = Form(default=0),
        file: UploadFile | None = File(default=None),
    ) -> dict:
        _enforce_rate_limit(request, rate_limiter, "optimize")
        try:
            get_domain_config(domain)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        raw_text = (text or "").strip()
        _validate_text_limits(raw_text)
        source_format = "txt"
        warnings: list[str] = []
        if file is not None and file.filename:
            suffix = Path(file.filename).suffix.lower()
            content = await _read_limited_upload(file)
            if suffix == ".txt":
                raw_text = content.decode("utf-8").strip()
                _validate_text_limits(raw_text)
                source_format = "txt"
            elif suffix == ".docx":
                source = read_docx_bytes(file.filename, content)
                raw_text = source.text.strip()
                _validate_text_limits(raw_text)
                source_format = source.source_format
                warnings.extend(source.warnings)
            else:
                raise HTTPException(status_code=400, detail="Web demo currently accepts text or .txt/.docx file uploads.")

        if not raw_text:
            raise HTTPException(status_code=400, detail="Provide text or .txt/.docx file input.")

        _authorize_provider_use(request, provider_mode)

        try:
            llm, provider_trace = _traced_client_for_provider_mode(
                provider_mode,
                user_provider=user_provider,
                user_base_url=user_base_url,
                user_model=user_model,
                user_api_key=user_api_key,
                user_timeout=user_timeout,
                user_max_retries=user_max_retries,
            )
        except ProviderConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        hosted_usage = None
        if provider_mode.lower() == "hosted":
            hosted_usage = _consume_hosted_usage(request)

        try:
            state = optimize_text(
                raw_text,
                domain,
                llm_client=llm,
                source_format=source_format,
                analysis_only=analysis_only,
                prompt_profile=user_prompt_profile.strip() or current_prompt_profile(),
                external_call_required=provider_trace.trace.external_call_required,
            )
            state.warnings.extend(warnings)
            payload = build_report_dict(state)
            payload["provider_trace"] = provider_trace.to_trace_payload()
            if hosted_usage:
                payload["hosted_usage"] = hosted_usage
            return payload
        except ExternalModelCallError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "error": "external_model_failed",
                    "message": f"External model workflow failed: {_safe_error_message(exc)}",
                    "provider_trace": provider_trace.to_trace_payload(),
                },
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Model workflow failed: {_safe_error_message(exc)}") from exc

    return app


def _dependency_status(module_name: str) -> str:
    return "available" if importlib.util.find_spec(module_name) else "missing"


def _runtime_policy_payload() -> dict:
    return runtime_policy_payload(hosted_model_enabled=bool(admin_token()) and hosted_provider_ready())


def _provider_status_payload(settings) -> dict:
    api_key_present = bool(settings.api_key)
    return {
        "provider": settings.provider,
        "model": settings.model,
        "prompt_profile": get_prompt_profile().id,
        "base_url_configured": bool(settings.base_url),
        "api_key_present": api_key_present,
        "configured": settings.provider == "mock" or api_key_present,
        "timeout": settings.timeout,
        "max_retries": settings.max_retries,
    }


def _safe_error_message(exc: Exception) -> str:
    message = redact_secrets(str(exc))
    for key_name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "PAPERSHIELD_API_KEY"]:
        message = message.replace(f"{key_name}=", f"{key_name}=<hidden>")
    return message


def _check_llm_client(client) -> None:
    client.complete([
        {"role": "system", "content": "Return only the revised paragraph as plain text."},
        {"role": "user", "content": "请润色以下段落，并保留引用占位符。\n\nBEGIN_DRAFT\n此外，数据安全问题需要完善{{REF_1}}。\nEND_DRAFT"},
    ])


def _authorize_provider_control(request: Request) -> None:
    if not provider_config_enabled():
        raise HTTPException(status_code=403, detail="Provider configuration is disabled for this deployment.")
    expected = provider_control_token()
    if expected and request.headers.get("X-PaperShield-Admin-Token") != expected:
        raise HTTPException(status_code=403, detail="Admin token required for provider configuration.")


def _authorize_provider_session(request: Request) -> None:
    token = request.headers.get("X-PaperShield-Admin-Token")
    access_expected = admin_token()
    control_expected = provider_control_token()
    accepted = {value for value in [access_expected, control_expected] if value}
    if accepted and token not in accepted:
        raise HTTPException(status_code=403, detail="Access token required.")


def _has_provider_control(request: Request) -> bool:
    expected = provider_control_token()
    return not expected or request.headers.get("X-PaperShield-Admin-Token") == expected


def _has_hosted_access(request: Request) -> bool:
    expected = admin_token()
    return not expected or request.headers.get("X-PaperShield-Admin-Token") == expected


def _authorize_provider_use(request: Request, provider_mode: str) -> None:
    normalized = provider_mode.strip().lower()
    if normalized in {"mock", "user", "byok"}:
        return
    if normalized == "hosted":
        if not hosted_provider_ready():
            raise HTTPException(status_code=400, detail="Hosted model is not configured for this deployment.")
        expected = admin_token()
        if not expected or request.headers.get("X-PaperShield-Admin-Token") != expected:
            raise HTTPException(status_code=403, detail="Access token required for hosted model calls.")
        return
    if not require_admin_token_for_provider_use():
        return
    expected = admin_token()
    if expected and request.headers.get("X-PaperShield-Admin-Token") != expected:
        raise HTTPException(status_code=403, detail="Admin token required for external model calls.")


def _enforce_rate_limit(request: Request, limiter: SlidingWindowRateLimiter, bucket: str) -> None:
    limits = runtime_limits()
    limit = limits.optimize_requests_per_minute if bucket == "optimize" else limits.provider_requests_per_minute
    client = request.client.host if request.client else "unknown"
    if not limiter.allow(f"{bucket}:{client}", limit):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait and try again.")


async def _read_limited_upload(file: UploadFile) -> bytes:
    max_bytes = runtime_limits().max_upload_bytes
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Uploaded file is too large. Limit: {max_bytes} bytes.")
    return content


def _validate_text_limits(raw_text: str) -> None:
    if not raw_text:
        return
    limits = runtime_limits()
    if len(raw_text) > limits.max_text_chars:
        raise HTTPException(status_code=413, detail=f"Text input is too large. Limit: {limits.max_text_chars} characters.")
    paragraph_count = count_paragraphs(raw_text)
    if paragraph_count > limits.max_paragraphs:
        raise HTTPException(status_code=413, detail=f"Too many paragraphs. Limit: {limits.max_paragraphs}.")


def _consume_hosted_usage(request: Request) -> dict:
    expected = admin_token()
    if not expected:
        raise HTTPException(status_code=403, detail="Hosted model access is not enabled for this deployment.")
    token = request.headers.get("X-PaperShield-Admin-Token", "")
    client_id = _hosted_client_id(request)
    usage_key = f"{token}:{client_id}"
    limit = hosted_free_run_limit()
    used = _hosted_usage.get(usage_key, 0)
    if limit and used >= limit:
        raise HTTPException(status_code=429, detail="Free hosted model usage limit reached. Please use your own model settings.")
    used += 1
    _hosted_usage[usage_key] = used
    remaining = max(limit - used, 0) if limit else 0
    return {"limit": limit, "used": used, "remaining": remaining}


def _hosted_client_id(request: Request) -> str:
    value = request.headers.get("X-PaperShield-Client-Id", "").strip()
    if value:
        return value[:128]
    return request.client.host if request.client else "unknown"


def _client_for_provider_mode(
    provider_mode: str,
    user_provider: str = "",
    user_base_url: str = "",
    user_model: str = "",
    user_api_key: str = "",
    user_timeout: int = 120,
    user_max_retries: int = 0,
):
    normalized = provider_mode.strip().lower()
    if normalized == "mock":
        return MockLLMClient()
    if normalized == "hosted":
        return client_from_settings(current_provider_settings())
    if normalized in {"user", "byok"}:
        settings = LLMSettings(
            provider=(user_provider or "openai-compatible").strip(),
            model=(user_model or "configured-model").strip(),
            base_url=(user_base_url or "").strip() or None,
            api_key=(user_api_key or "").strip(),
            timeout=_bounded_int(user_timeout, 120, minimum=1, maximum=300),
            max_retries=_bounded_int(user_max_retries, 0, minimum=0, maximum=3),
        )
        return client_from_settings(settings)
    if normalized in {"configured", "env", "real"}:
        return client_from_settings(current_provider_settings())
    raise HTTPException(status_code=400, detail="provider_mode must be mock, hosted, user, configured, or env.")


def _traced_client_for_provider_mode(
    provider_mode: str,
    user_provider: str = "",
    user_base_url: str = "",
    user_model: str = "",
    user_api_key: str = "",
    user_timeout: int = 120,
    user_max_retries: int = 0,
) -> tuple[TracingLLMClient, TracingLLMClient]:
    normalized = provider_mode.strip().lower()
    client = _client_for_provider_mode(
        normalized,
        user_provider=user_provider,
        user_base_url=user_base_url,
        user_model=user_model,
        user_api_key=user_api_key,
        user_timeout=user_timeout,
        user_max_retries=user_max_retries,
    )
    settings = _provider_trace_settings(
        normalized,
        user_provider=user_provider,
        user_model=user_model,
    )
    trace = ProviderTrace(
        mode=settings["mode"],
        provider=settings["provider"],
        model=settings["model"],
        external_call_required=settings["mode"] in {"hosted", "user"},
        status="not_started",
        errors=[],
    )
    traced = TracingLLMClient(client, trace)
    return traced, traced


def _provider_trace_settings(provider_mode: str, user_provider: str = "", user_model: str = "") -> dict[str, str]:
    normalized = provider_mode.strip().lower()
    if normalized == "mock":
        return {"mode": "mock", "provider": "mock", "model": "mock"}
    if normalized == "hosted":
        settings = current_provider_settings()
        return {"mode": "hosted", "provider": settings.provider, "model": settings.model}
    if normalized in {"user", "byok"}:
        return {
            "mode": "user",
            "provider": (user_provider or "openai-compatible").strip(),
            "model": (user_model or "configured-model").strip(),
        }
    settings = current_provider_settings()
    mode = "mock" if settings.provider == "mock" else "hosted"
    return {"mode": mode, "provider": settings.provider, "model": settings.model}


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    return min(parsed, maximum)


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PAPERSHIELD_WEB_PORT", "8000"))
    uvicorn.run("web.app:app", host="127.0.0.1", port=port, reload=False)
