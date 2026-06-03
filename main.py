from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from agent.graph import optimize_text, workflow_topology
from agent.llm import MockLLMClient, ProviderConfigError, client_from_env, settings_from_env
from agent.nodes.assemble import build_report_dict, build_report_html, build_review_checklist, build_review_markdown
from agent.prompts.layer2_prompts import DOMAIN_CONFIGS, get_domain_config
from agent.prompts.profiles import get_prompt_profile
from agent.evaluation import evaluate_fixtures
from utils.document_io import read_input_document, write_optimized_document
from utils.report_docx import write_report_docx


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list-domains":
            return list_domains()
        if args.command == "doctor":
            return doctor()
        if args.command == "eval-fixtures":
            return eval_fixtures_command(args)
        if args.command == "test-paragraph":
            return test_paragraph(args)
        if args.command == "optimize":
            return optimize_file(args)
        if args.command == "workflow-info":
            return workflow_info(args)
        parser.print_help()
        return 1
    except (ValueError, ProviderConfigError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"PaperShield failed: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaperShield academic writing quality and style-risk CLI")
    subparsers = parser.add_subparsers(dest="command")

    optimize = subparsers.add_parser("optimize", help="Optimize a .txt or .docx draft and write text/report outputs")
    optimize.add_argument("input_file")
    optimize.add_argument("--domain", required=True, choices=sorted(DOMAIN_CONFIGS))
    optimize.add_argument("--output", default=None, help="Output directory")
    optimize.add_argument("--input-format", default="auto", choices=["auto", "txt", "docx"], help="Input format")
    optimize.add_argument("--report-format", default="text", choices=["text", "json", "html", "docx", "both", "all"], help="Report output format")
    optimize.add_argument("--analysis-only", action="store_true", help="Run diagnostics without rewriting the document")

    paragraph = subparsers.add_parser("test-paragraph", help="Run one paragraph through the workflow")
    paragraph.add_argument("text")
    paragraph.add_argument("--domain", required=True, choices=sorted(DOMAIN_CONFIGS))
    paragraph.add_argument("--json", action="store_true", help="Print a structured JSON payload")

    subparsers.add_parser("list-domains", help="List supported domains")
    subparsers.add_parser("doctor", help="Check provider configuration and optional dependencies")
    workflow = subparsers.add_parser("workflow-info", help="Show workflow graph topology and active backend")
    workflow.add_argument("--json", action="store_true", help="Print structured JSON topology")
    fixtures = subparsers.add_parser("eval-fixtures", help="Run deterministic regression fixtures")
    fixtures.add_argument("--fixtures-dir", default="fixtures", help="Directory containing fixture JSON files")
    fixtures.add_argument("--json", action="store_true", help="Print structured JSON summary")
    return parser


def list_domains() -> int:
    for key, config in DOMAIN_CONFIGS.items():
        print(f"{key}: {config['display_name']} | protected_terms={len(config['protected_terms'])} | examples={len(config['few_shot_examples'])}")
    return 0


def optimize_file(args: argparse.Namespace) -> int:
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 2
    get_domain_config(args.domain)
    output_dir = Path(args.output) if args.output else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    source = read_input_document(input_path, args.input_format)
    llm = None if args.analysis_only else client_from_env()
    state = optimize_text(source.text, args.domain, llm, source_format=source.source_format, analysis_only=args.analysis_only)
    state.warnings.extend(source.warnings)

    optimized_suffix = ".docx" if source.source_format == "docx" else ".txt"
    optimized_path = output_dir / f"{input_path.stem}_optimized{optimized_suffix}"
    write_optimized_document(source, state.final_text, optimized_path)

    review_path = output_dir / f"{input_path.stem}_review.txt"
    review_path.write_text(build_review_checklist(state), encoding="utf-8")
    review_md_path = output_dir / f"{input_path.stem}_review.md"
    review_md_path.write_text(build_review_markdown(state), encoding="utf-8")

    report_payload = build_report_dict(state)
    report_paths: list[Path] = []
    if args.report_format in {"text", "both", "all"}:
        report_path = output_dir / f"{input_path.stem}_report.txt"
        report_path.write_text(state.report, encoding="utf-8")
        report_paths.append(report_path)
    if args.report_format in {"json", "both", "all"}:
        report_json_path = output_dir / f"{input_path.stem}_report.json"
        report_json_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report_paths.append(report_json_path)
    if args.report_format in {"html", "all"}:
        report_html_path = output_dir / f"{input_path.stem}_report.html"
        report_html_path.write_text(build_report_html(state), encoding="utf-8")
        report_paths.append(report_html_path)
    if args.report_format in {"docx", "all"}:
        report_docx_path = output_dir / f"{input_path.stem}_report.docx"
        write_report_docx(report_payload, report_docx_path)
        report_paths.append(report_docx_path)

    print(f"Optimized file: {optimized_path}")
    for report_path in report_paths:
        print(f"Report file: {report_path}")
    print(f"Review checklist: {review_path}")
    print(f"Review checklist: {review_md_path}")
    return 0


def test_paragraph(args: argparse.Namespace) -> int:
    get_domain_config(args.domain)
    llm = client_from_env()
    state = optimize_text(args.text, args.domain, llm)
    if args.json:
        print(json.dumps(build_report_dict(state), ensure_ascii=False, indent=2))
        return 0
    print(state.final_text)
    print()
    print(state.report)
    return 0


def doctor() -> int:
    settings = settings_from_env()
    print("=== PaperShield Doctor ===")
    print(f"Provider: {settings.provider}")
    print(f"Model: {settings.model}")
    print(f"Prompt profile: {get_prompt_profile().id}")
    print(f"Domains: {', '.join(sorted(DOMAIN_CONFIGS))}")
    print("Optional dependencies:")
    for module_name, label in [
        ("docx", "python-docx (.docx support)"),
        ("fastapi", "FastAPI (web demo)"),
        ("langgraph", "LangGraph orchestration"),
        ("transformers", "transformer perplexity scorer"),
        ("torch", "torch backend for transformer scorer"),
    ]:
        status = "available" if importlib.util.find_spec(module_name) else "missing"
        print(f"  - {label}: {status}")

    try:
        client = client_from_env()
        if isinstance(client, MockLLMClient):
            print("Ready for local demo with deterministic mock provider.")
        else:
            print("Provider configuration can be initialized.")
        return 0
    except ProviderConfigError as exc:
        print(str(exc))
        return 2


def workflow_info(args: argparse.Namespace) -> int:
    topology = workflow_topology()
    if args.json:
        print(json.dumps(topology, ensure_ascii=False, indent=2))
        return 0
    print(f"Backend: {topology['active_backend']}")
    print("Nodes:")
    for node in topology["nodes"]:
        print(f"  - {node}")
    print("Edges:")
    for source, target in topology["edges"]:
        print(f"  - {source} -> {target}")
    return 0


def eval_fixtures_command(args: argparse.Namespace) -> int:
    summary = evaluate_fixtures(Path(args.fixtures_dir))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["failed"] == 0 else 1

    for result in summary["results"]:
        marker = "PASS" if result["passed"] else "FAIL"
        detail = "" if result["passed"] else f" | {'; '.join(result['errors'])}"
        print(f"{marker} {result['id']}{detail}")
    print(f"Fixtures passed: {summary['passed']}/{summary['total']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
