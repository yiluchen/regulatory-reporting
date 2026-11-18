"""精排：线上用 bge-reranker-v2-m3（Cross-Encoder），离线用词面匹配兜底。

精排专门治「逾期天数」和「逾期账龄」这类看着像、口径完全不同的条款。
"""
from __future__ import annotations

import re

from .models import Chunk
from .sparse import tokenize

CITATION_RE = re.compile(r"第[一二三四五六七八九十百零〇\d]+条")


class LexicalReranker:
    """离线兜底：查询词覆盖率 + 条款号精确命中加权。"""

    name = "lexical-fallback"

    def score(self, query: str, chunk: Chunk) -> float:
        q = set(tokenize(query))
        d = set(tokenize(chunk.embed_text()))
        if not q:
            return 0.0
        overlap = len(q & d) / len(q)
        bonus = 0.25 if any(art in query for art in CITATION_RE.findall(chunk.article)) else 0.0
        return overlap + bonus

    def rerank(self, query: str, chunks: list[tuple[Chunk, float]]) -> list[tuple[Chunk, float]]:
        scored = [(c, self.score(query, c)) for c, _ in chunks]
        return sorted(scored, key=lambda x: x[1], reverse=True)


class CrossEncoderReranker:
    """bge-reranker-v2-m3。query 与 chunk 原文拼对打分。"""

    name = "bge-reranker-v2-m3"

    def __init__(self, model_path: str = "BAAI/bge-reranker-v2-m3") -> None:
        from FlagEmbedding import FlagReranker  # 延迟导入

        self.model = FlagReranker(model_path, use_fp16=True)

    def rerank(self, query: str, chunks: list[tuple[Chunk, float]]) -> list[tuple[Chunk, float]]:
        pairs = [[query, c.text] for c, _ in chunks]
        scores = self.model.compute_score(pairs, normalize=True)
        if isinstance(scores, float):
            scores = [scores]
        merged = [(c, float(s)) for (c, _), s in zip(chunks, scores)]
        return sorted(merged, key=lambda x: x[1], reverse=True)


def build_reranker(offline: bool = False):
    if offline:
        return LexicalReranker()
    try:
        return CrossEncoderReranker()
    except Exception:  # noqa: BLE001 - 无模型权重时降级
        return LexicalReranker()
