"""离线演示：研究线七节点 + 缓存命中。"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .cache import SemanticCache
from .memory import LayeredMemory
from .nodes import ReportNodes
from .retrieval import DualRetriever


@dataclass
class _Chunk:
    chunk_id: str
    doc_no: str
    article: str
    doc_title: str
    text: str
    version: str = "v1.0"
    effective_date: str = "2026-03-01"


@dataclass
class _Scored:
    chunk: _Chunk
    score: float


class _MiniRetriever:
    """没有安装 domain_llm 依赖时的最小检索实现。"""

    def __init__(self, chunks: list[_Chunk]) -> None:
        self.chunks = chunks

    def search(self, query: str, as_of: str | None = None):
        import re

        chars = set(re.findall(r"[\u4e00-\u9fff]", query))
        scored = []
        for chunk in self.chunks:
            overlap = len(chars & set(re.findall(r"[\u4e00-\u9fff]", chunk.text)))
            if overlap:
                scored.append(_Scored(chunk, overlap / max(1, len(chars))))
        return sorted(scored, key=lambda s: s.score, reverse=True)[:5]


REG_FALLBACK = [
    _Chunk("金监发〔2026〕1号#第四条", "金监发〔2026〕1号", "第四条", "商业银行金融资产风险分类办法（示例）",
           "逾期天数为金融资产本金或利息到期日次日起至统计日止的自然日天数，包含法定节假日。"),
    _Chunk("金监发〔2026〕1号#第五条", "金监发〔2026〕1号", "第五条", "商业银行金融资产风险分类办法（示例）",
           "逾期账龄按逾期时长划分为五个区间：90 天以内、90 天至 180 天、180 天至 360 天、360 天至 720 天、720 天以上。"),
    _Chunk("金监发〔2026〕1号#第三条", "金监发〔2026〕1号", "第三条", "商业银行金融资产风险分类办法（示例）",
           "金融资产按照风险程度分为正常、关注、次级、可疑、损失五类，后三类合称不良资产。"),
]
BANK_FALLBACK = [
    _Chunk("行内口径〔2026〕07号#第二条", "行内口径〔2026〕07号", "第二条", "行内信贷统计口径说明（示例）",
           "逾期账龄按月末最后一日余额划分区间，与监管按每日余额划分的统计方式不同，月度报表以本口径为准。"),
    _Chunk("行内口径〔2026〕07号#第一条", "行内口径〔2026〕07号", "第一条", "行内信贷统计口径说明（示例）",
           "逾期天数采用自然日口径，起算日与监管口径保持一致，即到期日次日。"),
]


def build_dual() -> DualRetriever:
    try:
        from dl.loader import load_chunks
        from dl.retriever import HybridRetriever

        docs = Path(__file__).resolve().parents[2] / "domain_llm" / "data" / "docs"
        chunks = load_chunks(docs)
        reg = HybridRetriever([c for c in chunks if c.doc_no.startswith("金监发")], offline=True)
        bank = HybridRetriever([c for c in chunks if c.doc_no.startswith("行内")], offline=True)
        print("使用 domain_llm 的真实知识库与混合检索")
    except Exception:  # noqa: BLE001 - 未设置 PYTHONPATH 时用内置语料
        print("未加载 domain_llm，使用内置演示语料")
        reg, bank = _MiniRetriever(REG_FALLBACK), _MiniRetriever(BANK_FALLBACK)
    return DualRetriever(reg, bank)


def main() -> None:
    dual = build_dual()
    cache = SemanticCache()
    nodes = ReportNodes(dual, cache=cache, memory=LayeredMemory())

    question = "《金融资产风险分类办法》对我行逾期账龄统计有什么影响？"
    state = {"question": question, "user_id": "u-001", "as_of": "2026-06-30", "trace": []}
    state.update(nodes.route(state))
    print(f"路由：{state['route']}")

    if state["route"] == "research":
        result = nodes.run_research(state)
    else:
        result = {**state, **nodes.collaborative(state)}

    print("\n" + result.get("draft", result.get("answer", "")))
    print("\n未验证引用：", result.get("unverified", []))
    print("节点轨迹：", [t["node"] for t in result.get("trace", [])])

    # 人工审核后入缓存，第二次提问命中 L1
    cache.put(question, result.get("draft", ""), result.get("citations", []), reviewed=True)
    hit = cache.get(question)
    print(f"\n二次提问：命中 {hit.layer}，首字可直接返回（生产环境约 80ms）")

    # 语义近似命中 L2
    paraphrase = question.replace("？", " 呢？")
    hit2 = cache.get(paraphrase)
    print(f"近似问法：{'命中 ' + hit2.layer if hit2 else '未命中'}")


if __name__ == "__main__":
    sys.exit(main())
