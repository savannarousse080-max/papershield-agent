from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from agent.graph import optimize_text
from agent.llm import MockLLMClient
from agent.state import AgentState, ParagraphRecord


class FailingLLMClient:
    def complete(self, messages: list[dict[str, str]]) -> str:
        raise RuntimeError("simulated fixture provider failure")


def evaluate_fixtures(fixtures_dir: Path) -> dict[str, Any]:
    if not fixtures_dir.exists():
        raise ValueError(f"Fixture directory not found: {fixtures_dir}")

    results = [_evaluate_fixture(path) for path in sorted(fixtures_dir.glob("*.json"))]
    passed = sum(1 for result in results if result["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "metrics": _aggregate_metrics(results),
        "results": results,
    }


def _evaluate_fixture(path: Path) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    fixture_id = fixture.get("id") or path.stem
    errors: list[str] = []

    state = optimize_text(
        fixture["text"],
        fixture["domain"],
        llm_client=MockLLMClient(),
        source_format=fixture.get("source_format", "txt"),
        analysis_only=fixture.get("analysis_only", False),
    )
    expect = fixture.get("expect", {})
    state_summary = _state_summary(state)

    _expect_contains(errors, "final_text", state.final_text, expect.get("contains", []))
    _expect_absent(errors, "final_text", state.final_text, expect.get("not_contains", []))
    _expect_contains(errors, "final_text", state.final_text, expect.get("preserved", []))
    _expect_status_counts(errors, state_summary["status_counts"], expect.get("status_counts", {}))
    _expect_risk_flags(errors, state.processed_paragraphs, expect.get("risk_flags", []))

    if "paragraph_count" in expect and len(state.processed_paragraphs) != expect["paragraph_count"]:
        errors.append(f"paragraph_count expected {expect['paragraph_count']}, got {len(state.processed_paragraphs)}")

    citation_min = expect.get("citation_retention_min")
    if citation_min is not None:
        actual = state.processed_paragraphs[0].metrics.citation_retention if state.processed_paragraphs else 0.0
        if actual < citation_min:
            errors.append(f"citation_retention expected >= {citation_min}, got {actual:.3f}")

    review_required_min = expect.get("review_required_min")
    if review_required_min is not None and state_summary["review_required"] < review_required_min:
        errors.append(f"review_required expected >= {review_required_min}, got {state_summary['review_required']}")

    if expect.get("fallback_on_provider_failure"):
        failure_state = optimize_text(
            fixture["text"],
            fixture["domain"],
            llm_client=FailingLLMClient(),
            source_format=fixture.get("source_format", "txt"),
        )
        bad_statuses = [record.status for record in failure_state.processed_paragraphs if record.status != "fallback"]
        if bad_statuses:
            errors.append(f"fallback expected for provider failure, got statuses: {bad_statuses}")
        _expect_contains(errors, "fallback final_text", failure_state.final_text, expect.get("fallback_contains", expect.get("contains", [])))

    return {
        "id": fixture_id,
        "path": str(path),
        "domain": fixture["domain"],
        "passed": not errors,
        "errors": errors,
        **state_summary,
    }


def _state_summary(state: AgentState) -> dict[str, Any]:
    records = state.processed_paragraphs
    status_counts = Counter(record.status for record in records)
    citation_values = [record.metrics.citation_retention for record in records if record.metrics]
    workflow_nodes = state.metrics.get("workflow_nodes", [])
    return {
        "paragraph_count": len(records),
        "fallback_count": sum(1 for record in records if record.status == "fallback"),
        "review_required": sum(1 for record in records if record.recommendation == "review"),
        "average_citation_retention": _avg(citation_values),
        "status_counts": dict(status_counts),
        "workflow_backend": state.metrics.get("workflow_backend", "unknown"),
        "workflow_nodes": list(workflow_nodes) if isinstance(workflow_nodes, list) else [],
    }


def _aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_paragraphs = sum(result.get("paragraph_count", 0) for result in results)
    weighted_citation = sum(
        result.get("average_citation_retention", 0.0) * result.get("paragraph_count", 0)
        for result in results
    )
    workflow_backends = Counter(result.get("workflow_backend", "unknown") for result in results)
    return {
        "total_paragraphs": total_paragraphs,
        "average_citation_retention": (weighted_citation / total_paragraphs) if total_paragraphs else 0.0,
        "review_required": sum(result.get("review_required", 0) for result in results),
        "fallback_count": sum(result.get("fallback_count", 0) for result in results),
        "workflow_backends": dict(workflow_backends),
    }


def _expect_contains(errors: list[str], field: str, value: str, needles: list[str]) -> None:
    for needle in needles:
        if needle not in value:
            errors.append(f"{field} missing expected text: {needle}")


def _expect_absent(errors: list[str], field: str, value: str, needles: list[str]) -> None:
    for needle in needles:
        if needle in value:
            errors.append(f"{field} contains forbidden text: {needle}")


def _expect_status_counts(errors: list[str], actual: dict[str, int], expected: dict[str, int]) -> None:
    for status, count in expected.items():
        if actual.get(status, 0) != count:
            errors.append(f"status_counts[{status}] expected {count}, got {actual.get(status, 0)}")


def _expect_risk_flags(errors: list[str], records: list[ParagraphRecord], expected_flags: list[str]) -> None:
    actual_flags = {flag for record in records for flag in record.risk_flags}
    for flag in expected_flags:
        if flag not in actual_flags:
            errors.append(f"risk_flags missing expected flag: {flag}")


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
