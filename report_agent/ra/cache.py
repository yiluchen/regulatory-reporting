"""两级语义缓存：L1 精确命中（Redis），L2 向量近似（pgvector）。

只有人工审核过的标准答案才允许被缓存命中——缓存不是"猜答案"。
"""
from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass, field


def _tokens(text: str) -> set[str]:
    """离线兜底用字符集合；线上换成 BGE-M3 向量后，L2 阈值按余弦相似度解释。"""
    return set(re.findall(r"[\u4e00-\u9fffa-zA-Z0-9]", text.lower()))


def _cosine(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


@dataclass
class CacheEntry:
    question: str
    answer: str
    citations: list[str] = field(default_factory=list)
    reviewed: bool = False
    created_at: float = field(default_factory=time.time)
    hits: int = 0
    tokens: set[str] = field(default_factory=set, repr=False)


@dataclass
class CacheHit:
    layer: str            # L1 / L2
    answer: str
    citations: list[str]
    score: float = 1.0


class SemanticCache:
    def __init__(self, threshold: float = 0.90, ttl: float = 3600.0, max_size: int = 2000) -> None:
        self.threshold = threshold
        self.ttl = ttl
        self.max_size = max_size
        self._entries: dict[str, CacheEntry] = {}

    @staticmethod
    def _key(question: str) -> str:
        normalized = re.sub(r"\s+", "", question.lower())
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def put(
        self, question: str, answer: str, citations: list[str] | None = None,
        reviewed: bool = False, now: float | None = None,
    ) -> None:
        now = now or time.time()
        key = self._key(question)
        self._entries[key] = CacheEntry(
            question=question,
            answer=answer,
            citations=list(citations or []),
            reviewed=reviewed,
            created_at=now,
            tokens=_tokens(question),
        )
        if len(self._entries) > self.max_size:
            oldest = min(self._entries.items(), key=lambda kv: kv[1].created_at)
            self._entries.pop(oldest[0], None)

    def _alive(self, entry: CacheEntry, now: float) -> bool:
        return entry.reviewed and (now - entry.created_at) <= self.ttl

    def get(self, question: str, now: float | None = None) -> CacheHit | None:
        now = now or time.time()

        # L1：精确命中
        key = self._key(question)
        entry = self._entries.get(key)
        if entry and self._alive(entry, now):
            entry.hits += 1
            return CacheHit("L1", entry.answer, entry.citations, 1.0)

        # L2：语义近似，仅比较已审核且在有效期内的条目
        tokens = _tokens(question)
        best: tuple[CacheEntry, float] | None = None
        for item in self._entries.values():
            if not self._alive(item, now):
                continue
            score = _cosine(tokens, item.tokens)
            if best is None or score > best[1]:
                best = (item, score)
        if best and best[1] >= self.threshold:
            best[0].hits += 1
            return CacheHit("L2", best[0].answer, best[0].citations, round(best[1], 4))
        return None

    def stats(self) -> dict:
        return {
            "entries": len(self._entries),
            "reviewed": sum(1 for e in self._entries.values() if e.reviewed),
            "hits": sum(e.hits for e in self._entries.values()),
        }
