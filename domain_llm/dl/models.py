"""知识条目与检索结果的数据结构。"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Chunk:
    doc_no: str                 # 文号，如 金监发〔2026〕1号
    doc_title: str
    version: str                # 版本，如 v1.0 / 2026-01-01
    article: str                # 条款号，如 第三条
    section: str                # 所属章节
    text: str
    effective_date: str = ""    # 生效日期 YYYY-MM-DD
    status: str = "active"      # active / abolished
    tags: list[str] = field(default_factory=list)

    @property
    def chunk_id(self) -> str:
        return f"{self.doc_no}#{self.article}"

    @property
    def citation(self) -> str:
        return f"《{self.doc_title}》（{self.doc_no}）{self.article}"

    def embed_text(self) -> str:
        """带上下文的嵌入文本：标题 + 章节 + 条款，避免断章取义。"""
        return f"{self.doc_title} {self.section} {self.article} {self.text}"


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
    stage: str = "dense"        # dense / sparse / rerank
    debug: dict = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
