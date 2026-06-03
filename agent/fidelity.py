from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field


FACT_PATTERNS = [
    re.compile(r"(?:19|20)\d{2}年?"),
    re.compile(r"\d+(?:\.\d+)?%"),
    re.compile(r"(司法解释|判决|数据|调查|研究|报告|统计|新增)"),
]

DOMAIN_TERMS = [
    "法益",
    "注意义务",
    "构成要件",
    "司法解释",
    "市场失灵",
    "信息不对称",
    "边际成本",
    "平台治理",
    "数据安全",
]


@dataclass
class FidelityResult:
    risk_flags: list[str] = field(default_factory=list)
    review_items: list[str] = field(default_factory=list)
    added_terms_count: int = 0
    term_change_count: int = 0
    unchanged: bool = False


def analyze_fidelity(original: str, rewritten: str) -> FidelityResult:
    result = FidelityResult()
    normalized_original = _normalize(original)
    normalized_rewritten = _normalize(rewritten)
    result.unchanged = normalized_original == normalized_rewritten

    added_facts = _new_matches(original, rewritten, FACT_PATTERNS)
    if added_facts:
        result.added_terms_count = len(added_facts)
        result.risk_flags.append("semantic_addition_risk")
        result.review_items.append(f"疑似新增事实或依据: {'、'.join(added_facts[:3])}，请确认是否来自原文。")

    added_terms = [term for term in DOMAIN_TERMS if term in rewritten and term not in original]
    removed_terms = [term for term in DOMAIN_TERMS if term in original and term not in rewritten]
    changed_terms = added_terms + removed_terms
    if changed_terms:
        result.term_change_count = len(changed_terms)
        result.risk_flags.append("term_change_risk")
        result.review_items.append(f"术语变化: {'、'.join(changed_terms[:4])}，请确认没有改变论证含义。")

    if result.unchanged:
        result.risk_flags.append("unchanged_output")
        result.review_items.append("润色结果与原文基本一致，可考虑人工判断是否需要继续优化。")

    return result


def build_diff_segments(original: str, rewritten: str) -> list[dict[str, str]]:
    segments: list[dict[str, str]] = []
    matcher = difflib.SequenceMatcher(a=original, b=rewritten)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            _append_segment(segments, "equal", original[i1:i2])
        elif tag == "delete":
            _append_segment(segments, "delete", original[i1:i2])
        elif tag == "insert":
            _append_segment(segments, "insert", rewritten[j1:j2])
        elif tag == "replace":
            _append_segment(segments, "delete", original[i1:i2])
            _append_segment(segments, "insert", rewritten[j1:j2])
    return [segment for segment in segments if segment["text"]]


def _new_matches(original: str, rewritten: str, patterns: list[re.Pattern[str]]) -> list[str]:
    original_matches = set()
    rewritten_matches = []
    for pattern in patterns:
        original_matches.update(match.group(0) for match in pattern.finditer(original))
        rewritten_matches.extend(match.group(0) for match in pattern.finditer(rewritten))
    return [match for match in _dedupe(rewritten_matches) if match not in original_matches]


def _append_segment(segments: list[dict[str, str]], op: str, text: str) -> None:
    if not text:
        return
    if segments and segments[-1]["op"] == op:
        segments[-1]["text"] += text
        return
    segments.append({"op": op, "text": text})


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
