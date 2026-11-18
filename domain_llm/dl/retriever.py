"""三阶段检索：稠密 top-20 ‖ 稀疏 top-20 → RRF → 精排 top-5。"""
from __future__ import annotations

from datetime import date

from .embedding import build_embedder, cosine
from .fusion import reciprocal_rank_fusion
from .models import Chunk, ScoredChunk
from .rerank import build_reranker
from .sparse import BM25


class HybridRetriever:
    def __init__(
        self,
        chunks: list[Chunk],
        *,
        embedder=None,
        reranker=None,
        dense_k: int = 20,
        sparse_k: int = 20,
        final_k: int = 5,
        offline: bool = False,
    ) -> None:
        self.chunks = chunks
        self.embedder = embedder or build_embedder(offline=offline)
        self.reranker = reranker or build_reranker(offline=offline)
        self.dense_k = dense_k
        self.sparse_k = sparse_k
        self.final_k = final_k

        self._texts = [c.embed_text() for c in chunks]
        self._vectors = self.embedder.encode(self._texts) if chunks else []
        self._bm25 = BM25(self._texts) if chunks else None

    def _allowed(self, index: int, as_of: str | None, include_abolished: bool) -> bool:
        chunk = self.chunks[index]
        if not include_abolished and chunk.status != "active":
            return False
        if as_of and chunk.effective_date and chunk.effective_date > as_of:
            return False
        return True

    def search(
        self,
        query: str,
        *,
        as_of: str | None = None,
        include_abolished: bool = False,
        top_k: int | None = None,
    ) -> list[ScoredChunk]:
        if not self.chunks:
            return []
        as_of = as_of or date.today().isoformat()

        query_vec = self.embedder.encode([query])[0]
        dense_all = [
            (i, cosine(query_vec, vec)) for i, vec in enumerate(self._vectors)
            if self._allowed(i, as_of, include_abolished)
        ]
        dense = sorted(dense_all, key=lambda x: x[1], reverse=True)[: self.dense_k]

        sparse_all = [
            (i, s) for i, s in (self._bm25.top_k(query, k=len(self.chunks)) if self._bm25 else [])
            if self._allowed(i, as_of, include_abolished)
        ][: self.sparse_k]

        fused = reciprocal_rank_fusion([dense, sparse_all])
        pool = [(self.chunks[i], score) for i, score in fused[: max(self.dense_k, self.sparse_k)]]
        reranked = self.reranker.rerank(query, pool)

        limit = top_k or self.final_k
        return [
            ScoredChunk(chunk=chunk, score=float(score), stage="rerank")
            for chunk, score in reranked[:limit]
        ]
