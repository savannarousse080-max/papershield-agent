from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploymentReadinessTests(unittest.TestCase):
    def test_docker_assets_define_fastapi_demo_service(self):
        dockerfile = ROOT / "Dockerfile"
        compose = ROOT / "docker-compose.yml"
        dockerignore = ROOT / ".dockerignore"
        gitignore = ROOT / ".gitignore"
        gitattributes = ROOT / ".gitattributes"
        render_config = ROOT / "render.yaml"

        self.assertTrue(dockerfile.exists())
        self.assertTrue(compose.exists())
        self.assertTrue(dockerignore.exists())
        self.assertTrue(gitignore.exists())
        self.assertTrue(gitattributes.exists())
        self.assertTrue(render_config.exists())

        dockerfile_text = dockerfile.read_text(encoding="utf-8")
        compose_text = compose.read_text(encoding="utf-8")
        dockerignore_text = dockerignore.read_text(encoding="utf-8")
        gitignore_text = gitignore.read_text(encoding="utf-8")
        gitattributes_text = gitattributes.read_text(encoding="utf-8")
        render_text = render_config.read_text(encoding="utf-8")

        self.assertIn("python:3.11-slim", dockerfile_text)
        self.assertIn("uvicorn", dockerfile_text)
        self.assertIn("web.app:app", dockerfile_text)
        self.assertIn("USER appuser", dockerfile_text)
        self.assertIn("${PORT:-8000}", dockerfile_text)
        self.assertIn("PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0", dockerfile_text)
        self.assertIn("PAPERSHIELD_LLM_PROVIDER=mock", compose_text)
        self.assertIn("PAPERSHIELD_PROVIDER_CONFIG_ENABLED=0", compose_text)
        self.assertIn("plan: free", render_text)
        self.assertIn("runtime: docker", render_text)
        self.assertIn("autoDeploy: true", render_text)
        self.assertIn("healthCheckPath: /healthz", render_text)
        self.assertIn("PAPERSHIELD_PROVIDER_CONFIG_ENABLED", render_text)
        self.assertIn('PAPERSHIELD_PROVIDER_CONFIG_ENABLED\n        value: "0"', render_text)
        self.assertIn("PAPERSHIELD_REQUIRE_ADMIN_TOKEN_FOR_PROVIDER_USE", render_text)
        self.assertIn('PAPERSHIELD_REQUIRE_ADMIN_TOKEN_FOR_PROVIDER_USE\n        value: "1"', render_text)
        self.assertIn("PAPERSHIELD_ADMIN_TOKEN", render_text)
        self.assertIn("sync: false", render_text)
        self.assertIn('"8000:8000"', compose_text)
        self.assertIn("config/provider.local.json", dockerignore_text)
        self.assertIn(".env", dockerignore_text)
        self.assertIn("__pycache__/", dockerignore_text)
        self.assertIn("out/", dockerignore_text)
        for pattern in ["out/", "*.docx", "uvicorn-*.log", "__pycache__/", "*.pyc", ".env", ".vs/", "setup-env.local.ps1"]:
            self.assertIn(pattern, gitignore_text)
        self.assertIn("* text=auto eol=lf", gitattributes_text)

    def test_local_scripts_document_verification_and_web_start(self):
        verify = ROOT / "scripts" / "verify.ps1"
        start_web = ROOT / "scripts" / "start-web.ps1"
        security_audit = ROOT / "scripts" / "security-audit.ps1"
        ci = ROOT / ".github" / "workflows" / "ci.yml"

        self.assertTrue(verify.exists())
        self.assertTrue(start_web.exists())
        self.assertTrue(security_audit.exists())
        self.assertTrue(ci.exists())

        verify_text = verify.read_text(encoding="utf-8")
        start_text = start_web.read_text(encoding="utf-8")
        audit_text = security_audit.read_text(encoding="utf-8")
        ci_text = ci.read_text(encoding="utf-8")

        self.assertIn("python main.py doctor", verify_text)
        self.assertIn("python -m unittest discover -s tests -v", verify_text)
        self.assertIn("python main.py eval-fixtures --json", verify_text)
        self.assertIn("PAPERSHIELD_LLM_PROVIDER", start_text)
        self.assertIn("python -m uvicorn web.app:app", start_text)
        self.assertIn("pip_audit", audit_text)
        self.assertIn("bandit", audit_text)
        self.assertIn("python -m unittest discover -s tests -v", ci_text)
        self.assertIn("python -m ruff check .", ci_text)
        self.assertIn("node --check web/static/app.js", ci_text)

    def test_dependency_specs_have_bounds_and_security_tooling(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        ml_requirements = (ROOT / "requirements-ml.txt").read_text(encoding="utf-8").splitlines()
        dev_requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        optional_requirements = (ROOT / "requirements-optional.txt").read_text(encoding="utf-8")

        for line in requirements + ml_requirements:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                self.assertIn(">=", stripped)
                self.assertIn("<", stripped)
        self.assertNotIn("langgraph", "\n".join(requirements).lower())
        self.assertIn("langgraph", optional_requirements)
        self.assertIn("pip-audit", dev_requirements)
        self.assertIn("bandit", dev_requirements)
        self.assertIn("ruff", dev_requirements)
        self.assertIn("httpx", dev_requirements)
        self.assertIn("pytest", dev_requirements)
        self.assertNotIn("pytest", "\n".join(requirements))

    def test_repository_files_do_not_contain_committed_runtime_secrets(self):
        secret_patterns = [
            "PAPERSHIELD_API_KEY=\"AQ.",
            "PAPERSHIELD_API_KEY='AQ.",
            "sk-",
            "BEGIN PRIVATE KEY",
        ]
        scan_targets = [
            ROOT / "setup-env.ps1",
            ROOT / ".env.example",
            ROOT / "README.md",
            ROOT / "Dockerfile",
            ROOT / "docker-compose.yml",
        ]

        for path in scan_targets:
            text = path.read_text(encoding="utf-8")
            for pattern in secret_patterns:
                self.assertNotIn(pattern, text, f"{path} appears to contain a secret-like value")

    def test_product_docs_are_aligned_with_demo_and_deployment_story(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        prd = (ROOT / "PaperShield-Agent-PRD-v3.md").read_text(encoding="utf-8")
        demo_script = ROOT / "docs" / "demo-script.md"

        self.assertTrue(demo_script.exists())
        demo_text = demo_script.read_text(encoding="utf-8")

        self.assertIn("scripts\\verify.ps1", readme)
        self.assertIn("docker compose up", readme)
        self.assertIn("工作流轨迹", readme)
        self.assertIn("条件审阅", readme)
        self.assertIn("/healthz", readme)
        self.assertIn("Render", readme)
        self.assertIn("Railway", readme)
        self.assertIn("docs/deployment-free.md", readme)
        self.assertIn("演示可用版", prd)
        self.assertIn("快速上线", prd)
        self.assertNotIn("不支持：`.docx`、Web Demo", prd)
        self.assertIn("条件审阅", prd)
        self.assertIn("5 分钟", demo_text)
        self.assertIn("工程交付", demo_text)
        self.assertIn("工作流轨迹", demo_text)

    def test_demo_outputs_are_refreshed_for_portfolio_walkthrough(self):
        out_dir = ROOT / "out"
        expected = {
            "demo_law_optimized.txt",
            "demo_law_report.txt",
            "demo_law_report.json",
            "demo_law_report.html",
            "demo_law_review.md",
        }

        existing = {path.name for path in out_dir.glob("demo_law_*")}
        self.assertTrue(expected.issubset(existing))

        for path in out_dir.glob("demo_law_*"):
            if path.is_file() and path.suffix in {".txt", ".json", ".html", ".md"}:
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("问题并不轻", text)
                self.assertNotIn("status=", text)
