"""控制点：每次工具调用都先取证、再按规则给出四类处置。"""
from __future__ import annotations

from dataclasses import dataclass

from .registry import ToolSpec
from .rules import RuleSet


@dataclass
class Decision:
    effect: str          # auto / observe / escalate / block
    rule_id: str
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.effect in ("auto", "observe")


class ControlPoint:
    """处置由规则表决定，模型无权参与判断。"""

    def __init__(self, rules: RuleSet) -> None:
        self.rules = rules

    def review(self, spec: ToolSpec, args: dict, ctx: dict) -> Decision:
        merged = {
            "readonly": spec.readonly,
            "risk": spec.risk,
            "category": spec.category,
            **ctx,
        }
        rule = self.rules.resolve(spec.name, merged)
        if rule is not None:
            return Decision(rule.effect, rule.id, rule.reason)

        # 未命中显式规则时的保守默认：只读放行，其余升级人工
        if spec.readonly:
            return Decision("auto", "DEFAULT-READONLY", "只读工具默认放行")
        return Decision("escalate", "DEFAULT-WRITE", "写操作默认转人工")
