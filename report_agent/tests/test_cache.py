"""两级语义缓存：只命中人工审核过的答案。"""
from ra.cache import SemanticCache


def test_unreviewed_never_returned():
    cache = SemanticCache()
    cache.put("逾期天数怎么计算", "自然日口径", reviewed=False)
    assert cache.get("逾期天数怎么计算") is None


def test_l1_exact_hit():
    cache = SemanticCache()
    cache.put("逾期天数怎么计算", "自然日口径", ["金监发〔2026〕1号#第四条"], reviewed=True)
    hit = cache.get("逾期天数  怎么计算")
    assert hit and hit.layer == "L1"


def test_l2_semantic_hit():
    cache = SemanticCache(threshold=0.9)
    cache.put("逾期天数怎么计算", "自然日口径", reviewed=True)
    hit = cache.get("逾期天数怎么计算呢")
    assert hit and hit.layer == "L2"
    assert 0.9 <= hit.score <= 1.0


def test_l2_miss_when_different_topic():
    cache = SemanticCache(threshold=0.9)
    cache.put("逾期天数怎么计算", "自然日口径", reviewed=True)
    assert cache.get("资本充足率怎么计算") is None


def test_ttl_expiry():
    cache = SemanticCache(ttl=10)
    cache.put("逾期天数怎么计算", "自然日口径", reviewed=True, now=1000.0)
    assert cache.get("逾期天数怎么计算", now=1005.0) is not None
    assert cache.get("逾期天数怎么计算", now=1020.0) is None


def test_stats():
    cache = SemanticCache()
    cache.put("q1", "a1", reviewed=True)
    cache.get("q1")
    assert cache.stats() == {"entries": 1, "reviewed": 1, "hits": 1}
