"""证据裁判：过滤、去重、冲突检测。"""
from ra.evidence import evidence_ids, judge


def _ev(chunk_id: str, source: str, text: str, score: float = 0.8, effective: str = "2026-03-01") -> dict:
    doc_no, article = chunk_id.split("#")
    return {
        "chunk_id": chunk_id,
        "doc_no": doc_no,
        "article": article,
        "doc_title": "示例文件",
        "text": text,
        "source": source,
        "score": score,
        "version": "v1.0",
        "effective_date": effective,
    }


REG = _ev(
    "金监发〔2026〕1号#第五条", "regulation",
    "逾期账龄按逾期时长划分为五个区间：90 天以内、90 天至 180 天、180 天至 360 天、360 天至 720 天、720 天以上。",
)
BANK = _ev(
    "行内口径〔2026〕07号#第二条", "bank",
    "逾期账龄按月末最后一日余额划分区间，与监管按每日余额划分的统计方式不同。",
)


def test_detects_regulation_bank_conflict():
    result = judge([REG, BANK])
    assert len(result.conflicts) == 1
    assert result.conflicts[0]["topic"] == ["逾期账龄"]
    assert {result.conflicts[0]["left"], result.conflicts[0]["right"]} == {
        "金监发〔2026〕1号#第五条", "行内口径〔2026〕07号#第二条"
    }


def test_same_source_no_conflict():
    other = _ev("金监发〔2026〕1号#第四条", "regulation", "逾期天数按自然日计算，共 5 天。")
    assert judge([REG, other]).conflicts == []


def test_dedup_keeps_highest_score():
    result = judge([REG, {**REG, "score": 0.99}])
    assert len(result.kept) == 1
    assert result.kept[0]["score"] == 0.99
    assert result.dropped == 1


def test_future_documents_filtered():
    future = {**REG, "effective_date": "2026-12-01"}
    result = judge([future], as_of="2026-06-30")
    assert result.kept == []
    assert result.dropped == 1


def test_evidence_ids():
    assert evidence_ids([REG, BANK]) == {"金监发〔2026〕1号#第五条", "行内口径〔2026〕07号#第二条"}
