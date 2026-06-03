from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scorer.metrics import TextPairMetrics


@dataclass
class TextBlock:
    kind: str
    text: str
    paragraph_index: int | None = None


@dataclass
class ParsedDocument:
    blocks: list[TextBlock]
    citation_map: dict[str, str]

    @property
    def paragraphs(self) -> list[TextBlock]:
        return [block for block in self.blocks if block.kind == "paragraph"]


@dataclass
class ParagraphRecord:
    index: int
    original_text: str
    rewritten_text: str
    protected_original: str
    protected_rewritten: str
    retry_count: int = 0
    status: str = "pending"
    metrics: TextPairMetrics | None = None
    warnings: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    review_items: list[str] = field(default_factory=list)
    recommendation: str = "accept"
    fidelity: dict[str, Any] = field(default_factory=dict)
    diff_segments: list[dict[str, str]] = field(default_factory=list)


@dataclass
class AgentState:
    raw_text: str
    domain: str
    source_format: str = "txt"
    analysis_only: bool = False
    prompt_profile: str = "default"
    parsed: ParsedDocument | None = None
    processed_paragraphs: list[ParagraphRecord] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    review_items: list[str] = field(default_factory=list)
    analysis_summary: dict[str, Any] | None = None
    final_text: str = ""
    report: str = ""
