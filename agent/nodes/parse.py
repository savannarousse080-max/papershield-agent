from __future__ import annotations

import re

from agent.state import ParsedDocument, TextBlock
from utils.citation_handler import protect_citations


TITLE_PATTERN = re.compile(
    r"^\s*(第[一二三四五六七八九十\d]+[章节].{0,30}|[一二三四五六七八九十]+、.{0,30}|#{1,6}\s+.{1,60}|[0-9]+[.、]\s*\S.{0,30})\s*$"
)
FIGURE_PATTERN = re.compile(r"^\s*(图)\s*\d+|^\s*Figure\s+\d+", re.IGNORECASE)
TABLE_PATTERN = re.compile(r"^\s*(表)\s*\d+|^\s*Table\s+\d+", re.IGNORECASE)
REFERENCES_PATTERN = re.compile(r"^\s*(参考文献|References|Bibliography)\s*$", re.IGNORECASE)
ABSTRACT_PATTERN = re.compile(r"^\s*(摘要|Abstract)\s*[:：]?", re.IGNORECASE)
KEYWORDS_PATTERN = re.compile(r"^\s*(关键词|关键字|Keywords?)\s*[:：]?", re.IGNORECASE)
METADATA_PATTERN = re.compile(
    r"^\s*(作者|姓名|学号|学院|院系|专业|班级|课程|指导教师|导师|联系方式|邮箱|电子邮箱|电话|单位|学校|日期)\s*[:：]?.{0,80}$",
    re.IGNORECASE,
)
PLAIN_HEADING_TERMS = {
    "绪论",
    "引言",
    "问题提出",
    "研究背景",
    "文献综述",
    "理论基础",
    "研究方法",
    "模型设定",
    "实证分析",
    "案例分析",
    "讨论",
    "结论",
    "结语",
    "附录",
}


def parse_text(raw_text: str) -> ParsedDocument:
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ParsedDocument(blocks=[], citation_map={})

    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", normalized) if chunk.strip()]
    blocks: list[TextBlock] = []
    citation_map: dict[str, str] = {}
    next_ref = 1
    paragraph_index = 0
    reference_chunks: list[str] = []
    in_references = False
    body_seen = False

    for chunk_position, chunk in enumerate(chunks):
        if in_references:
            reference_chunks.append(chunk)
            continue
        if REFERENCES_PATTERN.match(chunk.splitlines()[0].strip()):
            in_references = True
            reference_chunks.append(chunk)
            continue
        block_kind = _classify_chunk(chunk, chunk_position, body_seen)
        if block_kind != "paragraph":
            blocks.append(TextBlock(kind=block_kind, text=chunk))
            continue

        protected, chunk_map, next_ref = protect_citations(chunk, next_ref)
        citation_map.update(chunk_map)
        blocks.append(TextBlock(kind="paragraph", text=protected, paragraph_index=paragraph_index))
        paragraph_index += 1
        body_seen = True

    if reference_chunks:
        blocks.append(TextBlock(kind="references", text="\n\n".join(reference_chunks)))

    return ParsedDocument(blocks=blocks, citation_map=citation_map)


def _is_preserved_chunk(chunk: str) -> bool:
    return _classify_chunk(chunk, 0, False) != "paragraph"


def _classify_chunk(chunk: str, chunk_position: int, body_seen: bool) -> str:
    lines = [line.strip() for line in chunk.splitlines() if line.strip()]
    if not lines:
        return "preserved"
    first_line = lines[0]
    if ABSTRACT_PATTERN.match(first_line):
        return "abstract"
    if KEYWORDS_PATTERN.match(first_line):
        return "keywords"
    if len(lines) != 1:
        return "paragraph"
    line = lines[0]
    if FIGURE_PATTERN.match(line):
        return "figure"
    if TABLE_PATTERN.match(line):
        return "table"
    if TITLE_PATTERN.match(line) or _is_plain_heading(line):
        return "heading"
    if not body_seen and _is_front_matter_metadata(line, chunk_position):
        return "metadata"
    return "paragraph"


def _is_plain_heading(line: str) -> bool:
    normalized = line.strip().strip("：:")
    if normalized in PLAIN_HEADING_TERMS:
        return True
    if re.search(r"(论文|课程论文|毕业设计|开题报告|研究报告)$", normalized):
        return True
    if len(normalized) > 32:
        return False
    if re.search(r"[。！？!?；;，,]", normalized):
        return False
    return any(term in normalized for term in PLAIN_HEADING_TERMS)


def _is_front_matter_metadata(line: str, chunk_position: int) -> bool:
    if METADATA_PATTERN.match(line):
        return True
    normalized = line.strip()
    if chunk_position <= 6 and re.fullmatch(r"[\u4e00-\u9fff]{2,8}", normalized):
        return True
    return False
