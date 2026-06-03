from __future__ import annotations


STATUS_LABELS = {
    "accepted": "已通过",
    "below_threshold": "低于质量阈值",
    "fallback": "已保留原文",
    "analysis_only": "仅分析",
    "pending": "待处理",
}

RISK_FLAG_LABELS = {
    "fallback_original_retained": "原文兜底保留",
    "below_quality_threshold": "低于质量阈值",
    "citation_retention_risk": "引注保留风险",
    "template_word_residue": "模板化表达残留",
    "sentence_variation_reduced": "句式变化下降",
    "provider_warning": "模型调用警告",
    "unchanged_output": "润色结果未变化",
    "semantic_addition_risk": "疑似新增事实",
    "term_change_risk": "术语变化风险",
}

RECOMMENDATION_LABELS = {
    "accept": "建议采纳",
    "review": "建议复核",
    "keep_original": "建议保留原文",
}


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", "未知状态")


def risk_flag_label(flag: str | None) -> str:
    return RISK_FLAG_LABELS.get(flag or "", "未知风险")


def recommendation_label(value: str | None) -> str:
    return RECOMMENDATION_LABELS.get(value or "", "建议复核")
