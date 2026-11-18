"""四道闸门与置信度路由。"""
from dl.guardrails import (
    check_citations,
    check_schema,
    check_whitelist,
    confidence_score,
    route_by_confidence,
    run_guardrails,
)

EVIDENCE = {"金监发〔2026〕1号#第四条", "金监发〔2026〕1号#第五条"}
CATALOG = {"G01 资产负债项目统计表": ["贷款余额", "不良贷款余额"]}


def test_citation_required():
    assert not check_citations("逾期天数按自然日计算。", EVIDENCE).ok
    ok = check_citations("逾期天数按自然日计算 [金监发〔2026〕1号 第四条]。", EVIDENCE)
    assert ok.ok


def test_unknown_citation_rejected():
    result = check_citations("按自然日计算 [金监发〔2026〕1号 第九条]。", EVIDENCE)
    assert not result.ok
    assert result.code == "unknown_citation"


def test_whitelist():
    assert check_whitelist("G01 资产负债项目统计表", ["贷款余额"], CATALOG).ok
    assert not check_whitelist("G99 不存在的表", ["贷款余额"], CATALOG).ok
    assert not check_whitelist("G01 资产负债项目统计表", ["逾期账龄"], CATALOG).ok


def test_schema():
    schema = {"required": ["answer", "citations"], "properties": {"answer": "str", "citations": "list"}}
    assert check_schema({"answer": "x", "citations": []}, schema).ok
    assert not check_schema({"answer": "x"}, schema).ok
    assert not check_schema({"answer": 1, "citations": []}, schema).ok


def test_confidence_routing():
    assert confidence_score(1, 1, 1) == 1.0
    assert route_by_confidence(0.9) == "draft"
    assert route_by_confidence(0.7) == "draft_review"
    assert route_by_confidence(0.5) == "human"


def test_empty_retrieval_refuses():
    report = run_guardrails(
        answer="随便答", evidence_ids=set(), report_name="G01 资产负债项目统计表",
        field_names=["贷款余额"], catalog=CATALOG, payload={}, schema={},
        dense=0, rerank=0, self_score=0,
    )
    assert not report.ok
    assert report.route == "human"
    assert report.failed[0].code == "empty_retrieval"


def test_full_pipeline_blocks_low_confidence():
    report = run_guardrails(
        answer="逾期天数按自然日计算 [金监发〔2026〕1号 第四条]。",
        evidence_ids=EVIDENCE,
        report_name="G01 资产负债项目统计表",
        field_names=["贷款余额"],
        catalog=CATALOG,
        payload={"answer": "x", "citations": []},
        schema={"required": ["answer", "citations"]},
        dense=0.4, rerank=0.3, self_score=0.4,
    )
    assert report.ok
    assert report.route == "human"
