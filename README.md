# PaperShield

PaperShield is a local-first academic writing quality agent. It improves reviewability of drafts by reducing formulaic transitions, preserving citations, surfacing paragraph-level risk flags, and producing human-review reports. It does not promise to bypass or defeat AI detectors.

## Compliance Boundary

- Use it only on drafts you are allowed to edit.
- Review all facts, claims, terms, and citations manually.
- Treat metrics as local proxy signals, not detector results.
- The portfolio demo supports `.txt`, basic `.docx`, CLI workflows, and a single-user Web review workspace.

## 5-Minute Local Start

PowerShell:

```powershell
python -m pip install -r requirements.txt -r requirements-dev.txt
$env:PAPERSHIELD_LLM_PROVIDER="mock"
.\scripts\verify.ps1
.\scripts\start-web.ps1
```

cmd:

```cmd
python -m pip install -r requirements.txt -r requirements-dev.txt
set PAPERSHIELD_LLM_PROVIDER=mock
python main.py doctor
python -m unittest discover -s tests -v
python main.py workflow-info --json
python main.py eval-fixtures --json
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` and verify the service at `http://127.0.0.1:8000/healthz`.
For dependency and static security checks, install `requirements-dev.txt` and run `.\scripts\security-audit.ps1`.
Use `setup-env.ps1` as a parameterized local helper only; keep real keys in your shell, `.env`, or `setup-env.local.ps1`, which are ignored by Git.

## Docker Demo

```bash
docker compose up --build
```

The container exposes port `8000` and defaults to `PAPERSHIELD_LLM_PROVIDER=mock`, which is safe for public portfolio demos because no model key is required.

For Render or Railway:

- Build from this repository with the included `Dockerfile`.
- Expose port `8000`.
- Keep `PAPERSHIELD_LLM_PROVIDER=mock` for public demos.
- Keep `PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0` for public demos so visitors cannot change model endpoints.
- Use `/healthz` as the health check path.
- Only set `PAPERSHIELD_LLM_PROVIDER=openai|anthropic` and API keys for private deployments.

For a free GitHub-synced deployment path, see `docs/deployment-free.md`. The repository includes `render.yaml` for Render Blueprint/Web Service deployment with automatic redeploys from `main`.

## CLI Commands

```powershell
python main.py list-domains
python main.py doctor
python main.py optimize .\examples\demo_law.txt --domain law --output .\out --report-format all
python main.py optimize .\examples\demo_law.txt --domain law --output .\out --report-format all --analysis-only
python main.py test-paragraph "此外，数据安全问题需要完善[1]。" --domain law --json
python main.py workflow-info --json
python main.py eval-fixtures --json
```

`optimize` writes an optimized document, a text/JSON/HTML report, and review checklists. `--analysis-only` runs diagnostics without rewriting the document, which is useful for cautious `.docx` review. `workflow-info` reports the active orchestration backend and node topology.

## Web Demo

The Web review workspace accepts pasted text, `.txt`, and basic `.docx` uploads. It supports:

- domain selection for law, economics, and general social science;
- mock or environment-backed provider modes;
- provider status and connection testing before running a real model;
- analysis-only mode;
- paragraph-by-paragraph accept/keep controls;
- paragraph recommendations, semantic fidelity risk flags, and inline diff segments;
- workflow trace for backend, conditional review route, and executed nodes;
- structure-preserving final draft merge using `document_blocks`;
- Markdown and HTML export for portfolio walkthroughs.

## Architecture

The implementation is intentionally small and fast to ship:

1. Parse `.txt` or basic `.docx`, split paragraphs, protect citations, and preserve titles, figures, tables, and references.
2. Apply Layer 1 syntax naturalization.
3. Apply Layer 2 domain-aware academic wording.
4. Score with a combined local diagnostic: perplexity proxy, sentence-length variation, template-word reduction, citation retention.
5. Build paragraph-level risk flags, semantic fidelity hints, recommendations, and a manual review checklist.
6. Route the document through a conditional review gate: accepted drafts continue through `quality_accepted`, while risky drafts enter `manual_review_required`.
7. Retry low-quality paragraphs once, then fall back safely if needed.
8. Assemble final text and text/JSON/HTML reports.
9. Serve the same workflow through FastAPI for local and Docker demos.

Install `requirements-optional.txt` to enable LangGraph orchestration. When LangGraph is available, `optimize_text()` and `build_graph()` execute the conditional `StateGraph`; otherwise they fall back to the lightweight local graph. Structured CLI and Web reports include `workflow.backend`, `workflow.route`, `workflow.nodes`, and a Web workflow trace for observability. `eval-fixtures --json` reports aggregate quality metrics, review routing counts, fallback counts, citation retention, and workflow backend coverage. Optional ML scoring dependencies live in `requirements-ml.txt` and are not required for the fast demo path.

## Provider Configuration

Useful environment variables:

- `PAPERSHIELD_LLM_PROVIDER=mock|openai|anthropic`
- `PAPERSHIELD_PROMPT_PROFILE=default|research_writing_zh_word_v1`
- `PAPERSHIELD_LLM_MODEL`
- `PAPERSHIELD_LLM_BASE_URL`
- `PAPERSHIELD_LLM_TIMEOUT`
- `PAPERSHIELD_LLM_MAX_RETRIES`
- `PAPERSHIELD_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`
- `PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0|1`
- `PAPERSHIELD_ADMIN_TOKEN` for protecting provider config/check endpoints in private deployments
- `PAPERSHIELD_MAX_UPLOAD_BYTES`, `PAPERSHIELD_MAX_TEXT_CHARS`, `PAPERSHIELD_MAX_PARAGRAPHS`
- `PAPERSHIELD_OPTIMIZE_RATE_LIMIT_PER_MINUTE`, `PAPERSHIELD_PROVIDER_RATE_LIMIT_PER_MINUTE`

Public demos should stay on `mock`. Real providers are intended for private runs with explicit keys.
Provider base URLs are HTTPS-only and block localhost, private, link-local, multicast, and metadata hosts.

Prompt profiles:

- `default` is the built-in PaperShield profile.
- `research_writing_zh_word_v1` is a PaperShield-owned rewrite inspired by public research-writing prompt patterns. It adds stronger system-level guardrails for untrusted draft content, citation placeholders, Word-compatible plain text output, and mechanical-style review without making external detector claims.

Provider helper endpoints:

- `GET /api/provider/status` reports provider, model, prompt profile, timeout, retry, and whether an API key is present without returning the key.
- `POST /api/provider/check` tests the selected provider mode; `mock` is local and free, while `env` may call the configured provider.
- `GET /api/runtime/policy` reports active upload/text/paragraph limits and provider configuration policy.
