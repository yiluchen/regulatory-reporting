"""研究线七个节点 + 协同线。节点只返回 State 增量。

规划与执行解耦：Planner 只产出子问题，执行阶段不再重新规划。
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from .cache import SemanticCache
from .evidence import judge, evidence_ids
from .memory import LayeredMemory
from .retrieval import DualRetriever
from .state import ReportState

RESEARCH_HINTS = ("政策", "研究", "影响", "解读", "分析", "对比", "通知", "办法", "新规")
CITATION_RE = re.compile(r"\[([^\[\]]+?)\s+(第[一二三四五六七八九十百零〇\d]+条)\]")
MAX_ROUNDS = 3


def _trace(state: ReportState, node: str, **extra) -> list[dict]:
    return list(state.get("trace", [])) + [{"node": node, "ts": round(time.time(), 3), **extra}]


class ReportNodes:
    def __init__(
        self,
        dual: DualRetriever,
        cache: SemanticCache | None = None,
        memory: LayeredMemory | None = None,
        llm=None,
    ) -> None:
        self.dual = dual
        self.cache = cache or SemanticCache()
        self.memory = memory or LayeredMemory()
        self.llm = llm

    # ---------------------------------------------------------------- 入口
    def route(self, state: ReportState) -> dict:
        hit = self.cache.get(state["question"])
        if hit:
            return {
                "route": "cache",
                "cache_layer": hit.layer,
                "answer": hit.answer,
                "citations": hit.citations,
                "trace": _trace(state, "route", cache=hit.layer),
            }
        question = state["question"]
        route = "research" if any(h in question for h in RESEARCH_HINTS) else "collab"
        return {"route": route, "trace": _trace(state, "route", route=route)}

    # ------------------------------------------------------------ 协同线
    def collaborative(self, state: ReportState) -> dict:
        """记忆注入 → 编排器 → 专家 Agent；这里用确定性规则演示路由。"""
        context = self.memory.context(state.get("user_id", "anonymous"))
        evidences = state.get("evidences") or []
        expert = self._pick_expert(state["question"])
        answer = self._expert_answer(expert, evidences)
        self.memory.add_turn(state.get("user_id", "anonymous"), state["question"], answer)
        return {
            "answer": answer,
            "memory_context": context,
            "trace": _trace(state, "collaborative", expert=expert),
        }

    @staticmethod
    def _pick_expert(question: str) -> str:
        if any(w in question for w in ("校验", "勾稽", "平衡")):
            return "compliance"
        if any(w in question for w in ("数", "余额", "报表", "统计")):
            return "data_query"
        if any(w in question for w in ("任务", "编排", "调度")):
            return "task"
        return "rule_consult"

    @staticmethod
    def _expert_answer(expert: str, evidences: list[dict]) -> str:
        if not evidences:
            return f"[{expert}] 未检索到依据，请补充问题或转人工。"
        top = evidences[0]
        return (
            f"[{expert}] 依据 {top['chunk_id']}：{top['text'].splitlines()[0]}"
            f" 详见 [{top['doc_no']} {top['article']}]。"
        )

    # ------------------------------------------------------------ 研究线
    def plan(self, state: ReportState) -> dict:
        question = state["question"]
        sub_questions = [
            f"{question}：监管文件是如何规定的",
            f"{question}：行内口径与监管是否一致",
            f"{question}：涉及哪些报送报表与字段",
        ]
        return {
            "sub_questions": sub_questions,
            "rounds": 0,
            "need_more": True,
            "trace": _trace(state, "plan", sub_questions=len(sub_questions)),
        }

    def retrieve(self, state: ReportState) -> dict:
        queries = state.get("sub_questions") or [state["question"]]
        as_of = state.get("as_of")

        def run(query: str) -> list[dict]:
            with ThreadPoolExecutor(max_workers=2) as pool:
                reg = pool.submit(self.dual.search_one, "regulation", query, as_of)
                bank = pool.submit(self.dual.search_one, "bank", query, as_of)
                return reg.result() + bank.result()

        merged: dict[str, dict] = {e["chunk_id"]: e for e in state.get("evidences", [])}
        for query in queries[-2:]:          # 首轮全量、反思轮只补最后一问
            for ev in run(query):
                old = merged.get(ev["chunk_id"])
                if old is None or ev["score"] > old["score"]:
                    merged[ev["chunk_id"]] = ev
        return {
            "evidences": list(merged.values()),
            "trace": _trace(state, "retrieve", evidences=len(merged)),
        }

    def judge(self, state: ReportState) -> dict:
        result = judge(state.get("evidences", []), as_of=state.get("as_of"))
        return {
            "evidences": result.kept,
            "conflicts": result.conflicts,
            "trace": _trace(state, "judge", kept=len(result.kept), conflicts=len(result.conflicts)),
        }

    def analyze(self, state: ReportState) -> dict:
        kept = state.get("evidences", [])
        conflicts = state.get("conflicts", [])
        reg = [e for e in kept if e["source"] == "regulation"]
        bank = [e for e in kept if e["source"] == "bank"]
        analysis = (
            f"监管证据 {len(reg)} 条、行内证据 {len(bank)} 条；"
            f"口径冲突 {len(conflicts)} 组；"
            f"覆盖条款 {len({e['chunk_id'] for e in kept})} 个。"
        )
        return {"analysis": analysis, "trace": _trace(state, "analyst")}

    def reflect(self, state: ReportState) -> dict:
        rounds = int(state.get("rounds", 0)) + 1
        kept = state.get("evidences", [])
        need_more = rounds < MAX_ROUNDS and (len(kept) < 3 or bool(state.get("conflicts")))
        return {
            "rounds": rounds,
            "need_more": need_more,
            "trace": _trace(state, "reflect", round=rounds, need_more=need_more),
        }

    def write(self, state: ReportState) -> dict:
        kept = state.get("evidences", [])
        conflicts = state.get("conflicts", [])
        lines = [f"# {state['question']}", "", "## 结论", ""]
        if not kept:
            lines.append("未检索到足够依据，无法形成结论，已转人工。")
        else:
            for ev in kept[:3]:
                first = ev["text"].splitlines()[0]
                lines.append(f"- {first} [{ev['doc_no']} {ev['article']}]")
        if conflicts:
            lines += ["", "## 口径冲突（需专家确认）", ""]
            for c in conflicts:
                lines.append(f"- {c['left']} 与 {c['right']} 在 {','.join(c['topic'])} 上不一致")
        lines += ["", "## 证据清单", ""]
        for ev in kept:
            lines.append(f"- 《{ev['doc_title']}》（{ev['doc_no']}）{ev['article']}，版本 {ev['version']}")
        draft = "\n".join(lines)
        return {"draft": draft, "citations": [e["chunk_id"] for e in kept], "trace": _trace(state, "writer")}

    def verify(self, state: ReportState) -> dict:
        draft = state.get("draft", "")
        allowed = evidence_ids(state.get("evidences", []))
        refs = {f"{doc}#{art}" for doc, art in CITATION_RE.findall(draft)}
        unverified = sorted(refs - allowed)
        return {
            "unverified": unverified,
            "trace": _trace(state, "verify", refs=len(refs), unverified=len(unverified)),
        }

    # ------------------------------------------------------- 与图框架无关的编排
    def run_research(self, state: ReportState) -> ReportState:
        """顺序执行七节点，供 demo / API 复用；LangGraph 版见 graph.py。"""
        state = {**state, **self.plan(state)}
        while True:
            state = {**state, **self.retrieve(state)}
            state = {**state, **self.judge(state)}
            state = {**state, **self.analyze(state)}
            state = {**state, **self.reflect(state)}
            if not state.get("need_more"):
                break
            state = {**state, "sub_questions": [state["question"] + " 补充说明"]}
        state = {**state, **self.write(state)}
        state = {**state, **self.verify(state)}
        return state
