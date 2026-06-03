from __future__ import annotations

import importlib.util
import json
import re
import time

from agent.llm import LLMClient, MockLLMClient
from agent.nodes.assemble import assemble_final_text, build_report
from agent.nodes.layer1 import rewrite_syntax
from agent.nodes.layer2 import rewrite_lexical
from agent.nodes.parse import parse_text
from agent.nodes.scorer import score_paragraph
from agent.prompts.analysis_prompt import build_analysis_messages
from agent.prompts.layer2_prompts import get_domain_config
from agent.prompts.profiles import get_prompt_profile
from agent.review import aggregate_review_items, annotate_paragraph
from agent.state import AgentState, ParagraphRecord
from agent.workflow_labels import workflow_step_payload
from utils.citation_handler import restore_citations


MAX_RETRIES = 1
WORKFLOW_NODE_ORDER = (
    "parse_document",
    "process_paragraphs",
    "review_gate",
    "quality_accepted",
    "manual_review_required",
    "aggregate_review",
    "assemble_output",
)
WORKFLOW_EDGES = [
    ("START", "parse_document"),
    ("parse_document", "process_paragraphs"),
    ("process_paragraphs", "review_gate"),
    ("review_gate", "quality_accepted"),
    ("review_gate", "manual_review_required"),
    ("quality_accepted", "aggregate_review"),
    ("manual_review_required", "aggregate_review"),
    ("aggregate_review", "assemble_output"),
    ("assemble_output", "END"),
]


def optimize_text(
    raw_text: str,
    domain: str,
    llm_client: LLMClient | None = None,
    source_format: str = "txt",
    analysis_only: bool = False,
    prompt_profile: str | None = None,
) -> AgentState:
    graph = build_graph(domain, llm_client=llm_client)
    return graph.invoke(
        {
            "raw_text": raw_text,
            "domain": domain,
            "source_format": source_format,
            "analysis_only": analysis_only,
            "prompt_profile": prompt_profile,
        }
    )


def workflow_topology() -> dict:
    nodes = list(WORKFLOW_NODE_ORDER)
    return {
        "active_backend": "langgraph" if importlib.util.find_spec("langgraph") else "simple",
        "nodes": nodes,
        "steps": workflow_step_payload(nodes),
        "edges": [[source, target] for source, target in WORKFLOW_EDGES],
    }


def _initial_workflow_state(
    raw_text: str,
    domain: str,
    llm_client: LLMClient | None = None,
    source_format: str = "txt",
    analysis_only: bool = False,
    prompt_profile: str | None = None,
) -> dict:
    get_domain_config(domain)
    profile = get_prompt_profile(prompt_profile)
    llm = llm_client or MockLLMClient()
    return {
        "agent_state": AgentState(
            raw_text=raw_text,
            domain=domain,
            source_format=source_format,
            analysis_only=analysis_only,
            prompt_profile=profile.id,
        ),
        "llm_client": llm,
        "started": time.perf_counter(),
        "trace": [],
    }


def _parse_document_node(workflow: dict) -> dict:
    state: AgentState = workflow["agent_state"]
    state.parsed = parse_text(state.raw_text)
    return _workflow_update(workflow, "parse_document", state)


def _process_paragraphs_node(workflow: dict) -> dict:
    state: AgentState = workflow["agent_state"]
    llm: LLMClient = workflow["llm_client"]
    if state.parsed is None:
        raise ValueError("Workflow parse_document node must run before process_paragraphs.")

    analysis_warning = None
    if state.analysis_only:
        try:
            state.analysis_summary = _analyze_document_only(state, llm)
        except Exception as exc:
            analysis_warning = f"document analysis failed: {exc}"
            state.warnings.append(analysis_warning)
            state.analysis_summary = _fallback_analysis_summary(state, str(exc))

    for paragraph in state.parsed.paragraphs:
        if state.analysis_only:
            warnings = [analysis_warning] if analysis_warning else None
            state.processed_paragraphs.append(
                _analyze_paragraph_only(paragraph.paragraph_index or 0, paragraph.text, state.parsed.citation_map, warnings)
            )
            continue
        state.processed_paragraphs.append(
            _process_paragraph(
                index=paragraph.paragraph_index or 0,
                protected_text=paragraph.text,
                domain=state.domain,
                citation_map=state.parsed.citation_map,
                llm_client=llm,
                prompt_profile=state.prompt_profile,
            )
        )
    return _workflow_update(workflow, "process_paragraphs", state)


def _review_gate_node(workflow: dict) -> dict:
    state: AgentState = workflow["agent_state"]
    route = "manual_review_required" if _needs_manual_review(state) else "quality_accepted"
    state.metrics["workflow_route"] = route
    state.metrics["manual_review_required"] = route == "manual_review_required"
    return _workflow_update(workflow, "review_gate", state, {"route": route})


def _quality_accepted_node(workflow: dict) -> dict:
    state: AgentState = workflow["agent_state"]
    state.metrics["workflow_route"] = "quality_accepted"
    state.metrics["manual_review_required"] = False
    return _workflow_update(workflow, "quality_accepted", state, {"route": "quality_accepted"})


def _manual_review_required_node(workflow: dict) -> dict:
    state: AgentState = workflow["agent_state"]
    state.metrics["workflow_route"] = "manual_review_required"
    state.metrics["manual_review_required"] = True
    return _workflow_update(workflow, "manual_review_required", state, {"route": "manual_review_required"})


def _aggregate_review_node(workflow: dict) -> dict:
    state: AgentState = workflow["agent_state"]
    state.review_items = aggregate_review_items(state.processed_paragraphs)
    return _workflow_update(workflow, "aggregate_review", state)


def _assemble_output_node(workflow: dict) -> dict:
    state: AgentState = workflow["agent_state"]
    state.final_text = assemble_final_text(state)
    state.report = build_report(state, elapsed_seconds=time.perf_counter() - workflow["started"])
    return _workflow_update(workflow, "assemble_output", state)


def _workflow_update(workflow: dict, node_name: str, state: AgentState, extra: dict | None = None) -> dict:
    update = {
        "agent_state": state,
        "llm_client": workflow["llm_client"],
        "started": workflow["started"],
        "trace": _next_trace(workflow, node_name),
    }
    if "route" in workflow:
        update["route"] = workflow["route"]
    if extra:
        update.update(extra)
    return update


def _next_trace(workflow: dict, node_name: str) -> list[str]:
    return [*workflow.get("trace", []), node_name]


def _stamp_workflow_metadata(state: AgentState, backend: str, trace: list[str]) -> None:
    state.metrics["workflow_backend"] = backend
    state.metrics["workflow_nodes"] = list(trace or WORKFLOW_NODE_ORDER)


_WORKFLOW_NODES = {
    "parse_document": _parse_document_node,
    "process_paragraphs": _process_paragraphs_node,
    "review_gate": _review_gate_node,
    "quality_accepted": _quality_accepted_node,
    "manual_review_required": _manual_review_required_node,
    "aggregate_review": _aggregate_review_node,
    "assemble_output": _assemble_output_node,
}


def _needs_manual_review(state: AgentState) -> bool:
    return any(record.recommendation in {"review", "keep_original"} for record in state.processed_paragraphs)


def _select_review_route(workflow: dict) -> str:
    route = workflow.get("route")
    if route in {"quality_accepted", "manual_review_required"}:
        return route
    state: AgentState = workflow["agent_state"]
    return "manual_review_required" if _needs_manual_review(state) else "quality_accepted"


def _run_workflow_nodes(workflow: dict) -> dict:
    for node_name in ("parse_document", "process_paragraphs", "review_gate"):
        workflow.update(_WORKFLOW_NODES[node_name](workflow))
    workflow.update(_WORKFLOW_NODES[_select_review_route(workflow)](workflow))
    for node_name in ("aggregate_review", "assemble_output"):
        workflow.update(_WORKFLOW_NODES[node_name](workflow))
    return workflow


def _analyze_document_only(state: AgentState, llm_client: LLMClient) -> dict:
    if state.parsed is None:
        return _empty_analysis_summary(0, 0)
    body_text = "\n\n".join(restore_citations(block.text, state.parsed.citation_map) for block in state.parsed.paragraphs)
    response = llm_client.complete(build_analysis_messages(body_text or state.raw_text, state.domain, state.prompt_profile))
    summary = _parse_analysis_response(response)
    summary["scope"] = {
        "analyzed_paragraphs": len(state.parsed.paragraphs),
        "skipped_blocks": len([block for block in state.parsed.blocks if block.kind != "paragraph"]),
    }
    return summary


def _parse_analysis_response(response: str) -> dict:
    text = response.strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    payload = json.loads(match.group(0) if match else text)
    return {
        "overview": str(payload.get("overview") or "已完成文章级诊断，请结合下方要点复核正文质量。").strip(),
        "strengths": _string_list(payload.get("strengths")),
        "issues": _string_list(payload.get("issues")),
        "suggestions": _string_list(payload.get("suggestions")),
    }


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _fallback_analysis_summary(state: AgentState, reason: str) -> dict:
    paragraph_count = len(state.parsed.paragraphs) if state.parsed else 0
    skipped_count = len([block for block in state.parsed.blocks if block.kind != "paragraph"]) if state.parsed else 0
    summary = _empty_analysis_summary(paragraph_count, skipped_count)
    summary["overview"] = "模型文章级分析未完成，系统已保留原文并生成本地诊断指标。"
    summary["issues"] = [f"模型分析失败：{reason}"]
    summary["suggestions"] = ["请检查模型配置后重新运行，或先依据本地指标人工复核。"]
    return summary


def _empty_analysis_summary(paragraph_count: int, skipped_count: int) -> dict:
    return {
        "overview": "未发现可分析的正文段落。",
        "strengths": [],
        "issues": [],
        "suggestions": [],
        "scope": {
            "analyzed_paragraphs": paragraph_count,
            "skipped_blocks": skipped_count,
        },
    }


def _analyze_paragraph_only(index: int, protected_text: str, citation_map: dict[str, str], warnings: list[str] | None = None) -> ParagraphRecord:
    original_text = restore_citations(protected_text, citation_map)
    metrics = score_paragraph(protected_text, protected_text)
    return annotate_paragraph(ParagraphRecord(
        index=index,
        original_text=original_text,
        rewritten_text=original_text,
        protected_original=protected_text,
        protected_rewritten=protected_text,
        retry_count=0,
        status="analysis_only",
        metrics=metrics,
        warnings=warnings or [],
    ))


def _process_paragraph(
    index: int,
    protected_text: str,
    domain: str,
    citation_map: dict[str, str],
    llm_client: LLMClient,
    prompt_profile: str,
) -> ParagraphRecord:
    original_text = restore_citations(protected_text, citation_map)
    last_metrics = None
    warnings: list[str] = []
    retry_count = 0

    for attempt in range(MAX_RETRIES + 1):
        try:
            layer1 = rewrite_syntax(protected_text, llm_client, prompt_profile)
            layer2 = rewrite_lexical(layer1, domain, llm_client, prompt_profile)
            metrics = score_paragraph(protected_text, layer2)
            last_metrics = metrics
            missing = _missing_placeholders(protected_text, layer2)
            if missing:
                warnings.append(f"LLM output missed protected citations: {', '.join(missing)}")
            if metrics.passed and not missing:
                return annotate_paragraph(ParagraphRecord(
                    index=index,
                    original_text=original_text,
                    rewritten_text=restore_citations(layer2, citation_map),
                    protected_original=protected_text,
                    protected_rewritten=layer2,
                    retry_count=attempt,
                    status="accepted",
                    metrics=metrics,
                    warnings=warnings,
                ))
        except Exception as exc:
            warnings.append(f"paragraph processing failed: {exc}")
            break
        retry_count = attempt + 1

    if last_metrics is not None and not _missing_placeholders(protected_text, layer2):
        return annotate_paragraph(ParagraphRecord(
            index=index,
            original_text=original_text,
            rewritten_text=restore_citations(layer2, citation_map),
            protected_original=protected_text,
            protected_rewritten=layer2,
            retry_count=min(retry_count, MAX_RETRIES),
            status="below_threshold",
            metrics=last_metrics,
            warnings=warnings,
        ))

    fallback_metrics = score_paragraph(protected_text, protected_text)
    return annotate_paragraph(ParagraphRecord(
        index=index,
        original_text=original_text,
        rewritten_text=original_text,
        protected_original=protected_text,
        protected_rewritten=protected_text,
        retry_count=min(retry_count, MAX_RETRIES),
        status="fallback",
        metrics=fallback_metrics,
        warnings=warnings,
    ))


def _missing_placeholders(original: str, rewritten: str) -> list[str]:
    placeholders = [part for part in original.split() if part.startswith("{{REF_")]
    if not placeholders:
        import re

        placeholders = re.findall(r"\{\{REF_\d+\}\}", original)
    return [placeholder for placeholder in placeholders if placeholder not in rewritten]


class SimpleCompiledGraph:
    def __init__(self, domain: str, llm_client: LLMClient | None = None, backend: str = "simple"):
        self.domain = domain
        self.llm_client = llm_client
        self.backend = backend
        self.node_names = list(WORKFLOW_NODE_ORDER)

    def invoke(self, state: dict) -> AgentState:
        workflow = _initial_workflow_state(
            state["raw_text"],
            state.get("domain", self.domain),
            self.llm_client,
            source_format=state.get("source_format", "txt"),
            analysis_only=state.get("analysis_only", False),
            prompt_profile=state.get("prompt_profile"),
        )
        workflow = _run_workflow_nodes(workflow)
        agent_state = workflow["agent_state"]
        _stamp_workflow_metadata(agent_state, self.backend, workflow.get("trace", []))
        return agent_state


class LangGraphCompiledGraph:
    def __init__(self, domain: str, llm_client: LLMClient | None = None):
        from langgraph.graph import END, START, StateGraph

        self.domain = domain
        self.llm_client = llm_client
        self.backend = "langgraph"
        self.node_names = list(WORKFLOW_NODE_ORDER)
        graph = StateGraph(dict)

        for node_name in WORKFLOW_NODE_ORDER:
            graph.add_node(node_name, _WORKFLOW_NODES[node_name])
        graph.add_edge(START, "parse_document")
        graph.add_edge("parse_document", "process_paragraphs")
        graph.add_edge("process_paragraphs", "review_gate")
        graph.add_conditional_edges(
            "review_gate",
            _select_review_route,
            {
                "quality_accepted": "quality_accepted",
                "manual_review_required": "manual_review_required",
            },
        )
        graph.add_edge("quality_accepted", "aggregate_review")
        graph.add_edge("manual_review_required", "aggregate_review")
        graph.add_edge("aggregate_review", "assemble_output")
        graph.add_edge("assemble_output", END)
        self._compiled = graph.compile()

    def invoke(self, state: dict) -> AgentState:
        workflow = _initial_workflow_state(
            state["raw_text"],
            state.get("domain", self.domain),
            self.llm_client,
            source_format=state.get("source_format", "txt"),
            analysis_only=state.get("analysis_only", False),
            prompt_profile=state.get("prompt_profile"),
        )
        result = self._compiled.invoke(workflow)
        agent_state = result["agent_state"]
        _stamp_workflow_metadata(agent_state, self.backend, result.get("trace", []))
        return agent_state


def build_graph(domain: str, llm_client: LLMClient | None = None) -> SimpleCompiledGraph | LangGraphCompiledGraph:
    try:
        return LangGraphCompiledGraph(domain=domain, llm_client=llm_client)
    except Exception:
        return SimpleCompiledGraph(domain=domain, llm_client=llm_client)
