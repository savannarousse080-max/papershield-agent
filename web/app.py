from __future__ import annotations

import importlib.util
from io import BytesIO
import os
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent.graph import optimize_text, workflow_topology
from agent.llm import MockLLMClient, ProviderConfigError, client_from_settings
from agent.nodes.assemble import build_report_dict
from agent.prompts.layer2_prompts import get_domain_config
from agent.prompts.profiles import get_prompt_profile
from utils.document_io import read_docx_bytes
from utils.report_docx import DOCX_MIME, build_report_docx_bytes
from web.provider_settings import (
    current_prompt_profile,
    current_provider_settings,
    get_provider_config_payload,
    presets_payload,
    save_provider_config,
)
from web.security import (
    SECURITY_HEADERS,
    SlidingWindowRateLimiter,
    admin_token,
    count_paragraphs,
    provider_config_enabled,
    redact_secrets,
    runtime_limits,
    runtime_policy_payload,
)


WEB_ROOT = Path(__file__).resolve().parent
APP_VERSION = "1.11"


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
            "security": runtime_policy_payload(),
        }

    @app.get("/api/runtime/policy")
    def runtime_policy() -> dict:
        return runtime_policy_payload()

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
        _authorize_provider_control(request)
        return {
            "authenticated": True,
            "admin_token_required": bool(admin_token()),
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
    def provider_check(request: Request, provider_mode: str = Form(default="configured")) -> dict:
        normalized = provider_mode.lower()
        if normalized == "mock":
            client = MockLLMClient()
            client.complete([{"role": "user", "content": "请回复 ok。\n\nok"}])
            return {"status": "ready", "provider": "mock", "message": "本地演示模型已就绪，无需 API key。"}
        if normalized not in {"configured", "env", "real"}:
            raise HTTPException(status_code=400, detail="provider_mode must be mock, configured, or env.")
        _authorize_provider_control(request)
        _enforce_rate_limit(request, rate_limiter, "provider")
        try:
            settings = current_provider_settings()
            client = client_from_settings(settings)
            client.complete([
                {"role": "system", "content": "Reply with ok only."},
                {"role": "user", "content": "ok"},
            ])
            return {"status": "ready", "provider": settings.provider, "message": "Provider connection succeeded."}
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
            llm = _client_for_provider_mode(provider_mode)
        except ProviderConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        state = optimize_text(
            raw_text,
            domain,
            llm_client=llm,
            source_format=source_format,
            analysis_only=analysis_only,
            prompt_profile=current_prompt_profile(),
        )
        state.warnings.extend(warnings)
        return build_report_dict(state)

    return app


def _dependency_status(module_name: str) -> str:
    return "available" if importlib.util.find_spec(module_name) else "missing"


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


def _authorize_provider_control(request: Request) -> None:
    if not provider_config_enabled():
        raise HTTPException(status_code=403, detail="Provider configuration is disabled for this deployment.")
    expected = admin_token()
    if expected and request.headers.get("X-PaperShield-Admin-Token") != expected:
        raise HTTPException(status_code=403, detail="Admin token required for provider configuration.")


def _authorize_provider_use(request: Request, provider_mode: str) -> None:
    normalized = provider_mode.lower()
    if normalized == "mock":
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


def _client_for_provider_mode(provider_mode: str):
    normalized = provider_mode.lower()
    if normalized == "mock":
        return MockLLMClient()
    if normalized in {"configured", "env", "real"}:
        return client_from_settings(current_provider_settings())
    raise HTTPException(status_code=400, detail="provider_mode must be mock, configured, or env.")


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PAPERSHIELD_WEB_PORT", "8000"))
    uvicorn.run("web.app:app", host="127.0.0.1", port=port, reload=False)
