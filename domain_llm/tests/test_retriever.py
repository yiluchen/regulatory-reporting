"""混合检索：召回、过滤、引用可回溯。"""
import json
from pathlib import Path

import pytest

from dl.evaluate import evaluate_retrieval
from dl.loader import load_chunks
from dl.models import Chunk
from dl.retriever import HybridRetriever

BASE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def retriever():
    return HybridRetriever(load_chunks(BASE / "data" / "docs"), offline=True, final_k=5)


def test_hits_expected_article(retriever):
    results = retriever.search("逾期天数怎么计算")
    ids = [r.chunk_id for r in results]
    assert "金监发〔2026〕1号#第四条" in ids


def test_distinguishes_similar_terms(retriever):
    """「逾期账龄」与「逾期天数」看着像，但必须各自命中对应条款。"""
    age = [r.chunk_id for r in retriever.search("逾期账龄如何划分区间")]
    days = [r.chunk_id for r in retriever.search("逾期天数怎么计算")]
    assert "金监发〔2026〕1号#第五条" in age
    assert "金监发〔2026〕1号#第四条" in days


def test_abolished_and_future_docs_are_filtered():
    chunks = [
        Chunk("A〔2026〕1号", "旧办法", "v1.0", "第一条", "", "旧口径", "2025-01-01", "abolished"),
        Chunk("A〔2026〕2号", "新办法", "v2.0", "第一条", "", "新口径", "2026-03-01", "active"),
    ]
    r = HybridRetriever(chunks, offline=True)
    assert [c.chunk_id for c in r.search("口径")] == ["A〔2026〕2号#第一条"]
    both = {c.chunk_id for c in r.search("口径", include_abolished=True)}
    assert both == {"A〔2026〕1号#第一条", "A〔2026〕2号#第一条"}
    assert r.search("口径", as_of="2026-01-01") == []


def test_eval_set_recall(retriever):
    cases = [
        json.loads(l)
        for l in (BASE / "data" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    metrics = evaluate_retrieval(retriever, cases, k=5)
    assert metrics["recall@5"] >= 0.9, metrics["misses"]
