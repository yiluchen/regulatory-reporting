"""控制点：四类处置与默认策略。"""
from harness.control_point import ControlPoint
from harness.registry import ToolRegistry, ToolSpec
from harness.rules import Rule, RuleSet


def _registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolSpec("query_report_data", lambda **k: {}, readonly=True, risk="low"))
    reg.register(ToolSpec("search_regulation", lambda **k: {}, readonly=True, risk="low", category="kb"))
    reg.register(ToolSpec("submit_report", lambda **k: {}, readonly=False, risk="high"))
    reg.register(ToolSpec("delete_batch", lambda **k: {}, readonly=False, risk="high"))
    reg.register(ToolSpec("export_material", lambda **k: {}, readonly=True, risk="medium"))
    return reg


def _control() -> ControlPoint:
    rules = RuleSet(
        [
            Rule("R-READ", "query_report_data", "auto", conditions={"cross_org": False}),
            Rule("R-CROSS", "query_report_data", "observe", conditions={"cross_org": True}),
            Rule("R-SUBMIT", "submit_report", "escalate"),
            Rule("R-DELETE", "delete_*", "block"),
            Rule("R-EXPORT", "export_*", "observe"),
        ]
    )
    return ControlPoint(rules)


def test_auto_for_readonly_same_org():
    cp = _control()
    decision = cp.review(_registry().get("query_report_data"), {}, {"cross_org": False})
    assert decision.effect == "auto" and decision.allowed


def test_observe_for_cross_org():
    cp = _control()
    decision = cp.review(_registry().get("query_report_data"), {}, {"cross_org": True})
    assert decision.effect == "observe" and decision.allowed


def test_escalate_for_write():
    cp = _control()
    decision = cp.review(_registry().get("submit_report"), {}, {"cross_org": False})
    assert decision.effect == "escalate" and not decision.allowed


def test_block_for_dangerous_tool():
    cp = _control()
    decision = cp.review(_registry().get("delete_batch"), {}, {"cross_org": False})
    assert decision.effect == "block" and not decision.allowed


def test_most_severe_rule_wins():
    rules = RuleSet(
        [
            Rule("R1", "export_*", "auto"),
            Rule("R2", "export_*", "block"),
            Rule("R3", "export_*", "observe"),
        ]
    )
    assert ControlPoint(rules).review(_registry().get("export_material"), {}, {}).effect == "block"


def test_default_policy_without_rule():
    cp = ControlPoint(RuleSet([]))
    assert cp.review(_registry().get("search_regulation"), {}, {}).effect == "auto"
    assert cp.review(_registry().get("submit_report"), {}, {}).effect == "escalate"
