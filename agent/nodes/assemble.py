from __future__ import annotations

from datetime import datetime
from html import escape
import re

from agent.labels import recommendation_label, risk_flag_label, status_label
from agent.prompts.layer2_prompts import get_domain_config
from agent.state import AgentState, ParagraphRecord
from agent.workflow_labels import backend_label, manual_review_label, route_label, workflow_step_payload
from utils.citation_handler import restore_citations


def assemble_final_text(state: AgentState) -> str:
    if state.parsed is None:
        return ""
    paragraph_by_index = {record.index: record for record in state.processed_paragraphs}
    parts: list[str] = []
    for block in state.parsed.blocks:
        if block.kind == "paragraph" and block.paragraph_index is not None:
            parts.append(paragraph_by_index[block.paragraph_index].rewritten_text)
        else:
            parts.append(block.text)
    return "\n\n".join(part for part in parts if part)


def build_report(state: AgentState, elapsed_seconds: float = 0.0) -> str:
    domain_config = get_domain_config(state.domain)
    records = state.processed_paragraphs
    retry_count = sum(record.retry_count for record in records)
    fallback_indexes = [record.index + 1 for record in records if record.status == "fallback"]
    avg_original = _avg([record.metrics.original_perplexity for record in records if record.metrics])
    avg_rewritten = _avg([record.metrics.rewritten_perplexity for record in records if record.metrics])
    avg_change = ((avg_rewritten - avg_original) / avg_original) if avg_original else 0.0
    avg_citation = _avg([record.metrics.citation_retention for record in records if record.metrics])
    avg_template = _avg([record.metrics.template_reduction for record in records if record.metrics])

    lines = [
        "=== PaperShield 合规润色诊断报告 ===",
        "",
        f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"领域设定: {domain_config['display_name']} ({state.domain})",
        f"处理模式: {'仅分析，不改写原文' if state.analysis_only else '润色与诊断'}",
        f"处理段落数: {len(records)}",
        f"重试触发: {retry_count} 次",
        f"处理耗时: {elapsed_seconds:.2f} 秒",
        "",
        "组合指标:",
        f"  困惑度代理均值: {avg_original:.2f} -> {avg_rewritten:.2f} ({avg_change:+.1%})",
        f"  模板词减少率均值: {avg_template:.1%}",
        f"  引注保留率均值: {avg_citation:.1%}",
        "",
        "指标说明:",
        "  - 困惑度代理是本地语言多样性参考值，不等同于任何外部检测器结果。",
        "  - 模板词减少率衡量常见套话连接词是否下降。",
        "  - 引注保留率只检查数量和占位符还原，不能替代人工核验。",
        "  - 语义保真提示用于发现疑似新增事实、术语变化和未变化输出，不能替代人工判断。",
        "",
    ]
    if state.analysis_only and state.analysis_summary:
        lines.extend(_analysis_summary_lines(state.analysis_summary))
        lines.append("")
    lines.append("逐段明细:")
    for record in records:
        if record.metrics:
            lines.append(
                "  段落 {idx}: 状态={status}, 建议={recommendation}, 重试={retry} 次, 困惑度={before:.2f}->{after:.2f}, "
                "模板减少={template:.1%}, 引注保留={citation:.1%}".format(
                    idx=record.index + 1,
                    status=status_label(record.status),
                    recommendation=recommendation_label(record.recommendation),
                    retry=record.retry_count,
                    before=record.metrics.original_perplexity,
                    after=record.metrics.rewritten_perplexity,
                    template=record.metrics.template_reduction,
                    citation=record.metrics.citation_retention,
                )
            )
        else:
            lines.append(f"  段落 {record.index + 1}: 状态={status_label(record.status)}, 重试={record.retry_count} 次")
        for warning in record.warnings:
            lines.append(f"    - {warning}")
        for flag in record.risk_flags:
            lines.append(f"    风险标记: {risk_flag_label(flag)}")
    lines.extend(["", "人工复核清单:"])
    if state.review_items:
        lines.extend(f"  - {item}" for item in state.review_items)
    else:
        lines.append("  - 未发现额外段落级风险；仍需人工复核事实、术语和引注。")
    lines.extend(["", "合规提示:"])
    lines.append("  - 本工具只用于自有草稿的学术表达质量提升与风格风险诊断。")
    lines.append("  - 指标为本地代理指标，不能代表任何 AI 检测器结果。")
    lines.append("  - 请人工复核事实、术语、引注和论点是否保持一致。")
    if fallback_indexes:
        lines.append(f"  - 以下段落因处理失败或质量不足已保留原文: {fallback_indexes}")
    return "\n".join(lines)


def build_review_checklist(state: AgentState) -> str:
    lines = [
        "=== PaperShield 人工复核清单 ===",
        "",
        "请在提交或引用前逐项核对：",
    ]
    if state.review_items:
        lines.extend(f"- {item}" for item in state.review_items)
    else:
        lines.append("- 复核事实、术语、论点和引注位置是否与原文一致。")
    lines.extend(
        [
            "- 确认没有新增事实、数据、文献或结论。",
            "- 确认报告指标仅作为本地代理信号使用。",
        ]
    )
    return "\n".join(lines)


def build_review_markdown(state: AgentState) -> str:
    lines = [
        "# PaperShield 人工复核清单",
        "",
        "请在提交或引用前逐项核对：",
    ]
    if state.review_items:
        lines.extend(f"- [ ] {item}" for item in state.review_items)
    else:
        lines.append("- [ ] 复核事实、术语、论点和引注位置是否与原文一致。")
    lines.extend(
        [
            "- [ ] 确认没有新增事实、数据、文献或结论。",
            "- [ ] 确认报告指标仅作为本地代理信号使用。",
        ]
    )
    return "\n".join(lines)


def build_report_html(state: AgentState) -> str:
    paragraphs = "\n".join(f"<p>{escape(line) or '&nbsp;'}</p>" for line in state.report.splitlines())
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>PaperShield 合规润色诊断报告</title>
    <style>
      body {{ max-width: 920px; margin: 40px auto; color: #16211d; font-family: Georgia, "Microsoft YaHei", serif; line-height: 1.7; }}
      h1 {{ font-size: 28px; }}
      p {{ margin: 0 0 8px; white-space: pre-wrap; }}
    </style>
  </head>
  <body>
    <h1>PaperShield 合规润色诊断报告</h1>
    {paragraphs}
  </body>
</html>"""


def build_report_dict(state: AgentState, elapsed_seconds: float = 0.0) -> dict:
    records = state.processed_paragraphs
    avg_original = _avg([record.metrics.original_perplexity for record in records if record.metrics])
    avg_rewritten = _avg([record.metrics.rewritten_perplexity for record in records if record.metrics])
    avg_change = ((avg_rewritten - avg_original) / avg_original) if avg_original else 0.0
    return {
        "domain": state.domain,
        "prompt_profile": state.prompt_profile,
        "source_format": state.source_format,
        "analysis_only": state.analysis_only,
        "paragraph_count": len(records),
        "retry_count": sum(record.retry_count for record in records),
        "elapsed_seconds": round(elapsed_seconds, 4),
        "final_text": state.final_text,
        "report": state.report,
        "analysis_summary": state.analysis_summary,
        "metrics": {
            "average_original_perplexity": avg_original,
            "average_rewritten_perplexity": avg_rewritten,
            "average_perplexity_change": avg_change,
            "average_template_reduction": _avg([record.metrics.template_reduction for record in records if record.metrics]),
            "average_citation_retention": _avg([record.metrics.citation_retention for record in records if record.metrics]),
        },
        "workflow": _workflow_payload(state),
        "paragraphs": [_paragraph_to_dict(record) for record in records],
        "provider_error": _provider_error_payload(records),
        "document_blocks": _document_blocks_to_dict(state),
        "warnings": state.warnings,
        "review_items": state.review_items,
        "compliance": {
            "boundary": "Only use on drafts you are allowed to edit.",
            "detector_claim": "Metrics are local proxy signals, not external AI detector results.",
            "manual_review": "Manually verify facts, terms, claims, and citations.",
        },
    }


def _workflow_payload(state: AgentState) -> dict:
    nodes = state.metrics.get("workflow_nodes", [])
    node_list = list(nodes) if isinstance(nodes, list) else []
    backend = state.metrics.get("workflow_backend", "unknown")
    route = state.metrics.get("workflow_route", "unknown")
    manual_required = bool(state.metrics.get("manual_review_required", False))
    return {
        "backend": backend,
        "backend_label": backend_label(backend),
        "nodes": node_list,
        "steps": workflow_step_payload(node_list),
        "route": route,
        "route_label": route_label(route),
        "manual_review_required": manual_required,
        "manual_review_label": manual_review_label(manual_required),
    }


def _document_blocks_to_dict(state: AgentState) -> list[dict]:
    if state.parsed is None:
        return []
    blocks: list[dict] = []
    for block in state.parsed.blocks:
        if block.kind == "paragraph":
            report_index = None if block.paragraph_index is None else block.paragraph_index + 1
            blocks.append(
                {
                    "kind": "paragraph",
                    "text": None,
                    "paragraph_index": block.paragraph_index,
                    "paragraph_report_index": report_index,
                }
            )
            continue
        blocks.append(
            {
                "kind": block.kind,
                "text": restore_citations(block.text, state.parsed.citation_map),
                "paragraph_index": None,
                "paragraph_report_index": None,
            }
        )
    return blocks


def _paragraph_to_dict(record: ParagraphRecord) -> dict:
    metrics = record.metrics
    return {
        "index": record.index + 1,
        "status": record.status,
        "status_label": status_label(record.status),
        "retry_count": record.retry_count,
        "original_text": record.original_text,
        "rewritten_text": record.rewritten_text,
        "risk_flags": record.risk_flags,
        "risk_flag_labels": [risk_flag_label(flag) for flag in record.risk_flags],
        "recommendation": record.recommendation,
        "recommendation_label": recommendation_label(record.recommendation),
        "warnings": record.warnings,
        "review_items": record.review_items,
        "fidelity": record.fidelity,
        "diff_segments": record.diff_segments,
        "metrics": None
        if metrics is None
        else {
            "original_perplexity": metrics.original_perplexity,
            "rewritten_perplexity": metrics.rewritten_perplexity,
            "perplexity_change": metrics.perplexity_change,
            "original_sentence_variation": metrics.original_sentence_variation,
            "rewritten_sentence_variation": metrics.rewritten_sentence_variation,
            "sentence_variation_change": metrics.sentence_variation_change,
            "template_reduction": metrics.template_reduction,
            "citation_retention": metrics.citation_retention,
            "score": metrics.score,
            "passed": metrics.passed,
        },
    }


def _provider_error_payload(records: list[ParagraphRecord]) -> dict:
    fallback_count = sum(1 for record in records if record.status == "fallback")
    provider_warnings = [
        warning
        for record in records
        for warning in record.warnings
        if _looks_like_provider_warning(warning)
    ]
    failed = bool(provider_warnings)
    all_fallback = bool(records) and fallback_count == len(records)
    return {
        "failed": failed,
        "message": _friendly_provider_error_message(provider_warnings[0], all_fallback) if failed else "",
        "all_fallback": all_fallback,
        "fallback_count": fallback_count,
        "warning_count": len(provider_warnings),
        "details": [_sanitize_provider_warning(warning) for warning in provider_warnings[:3]],
    }


def _analysis_summary_lines(summary: dict) -> list[str]:
    lines = ["文章级分析:"]
    overview = str(summary.get("overview") or "").strip()
    if overview:
        lines.append(f"  概述: {overview}")
    for label, key in [("优势", "strengths"), ("问题", "issues"), ("建议", "suggestions")]:
        values = summary.get(key) or []
        if values:
            lines.append(f"  {label}:")
            lines.extend(f"    - {value}" for value in values)
    scope = summary.get("scope") or {}
    if scope:
        lines.append(
            "  范围: 正文段落 {paragraphs} 段，跳过非正文块 {blocks} 个".format(
                paragraphs=scope.get("analyzed_paragraphs", 0),
                blocks=scope.get("skipped_blocks", 0),
            )
        )
    return lines


def _looks_like_provider_warning(warning: str) -> bool:
    lowered = warning.lower()
    markers = [
        "paragraph processing failed",
        "llm provider",
        "provider request",
        "missing api key",
        "http 401",
        "http 403",
        "http 429",
        "http 503",
        "quota",
        "resource_exhausted",
        "model not found",
        "urlopen error",
        "connection refused",
    ]
    return any(marker in lowered for marker in markers)


def _friendly_provider_error_message(warning: str, all_fallback: bool) -> str:
    lowered = warning.lower()
    suffix = " Original text was preserved." if all_fallback else " Some paragraphs were preserved."
    status_code = _extract_http_status(warning)
    if "missing api key" in lowered:
        return "Model call failed: missing API key." + suffix
    if "base url" in lowered and ("missing" in lowered or "required" in lowered):
        return "Model call failed: base URL is missing for the selected provider." + suffix
    if status_code in {401, 403}:
        return f"Model call failed: authentication or permission error (HTTP {status_code})." + suffix
    if status_code == 429 or "quota" in lowered or "resource_exhausted" in lowered or "rate limit" in lowered:
        return "Model call failed: quota or rate limit reached. Reduce paragraph count, switch model, or wait for quota to recover." + suffix
    if status_code in {404, 400} and "model" in lowered:
        return f"Model call failed: model not found or unavailable (HTTP {status_code})." + suffix
    if status_code == 503:
        return "Model call failed: provider service unavailable (HTTP 503)." + suffix
    if status_code:
        return f"Model call failed: provider returned HTTP {status_code}." + suffix
    return "Model call failed. Check API key, base URL, model name, quota, and network access." + suffix


def _extract_http_status(warning: str) -> int | None:
    match = re.search(r"http\D{0,12}([1-5]\d\d)", warning, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _sanitize_provider_warning(warning: str) -> str:
    sanitized = warning
    sanitized = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer <hidden>", sanitized)
    sanitized = re.sub(r"(api[_-]?key['\"]?\s*[:=]\s*)['\"]?[^,'\"\s}]+", r"\1<hidden>", sanitized, flags=re.IGNORECASE)
    return sanitized[:500]


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
