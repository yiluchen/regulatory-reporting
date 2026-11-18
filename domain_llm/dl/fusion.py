"""RRF 融合：把稠密与稀疏两路召回按排名融合，避免单路漏召。"""
from __future__ import annotations


def reciprocal_rank_fusion(
    rankings: list[list[tuple[int, float]]], k: int = 60
) -> list[tuple[int, float]]:
    """rankings: 每路 [(下标, 分数)]，已按分数降序。返回 [(下标, RRF 分)]。"""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, (idx, _score) in enumerate(ranking, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda x: x[1], reverse=True)
