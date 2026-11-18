"""节点：路由、成稿与引用校验。"""
from ra.cache import SemanticCache
from ra.nodes import ReportNodes

EV = {
    "chunk_id": "金监发〔2026〕1号#第五条",
    "doc_no": "金监发〔2026〕1号",
    "article": "第五条",
    "doc_title": "金融资产风险分类办法（示例）",
    "text": "逾期账龄按逾期时长划分为五个区间。",
    "source": "regulation",
    "score": 0.9,
    "version": "v1.0",
    "effective_date": "2026-03-01",
}


class StubDual:
    def search_one(self, which, question, as_of):
        return [EV] if which == "regulation" else []


def _nodes(cache=None) -> ReportNodes:
    return ReportNodes(StubDual(), cache=cache or SemanticCache())


def test_route_collab_for_faq():
    state = {"question": "逾期天数怎么计算", "trace": []}
    assert _nodes().route(state)["route"] == "collab"


def test_route_research_for_policy_question():
    state = {"question": "新的风险分类办法对我行不良率统计有什么影响", "trace": []}
    assert _nodes().route(state)["route"] == "research"


def test_route_hits_reviewed_cache_only():
    cache = SemanticCache()
    nodes = _nodes(cache)
    assert nodes.route({"question": "逾期天数怎么计算", "trace": []})["route"] == "collab"

    cache.put("逾期天数怎么计算", "标准答案", ["金监发〔2026〕1号#第四条"], reviewed=True)
    result = nodes.route({"question": "逾期天数怎么计算", "trace": []})
    assert result["route"] == "cache"
    assert result["answer"] == "标准答案"


def test_write_binds_citation_and_verify_passes():
    nodes = _nodes()
    state = {"question": "逾期账龄口径", "evidences": [EV], "conflicts": [], "trace": []}
    draft = nodes.write(state)
    assert "[金监发〔2026〕1号 第五条]" in draft["draft"]

    verified = nodes.verify({**state, **draft})
    assert verified["unverified"] == []


def test_verify_flags_fabricated_citation():
    nodes = _nodes()
    state = {"evidences": [EV], "trace": []}
    draft = {"draft": "结论 [金监发〔2026〕1号 第九条]", "citations": []}
    assert nodes.verify({**state, **draft})["unverified"] == ["金监发〔2026〕1号#第九条"]


def test_run_research_bounded_rounds():
    nodes = _nodes()
    state = {"question": "新规对我行有什么影响", "trace": []}
    result = nodes.run_research(state)
    assert 1 <= result["rounds"] <= 3
    assert result["draft"].startswith("# ")
    assert "writer" in [t["node"] for t in result["trace"]]
