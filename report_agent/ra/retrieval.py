"""双路检索与图谱容错闭环。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from .state import Evidence


class ChunkRetriever(Protocol):
    def search(self, query: str, **kwargs): ...


def _to_evidence(scored, source: str) -> Evidence:
    chunk = scored.chunk
    return {
        "chunk_id": chunk.chunk_id,
        "doc_no": chunk.doc_no,
        "article": chunk.article,
        "doc_title": chunk.doc_title,
        "text": chunk.text,
        "source": source,
        "score": float(scored.score),
        "version": chunk.version,
        "effective_date": chunk.effective_date,
    }


@dataclass
class DualResult:
    evidences: list[Evidence] = field(default_factory=list)
    graph_rows: list[dict] = field(default_factory=list)
    degraded: bool = False


class DualRetriever:
    """监管发文与行内口径两路并行检索，结果在证据节点合并。"""

    def __init__(self, regulation: ChunkRetriever, bank: ChunkRetriever, graph=None) -> None:
        self.regulation = regulation
        self.bank = bank
        self.graph = graph

    def search_one(self, which: str, question: str, as_of: str | None) -> list[Evidence]:
        retriever = self.regulation if which == "regulation" else self.bank
        return [_to_evidence(s, which) for s in retriever.search(question, as_of=as_of)]

    def graph_query(self, question: str, generate_cypher: Callable[[str], str]) -> tuple[list[dict], bool]:
        """LLM 生成 Cypher → 执行；报错降级关键词检索，保证查询不中断。"""
        if self.graph is None:
            return [], False
        try:
            cypher = generate_cypher(question)
            return self.graph.run(cypher), False
        except Exception:  # noqa: BLE001 - 图查询失败必须降级而不是中断
            rows = self.graph.keyword_search(question) if hasattr(self.graph, "keyword_search") else []
            return rows, True
