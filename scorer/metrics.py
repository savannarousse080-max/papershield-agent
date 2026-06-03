from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass

from utils.citation_handler import count_citations


TEMPLATE_WORDS = ["此外", "因此", "综上所述", "值得注意的是", "不可忽视的是", "显著", "重要意义"]
SENTENCE_SPLIT_PATTERN = re.compile(r"[。！？；;]+")


@dataclass
class TextPairMetrics:
    original_perplexity: float
    rewritten_perplexity: float
    perplexity_change: float
    original_sentence_variation: float
    rewritten_sentence_variation: float
    sentence_variation_change: float
    template_reduction: float
    citation_retention: float
    score: float
    passed: bool


def template_word_count(text: str) -> int:
    return sum(text.count(word) for word in TEMPLATE_WORDS)


def sentence_lengths(text: str) -> list[int]:
    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_PATTERN.split(text) if sentence.strip()]
    return [len(sentence) for sentence in sentences]


def sentence_length_variation(text: str) -> float:
    lengths = sentence_lengths(text)
    if len(lengths) < 2:
        return 0.0
    return statistics.pstdev(lengths)


def heuristic_perplexity(text: str) -> float:
    tokens = [char for char in text if not char.isspace()]
    if not tokens:
        return 0.0
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    total = len(tokens)
    entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
    variation_bonus = 1 + min(sentence_length_variation(text), 20) / 50
    template_penalty = 1 / (1 + template_word_count(text) * 0.08)
    return math.exp(entropy) * variation_bonus * template_penalty


def citation_retention(original: str, rewritten: str) -> float:
    original_count = count_citations(original)
    if original_count == 0:
        return 1.0
    rewritten_count = count_citations(rewritten)
    return min(1.0, rewritten_count / original_count)


def evaluate_text_pair(original: str, rewritten: str) -> TextPairMetrics:
    original_ppl = heuristic_perplexity(original)
    rewritten_ppl = heuristic_perplexity(rewritten)
    perplexity_change = _relative_change(original_ppl, rewritten_ppl)

    original_variation = sentence_length_variation(original)
    rewritten_variation = sentence_length_variation(rewritten)
    variation_change = rewritten_variation - original_variation

    original_templates = template_word_count(original)
    rewritten_templates = template_word_count(rewritten)
    if original_templates == 0:
        template_reduction = 1.0 if rewritten_templates == 0 else 0.0
    else:
        template_reduction = max(0.0, (original_templates - rewritten_templates) / original_templates)

    retention = citation_retention(original, rewritten)
    score = (
        0.35 * min(1.0, max(0.0, template_reduction))
        + 0.25 * retention
        + 0.2 * min(1.0, max(0.0, perplexity_change + 0.2))
        + 0.2 * (1.0 if variation_change >= 0 else 0.0)
    )
    passed = retention >= 1.0 and template_reduction >= 0.75 and score >= 0.7
    return TextPairMetrics(
        original_perplexity=original_ppl,
        rewritten_perplexity=rewritten_ppl,
        perplexity_change=perplexity_change,
        original_sentence_variation=original_variation,
        rewritten_sentence_variation=rewritten_variation,
        sentence_variation_change=variation_change,
        template_reduction=template_reduction,
        citation_retention=retention,
        score=score,
        passed=passed,
    )


def _relative_change(original: float, new: float) -> float:
    if original == 0:
        return 0.0
    return (new - original) / original
