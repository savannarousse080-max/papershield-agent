from __future__ import annotations

from agent.fidelity import analyze_fidelity, build_diff_segments
from agent.state import ParagraphRecord


def annotate_paragraph(record: ParagraphRecord) -> ParagraphRecord:
    flags: list[str] = []
    items: list[str] = []
    metrics = record.metrics
    paragraph_label = f"段落 {record.index + 1}"
    fidelity = analyze_fidelity(record.original_text, record.rewritten_text)
    record.fidelity = {
        "added_terms_count": fidelity.added_terms_count,
        "term_change_count": fidelity.term_change_count,
        "unchanged": fidelity.unchanged,
    }
    record.diff_segments = build_diff_segments(record.original_text, record.rewritten_text)

    if record.status == "fallback":
        flags.append("fallback_original_retained")
        items.append(f"{paragraph_label}: 处理失败或引用保护风险较高，已保留原文，请重点复核。")
    elif record.status == "below_threshold":
        flags.append("below_quality_threshold")
        items.append(f"{paragraph_label}: 组合指标未达阈值，建议人工判断是否采用润色结果。")
    else:
        items.append(f"{paragraph_label}: 复核事实、术语、论点和引注位置是否与原文一致。")

    if metrics is not None:
        if metrics.citation_retention < 1.0:
            flags.append("citation_retention_risk")
            items.append(f"{paragraph_label}: 引注数量未完全保留，需要逐条核对。")
        if metrics.template_reduction < 0.75:
            flags.append("template_word_residue")
            items.append(f"{paragraph_label}: 模板化连接词减少不足，可考虑人工精修。")
        if metrics.sentence_variation_change < 0:
            flags.append("sentence_variation_reduced")
            items.append(f"{paragraph_label}: 句长变化下降，注意避免新的机械化表达。")

    for flag in fidelity.risk_flags:
        if not (record.status == "analysis_only" and flag == "unchanged_output"):
            flags.append(flag)
    for item in fidelity.review_items:
        if not (record.status == "analysis_only" and "润色结果与原文基本一致" in item):
            items.append(f"{paragraph_label}: {item}")

    if record.warnings:
        flags.append("provider_warning")
        for warning in record.warnings:
            items.append(f"{paragraph_label}: {warning}")

    record.risk_flags = _dedupe(flags)
    record.review_items = _dedupe(items)
    record.recommendation = _recommendation(record)
    return record


def aggregate_review_items(records: list[ParagraphRecord]) -> list[str]:
    items: list[str] = []
    for record in records:
        items.extend(record.review_items)
    return _dedupe(items)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _recommendation(record: ParagraphRecord) -> str:
    if record.status == "fallback":
        return "keep_original"
    review_flags = {
        "below_quality_threshold",
        "citation_retention_risk",
        "semantic_addition_risk",
        "term_change_risk",
        "provider_warning",
        "sentence_variation_reduced",
    }
    if record.status in {"below_threshold", "analysis_only"}:
        return "review"
    if any(flag in review_flags for flag in record.risk_flags):
        return "review"
    return "accept"
