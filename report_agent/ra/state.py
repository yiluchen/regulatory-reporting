"""LangGraph 全局状态。节点只读写 State，不互相传参。"""
from __future__ import annotations

from typing import TypedDict


class Evidence(TypedDict, total=False):
    chunk_id: str
    doc_no: str
    article: str
    doc_title: str
    text: str
    source: str          # regulation / bank
    score: float
    version: str
    effective_date: str


class ReportState(TypedDict, total=False):
    question: str
    user_id: str
    as_of: str
    route: str                    # cache / collab / research
    cache_layer: str | None       # L1 / L2 / None
    answer: str
    memory_context: str
    sub_questions: list[str]
    evidences: list[Evidence]
    conflicts: list[dict]
    analysis: str
    rounds: int
    need_more: bool
    draft: str
    citations: list[str]
    unverified: list[str]
    trace: list[dict]
