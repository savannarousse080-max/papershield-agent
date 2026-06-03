from __future__ import annotations

from scorer.metrics import TextPairMetrics, evaluate_text_pair


def score_paragraph(original: str, rewritten: str) -> TextPairMetrics:
    return evaluate_text_pair(original, rewritten)
