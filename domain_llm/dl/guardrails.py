"""四道防幻觉闸门：强制溯源、白名单、JSON 结构、置信度路由。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CITATION_RE = re.compile(r"\[([^\[\]]+?)\s+(第[一二三四五六七八九十百零〇\d]+条)\]")


@dataclass
class CheckResult:
    ok: bool
    code: str
    message: str = ""


@dataclass
class GuardrailReport:
    results: list[CheckResult] = field(default_factory=list)
    confidence: float = 0.0
    route: str = "human"        # draft / draft_review / human

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if not r.ok]

    def summary(self) -> str:
        bad = "，".join(f"{r.code}:{r.message}" for r in self.failed) or "全部通过"
        return f"置信度 {self.confidence:.2f}，路由 {self.route}，闸门结果 {bad}"


def check_citations(answer: str, evidence_ids: set[str]) -> CheckResult:
    """每句结论必须带 [文号 第X条]，且必须能在检索证据里找到。"""
    refs = CITATION_RE.findall(answer)
    if not refs:
        return CheckResult(False, "no_citation", "回答未附任何条款出处")
    unknown = [f"{doc} {art}" for doc, art in refs if f"{doc}#{art}" not in evidence_ids]
    if unknown:
        return CheckResult(False, "unknown_citation", f"引用了未检索到的条款: {unknown[:3]}")
    return CheckResult(True, "citation_ok", f"引用 {len(refs)} 处均可回溯")


def check_whitelist(
    report_name: str, field_names: list[str], catalog: dict[str, list[str]]
) -> CheckResult:
    """报表名、字段名必须在台账里精确匹配。"""
    if report_name not in catalog:
        return CheckResult(False, "unknown_report", f"报表 {report_name} 不在报送目录")
    allowed = set(catalog[report_name])
    unknown = [f for f in field_names if f not in allowed]
    if unknown:
        return CheckResult(False, "unknown_field", f"字段不在报表清单: {unknown[:3]}")
    return CheckResult(True, "whitelist_ok", f"{report_name} 的 {len(field_names)} 个字段均命中")


def check_schema(payload: dict, schema: dict) -> CheckResult:
    """极简 JSON 结构校验：required + type。"""
    for key in schema.get("required", []):
        if key not in payload:
            return CheckResult(False, "schema_missing", f"缺少字段 {key}")
    types = {"str": str, "int": int, "float": (int, float), "list": list, "dict": dict}
    for key, kind in schema.get("properties", {}).items():
        if key in payload and not isinstance(payload[key], types[kind]):
            return CheckResult(False, "schema_type", f"{key} 类型应为 {kind}")
    return CheckResult(True, "schema_ok", "结构符合约定")


def confidence_score(dense: float, rerank: float, self_score: float) -> float:
    """检索相似度、精排分、模型自评加权；各分量都归一到 0-1。"""
    value = 0.3 * max(0.0, min(1.0, dense)) + 0.45 * max(0.0, min(1.0, rerank)) + 0.25 * max(0.0, min(1.0, self_score))
    return round(value, 4)


def route_by_confidence(confidence: float, high: float = 0.85, low: float = 0.60) -> str:
    if confidence >= high:
        return "draft"          # 高置信，直接出草稿
    if confidence < low:
        return "human"          # 不给草稿，转人工
    return "draft_review"       # 出草稿但强制人工复核


def run_guardrails(
    *,
    answer: str,
    evidence_ids: set[str],
    report_name: str,
    field_names: list[str],
    catalog: dict[str, list[str]],
    payload: dict,
    schema: dict,
    dense: float,
    rerank: float,
    self_score: float,
) -> GuardrailReport:
    # 检索为空时直接拒答，不调模型
    if not evidence_ids:
        return GuardrailReport(
            results=[CheckResult(False, "empty_retrieval", "未检索到任何依据，拒答")],
            confidence=0.0,
            route="human",
        )
    report = GuardrailReport()
    report.results.append(check_citations(answer, evidence_ids))
    report.results.append(check_whitelist(report_name, field_names, catalog))
    report.results.append(check_schema(payload, schema))
    report.confidence = confidence_score(dense, rerank, self_score)
    report.route = route_by_confidence(report.confidence) if report.ok else "human"
    return report
