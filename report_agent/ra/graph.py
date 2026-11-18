"""LangGraph 状态图：条件边实现选线与反思循环，Checkpointer 支持断点恢复。

langgraph 未安装时本模块不可导入，其余模块不依赖它。
"""
from __future__ import annotations

from .nodes import ReportNodes
from .state import ReportState


def build_graph(nodes: ReportNodes, checkpointer=None):
    from langgraph.graph import END, StateGraph

    graph = StateGraph(ReportState)
    graph.add_node("route", nodes.route)
    graph.add_node("collab", nodes.collaborative)
    graph.add_node("plan", nodes.plan)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("judge", nodes.judge)
    graph.add_node("analyst", nodes.analyze)
    graph.add_node("reflect", nodes.reflect)
    graph.add_node("writer", nodes.write)
    graph.add_node("verify", nodes.verify)

    graph.set_entry_point("route")
    graph.add_conditional_edges(
        "route",
        lambda state: state["route"],
        {"cache": END, "collab": "collab", "research": "plan"},
    )
    graph.add_edge("collab", END)
    graph.add_edge("plan", "retrieve")
    graph.add_edge("retrieve", "judge")
    graph.add_edge("judge", "analyst")
    graph.add_edge("analyst", "reflect")
    graph.add_conditional_edges(
        "reflect",
        lambda state: "retrieve" if state.get("need_more") else "writer",
        {"retrieve": "retrieve", "writer": "writer"},
    )
    graph.add_edge("writer", "verify")
    graph.add_edge("verify", END)

    if checkpointer is None:
        try:
            from langgraph.checkpoint.memory import MemorySaver

            checkpointer = MemorySaver()
        except Exception:  # noqa: BLE001 - 旧版本没有 MemorySaver 时退化为无检查点
            checkpointer = None
    return graph.compile(checkpointer=checkpointer) if checkpointer else graph.compile()
