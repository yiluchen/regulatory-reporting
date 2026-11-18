"""检索评测：recall@k / precision@k / 口径命中率。"""
from __future__ import annotations


def evaluate_retrieval(retriever, cases: list[dict], k: int = 5) -> dict:
    hits = 0
    precision_sum = 0.0
    misses: list[dict] = []

    for case in cases:
        results = retriever.search(case["q"], top_k=k)
        ids = [r.chunk_id for r in results]
        gold = set(case.get("gold", []))
        hit = bool(gold & set(ids))
        hits += int(hit)
        precision_sum += (len(gold & set(ids)) / max(1, min(k, len(ids)))) if ids else 0.0
        if not hit:
            misses.append({"q": case["q"], "gold": sorted(gold), "got": ids})

    total = max(1, len(cases))
    return {
        "cases": len(cases),
        f"recall@{k}": round(hits / total, 4),
        f"precision@{k}": round(precision_sum / total, 4),
        "misses": misses,
    }
