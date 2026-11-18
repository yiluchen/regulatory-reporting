"""LangGraph 装配冒烟：装了 langgraph 才跑。"""
import pytest

pytest.importorskip("langgraph")

from ra.demo import build_dual  # noqa: E402
from ra.graph import build_graph  # noqa: E402
from ra.nodes import ReportNodes  # noqa: E402


def test_research_flow_runs_through_graph():
    graph = build_graph(ReportNodes(build_dual()))
    out = graph.invoke(
        {
            "question": "新的风险分类办法对我行不良率统计有什么影响",
            "user_id": "smoke",
            "trace": [],
        },
        config={"configurable": {"thread_id": "smoke-graph"}},
    )
    assert out["route"] == "research"
    assert out["draft"]
    assert "## 证据清单" in out["draft"]
    assert out["unverified"] == []


def test_collab_route_short_circuits():
    graph = build_graph(ReportNodes(build_dual()))
    out = graph.invoke(
        {"question": "逾期天数怎么计算", "user_id": "smoke", "trace": []},
        config={"configurable": {"thread_id": "smoke-graph-2"}},
    )
    assert out["route"] in ("collab", "cache")
    assert out.get("answer")
