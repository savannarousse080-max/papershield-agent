FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PAPERSHIELD_LLM_PROVIDER=mock
ENV PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0
ENV PAPERSHIELD_WEB_PORT=8000
ENV PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN adduser --system --group appuser

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD-SHELL python -c "import json, os, urllib.request; port=os.environ.get('PORT','8000'); data=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=3)); raise SystemExit(0 if data.get('status') == 'ok' else 1)"

CMD ["sh", "-c", "python -m uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
