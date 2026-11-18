"""FastMCP 工具服务：工具与 Agent 解耦，调用方必须带会话身份。

启动：python -m ra.mcp_server（需 pip install fastmcp）
"""
from __future__ import annotations


def build_server(retriever):
    from fastmcp import FastMCP

    mcp = FastMCP("report-tools")

    @mcp.tool
    def search_regulation(question: str, as_of: str = "") -> list[dict]:
        """检索监管发文条款，返回带文号与版本的条款列表。"""
        return [
            {
                "chunk_id": s.chunk.chunk_id,
                "doc_no": s.chunk.doc_no,
                "article": s.chunk.article,
                "text": s.chunk.text,
                "version": s.chunk.version,
            }
            for s in retriever.search(question, as_of=as_of or None)
        ]

    @mcp.tool
    def query_report_data(session_id: str, report: str, org: str, stat_date: str) -> dict:
        """只读查询报送数据。session_id 用于按机构与岗位过滤，越权直接拒绝。"""
        if not session_id:
            raise PermissionError("缺少会话身份")
        # 生产实现：按 session 解析机构/角色，再注入 SQL 过滤条件；此处返回结构示例
        return {
            "report": report,
            "org": org,
            "stat_date": stat_date,
            "rows": [],
            "readonly": True,
        }

    @mcp.tool
    def generate_material(topic: str, evidences: list[str]) -> dict:
        """生成报送材料草稿，只写草稿区，需专家终审。"""
        return {"topic": topic, "evidences": evidences, "status": "DRAFT", "review_required": True}

    return mcp


def main() -> None:
    from pathlib import Path

    from dl.loader import load_chunks
    from dl.retriever import HybridRetriever

    docs = Path(__file__).resolve().parents[2] / "domain_llm" / "data" / "docs"
    retriever = HybridRetriever(load_chunks(docs), offline=True)
    build_server(retriever).run()


if __name__ == "__main__":
    main()
