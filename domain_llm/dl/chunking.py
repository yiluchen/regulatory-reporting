"""条款级分块：按「第X条」切，保留文号、版本、章节与生效日期。

按字数硬切会把一句话切断；按条款切每块语义完整，检索时还能带上下文。
"""
from __future__ import annotations

import re

from .models import Chunk

ARTICLE_RE = re.compile(r"^第[一二三四五六七八九十百零〇\d]+条")
CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十]+章")


def _split_articles(text: str) -> list[tuple[str, str]]:
    """返回 [(所属章节, 以「第X条」开头的原文块)]。"""
    section = ""
    blocks: list[tuple[str, str]] = []
    current: list[str] = []
    current_section = ""

    def flush() -> None:
        if current:
            blocks.append((current_section, "\n".join(current).strip()))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            flush()
            current = []
            section = line.lstrip("# ").strip()
            continue
        if CHAPTER_RE.match(line):
            flush()
            current = []
            section = line
            continue
        if ARTICLE_RE.match(line):
            flush()
            current = [line]
            current_section = section
        elif current:
            current.append(line)
    flush()
    return [(sec, blk) for sec, blk in blocks if blk]


def chunk_document(
    text: str,
    *,
    doc_no: str,
    doc_title: str,
    version: str,
    effective_date: str = "",
    status: str = "active",
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section, block in _split_articles(text):
        first_line = block.splitlines()[0].strip()
        match = ARTICLE_RE.match(first_line)
        article = match.group(0) if match else "全文"
        chunks.append(
            Chunk(
                doc_no=doc_no,
                doc_title=doc_title,
                version=version,
                article=article,
                section=section,
                text=block,
                effective_date=effective_date,
                status=status,
            )
        )
    return chunks
