# Free Deployment Guide

PaperShield can be deployed as a public mock demo without storing model keys.

## Recommended Path: GitHub + Render Free Web Service

Use this for the lowest-friction public demo with automatic redeploys from `main`.

1. Push this repository to GitHub.
2. In Render, create a new Blueprint or Web Service from the GitHub repository.
3. Keep the included `render.yaml` settings:
   - `plan: free`
   - `runtime: docker`
   - `healthCheckPath: /healthz`
   - `PAPERSHIELD_LLM_PROVIDER=mock`
   - `PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0`
4. After deployment, open `/healthz` and confirm `status` is `ok`.

Render free services may sleep after inactivity, so the first request after a quiet period can be slower.

## Alternative Free Paths

- Koyeb free instance: use the Dockerfile, set `PORT` from the platform, and keep the same public-demo env vars.
- Hugging Face Docker Space: good for a public portfolio demo; configure the Space to use Docker and expose the app port.
- Google Cloud Run free tier: technically has a free allowance, but normally requires billing setup.

## Safe Public Demo Environment

```env
PAPERSHIELD_LLM_PROVIDER=mock
PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0
PAPERSHIELD_PROMPT_PROFILE=default
```

## Private Real-Model Environment

Only use this behind trusted access.

```env
PAPERSHIELD_LLM_PROVIDER=openai-compatible
PAPERSHIELD_LLM_BASE_URL=https://provider.example.com/v1
PAPERSHIELD_LLM_MODEL=provider-model-id
PAPERSHIELD_API_KEY=<set in platform secret manager>
PAPERSHIELD_PROVIDER_CONFIG_ENABLED=1
PAPERSHIELD_ADMIN_TOKEN=<set in platform secret manager>
```

Do not commit real keys to GitHub.
