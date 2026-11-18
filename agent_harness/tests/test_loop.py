"""Agent Loop：四类处置、步数熔断、错误回灌、模型热切换。"""
from __future__ import annotations

from pathlib import Path

from harness.audit import AuditLog
from harness.control_point import ControlPoint
from harness.loop import AgentLoop
from harness.models import ModelAdapter, ModelRegistry, ToolCall
from harness.registry import ToolRegistry, ToolSpec
from harness.rules import RuleSet

CONFIG = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


class StubModel(ModelAdapter):
    """按给定队列逐轮返回工具调用，队列耗尽后返回空表示作答。"""

    def __init__(self, name: str, plan_queue: list[list[ToolCall]] | None = None) -> None:
        self.name = name
        self.plan_queue = list(plan_queue or [])
        self.plan_calls = 0

    def plan(self, question: str, observations: list[dict]) -> list[ToolCall]:
        self.plan_calls += 1
        return self.plan_queue.pop(0) if self.plan_queue else []

    def answer(self, question: str, observations: list[dict]) -> str:
        return f"{self.name}: 完成 {len(observations)} 个观测"


class RepeatModel(ModelAdapter):
    """每轮都返回同一调用，用于触发步数熔断。"""

    name = "repeat"

    def __init__(self, call: ToolCall) -> None:
        self.call = call

    def plan(self, question: str, observations: list[dict]) -> list[ToolCall]:
        return [self.call]

    def answer(self, question: str, observations: list[dict]) -> str:
        return "熔断后作答"


def build_registry(counters: dict[str, int]) -> ToolRegistry:
    def query_report_data(report: str, org: str, stat_date: str) -> dict:
        counters["query"] = counters.get("query", 0) + 1
        return {"rows": [{"org": org, "report": report}]}

    def submit_report(report: str, stat_date: str) -> dict:
        counters["submit"] = counters.get("submit", 0) + 1
        return {"submitted": True}

    def delete_batch(batch: str) -> dict:
        counters["delete"] = counters.get("delete", 0) + 1
        return {"deleted": batch}

    def explode(**kwargs) -> dict:
        counters["explode"] = counters.get("explode", 0) + 1
        raise RuntimeError("上游数据源连接失败")

    def ok_tool(**kwargs) -> dict:
        counters["ok"] = counters.get("ok", 0) + 1
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(ToolSpec("query_report_data", query_report_data, readonly=True, risk="low"))
    registry.register(ToolSpec("submit_report", submit_report, readonly=False, risk="high"))
    registry.register(ToolSpec("delete_batch", delete_batch, readonly=False, risk="high"))
    registry.register(ToolSpec("explode", explode, readonly=True, risk="low"))
    registry.register(ToolSpec("ok_tool", ok_tool, readonly=True, risk="low"))
    return registry


def make_loop(models: ModelRegistry, counters: dict[str, int], **kwargs) -> AgentLoop:
    return AgentLoop(
        registry=build_registry(counters),
        models=models,
        control=ControlPoint(RuleSet.load(CONFIG)),
        audit=AuditLog(),
        **kwargs,
    )


def test_auto_runs_same_org_query():
    counters: dict[str, int] = {}
    model = StubModel(
        "stub",
        [[ToolCall("query_report_data", {"report": "G01", "org": "SH01", "stat_date": "2026-03-31"})]],
    )
    loop = make_loop(ModelRegistry().register(model, activate=True), counters)

    result = loop.run("查余额", session_id="S1", user_id="u1", role="analyst", allowed_orgs=["SH01", "SH02"])

    assert counters["query"] == 1
    assert len(result.observations) == 1
    obs = result.observations[0]
    assert obs["status"] == "ok" and obs["effect"] == "auto"


def test_observe_runs_cross_org_query_and_marks_observed():
    counters: dict[str, int] = {}
    model = StubModel(
        "stub",
        [[ToolCall("query_report_data", {"report": "G01", "org": "SZ01", "stat_date": "2026-03-31"})]],
    )
    loop = make_loop(ModelRegistry().register(model, activate=True), counters)

    result = loop.run("查深圳", session_id="S2", user_id="u2", role="analyst", allowed_orgs=["SH01", "SH02"])

    assert counters["query"] == 1
    obs = result.observations[0]
    assert obs["status"] == "ok" and obs["effect"] == "observe"
    assert obs["observed"] is True


def test_escalate_does_not_execute_write_tool():
    counters: dict[str, int] = {}
    model = StubModel(
        "stub",
        [[ToolCall("submit_report", {"report": "G01", "stat_date": "2026-03-31"})]],
    )
    loop = make_loop(ModelRegistry().register(model, activate=True), counters)

    result = loop.run("提交报送", session_id="S3", user_id="u3", role="analyst", allowed_orgs=["SH01"])

    assert counters.get("submit", 0) == 0
    obs = result.observations[0]
    assert obs["status"] == "pending_human" and obs["effect"] == "escalate"


def test_block_does_not_execute_delete_tool():
    counters: dict[str, int] = {}
    model = StubModel("stub", [[ToolCall("delete_batch", {"batch": "202603"})]])
    loop = make_loop(ModelRegistry().register(model, activate=True), counters)

    result = loop.run("删除批次", session_id="S4", user_id="u4", role="analyst", allowed_orgs=["SH01"])

    assert counters.get("delete", 0) == 0
    obs = result.observations[0]
    assert obs["status"] == "blocked" and obs["effect"] == "block"


def test_max_steps_breaker():
    counters: dict[str, int] = {}
    call = ToolCall("query_report_data", {"report": "G01", "org": "SH01", "stat_date": "2026-03-31"})
    loop = make_loop(ModelRegistry().register(RepeatModel(call), activate=True), counters, max_steps=3)

    result = loop.run("一直查", session_id="S5", user_id="u5", role="analyst", allowed_orgs=["SH01"])

    assert counters["query"] == 3
    assert result.stopped_reason == "max_steps"
    assert result.steps == 3
    assert len(result.observations) == 3
    assert all(o["status"] == "ok" for o in result.observations)


def test_tool_error_is_fed_back_and_loop_answers():
    counters: dict[str, int] = {}
    model = StubModel(
        "stub",
        [[ToolCall("explode"), ToolCall("ok_tool")]],
    )
    loop = make_loop(ModelRegistry().register(model, activate=True), counters)

    result = loop.run("先查后答", session_id="S6", user_id="u6", role="analyst", allowed_orgs=["SH01"])

    error_obs = next(o for o in result.observations if o["tool"] == "explode")
    assert error_obs["status"] == "error"
    assert "上游数据源连接失败" in error_obs["detail"]
    # 同批其他工具成功，循环继续到下一轮，最终仍返回答案
    assert model.plan_calls == 2
    assert result.answer
    assert result.stopped_reason == "model_done"


def test_model_hot_switch_is_reflected_in_audit():
    counters: dict[str, int] = {}
    call = ToolCall("query_report_data", {"report": "G01", "org": "SH01", "stat_date": "2026-03-31"})
    models = ModelRegistry().register(StubModel("a", [[call]]), activate=True).register(
        StubModel("b", [[call]])
    )
    models.activate("b")
    loop = make_loop(models, counters)

    loop.run("热切换", session_id="S7", user_id="u7", role="analyst", allowed_orgs=["SH01"])

    assert loop.audit.records
    assert all(record.model == "b" for record in loop.audit.records)
    assert all(item["model_version"] == "b" for item in loop.audit.by_session("S7"))
