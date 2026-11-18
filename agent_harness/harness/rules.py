"""风险规则：用 YAML 声明，代码只做匹配与仲裁。"""
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

import yaml

SEVERITY = {"auto": 0, "observe": 1, "escalate": 2, "block": 3}


@dataclass
class Rule:
    id: str
    action: str                       # 支持通配符，如 "data.query"
    effect: str                       # auto / observe / escalate / block
    risk: str = "low"
    reason: str = ""
    conditions: dict = field(default_factory=dict)

    def matches(self, action: str, ctx: dict) -> bool:
        if not fnmatch(action, self.action):
            return False
        for key, expected in self.conditions.items():
            if key == "role_in":
                if ctx.get("role") not in expected:
                    return False
            elif ctx.get(key) != expected:
                return False
        return True


class RuleSet:
    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules

    @classmethod
    def load(cls, path: str | Path) -> "RuleSet":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        rules = [
            Rule(
                id=item["id"],
                action=item["action"],
                effect=item["effect"],
                risk=item.get("risk", "low"),
                reason=item.get("reason", ""),
                conditions=item.get("conditions", {}),
            )
            for item in raw.get("rules", [])
        ]
        return cls(rules)

    def match(self, action: str, ctx: dict) -> list[Rule]:
        return [r for r in self.rules if r.matches(action, ctx)]

    def resolve(self, action: str, ctx: dict) -> Rule | None:
        """多条命中时取最严格的一条：block > escalate > observe > auto。"""
        matched = self.match(action, ctx)
        if not matched:
            return None
        return max(matched, key=lambda r: SEVERITY[r.effect])
