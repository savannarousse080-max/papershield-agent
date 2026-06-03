from __future__ import annotations

import re


CITATION_PATTERN = re.compile(
    r"(\{\{REF_\d+\}\}|\[\d+(?:[-,，]\d+)?\]|\([^)（）]*(?:19|20)\d{2}[a-zA-Z]?[^)（）]*\)|[¹²³⁴⁵⁶⁷⁸⁹⁰]+)"
)


def protect_citations(text: str, start_index: int = 1) -> tuple[str, dict[str, str], int]:
    citation_map: dict[str, str] = {}
    index = start_index

    def replace(match: re.Match[str]) -> str:
        nonlocal index
        original = match.group(0)
        if original.startswith("{{REF_"):
            return original
        placeholder = f"{{{{REF_{index}}}}}"
        citation_map[placeholder] = original
        index += 1
        return placeholder

    return CITATION_PATTERN.sub(replace, text), citation_map, index


def restore_citations(text: str, citation_map: dict[str, str]) -> str:
    restored = text
    for placeholder, original in citation_map.items():
        restored = restored.replace(placeholder, original)
    return restored


def count_citations(text: str) -> int:
    return len(CITATION_PATTERN.findall(text))
