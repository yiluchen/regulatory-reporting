"""BM25 稀疏检索（纯 Python）。

中文用「单字 + 相邻二元组」切分，英文/数字按词切分，
不依赖分词器即可在离线环境复现混合检索里的稀疏一路。
"""
from __future__ import annotations

import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    chars = TOKEN_RE.findall(text)
    tokens: list[str] = []
    for i, tok in enumerate(chars):
        tokens.append(tok)
        if i + 1 < len(chars) and len(tok) == 1 and len(chars[i + 1]) == 1:
            if "\u4e00" <= tok <= "\u9fff" and "\u4e00" <= chars[i + 1] <= "\u9fff":
                tokens.append(tok + chars[i + 1])
    return tokens


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = [Counter(tokenize(d)) for d in docs]
        self.lengths = [sum(c.values()) for c in self.corpus]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.df: Counter = Counter()
        for counter in self.corpus:
            self.df.update(counter.keys())

    def _idf(self, term: str, n: int) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def scores(self, query: str) -> list[float]:
        n = len(self.corpus)
        terms = tokenize(query)
        result: list[float] = []
        for counter, length in zip(self.corpus, self.lengths):
            score = 0.0
            for term in terms:
                tf = counter.get(term, 0)
                if not tf:
                    continue
                norm = 1 - self.b + self.b * (length / (self.avg_len or 1))
                score += self._idf(term, n) * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)
            result.append(score)
        return result

    def top_k(self, query: str, k: int = 20) -> list[tuple[int, float]]:
        scores = self.scores(query)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in ranked[:k] if s > 0]
