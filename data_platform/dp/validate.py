"""三层校验：字段级、表内、表间，并给出可复算的通过率。"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import TableSpec


@dataclass
class Issue:
    level: str          # field / table / cross
    table: str
    rule: str
    key: str
    message: str


@dataclass
class Report:
    checks: int = 0
    passed: int = 0
    issues: list[Issue] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return 1.0 if self.checks == 0 else self.passed / self.checks

    def add(self, ok: bool, issue: Issue | None = None) -> None:
        self.checks += 1
        if ok:
            self.passed += 1
        elif issue is not None:
            self.issues.append(issue)

    def summary(self) -> str:
        by_level: dict[str, int] = {}
        for issue in self.issues:
            by_level[issue.level] = by_level.get(issue.level, 0) + 1
        detail = "，".join(f"{k}:{v}" for k, v in sorted(by_level.items())) or "无"
        return (
            f"校验断言 {self.checks} 条，通过 {self.passed} 条，"
            f"通过率 {self.pass_rate:.2%}；问题分布 {detail}"
        )


def validate_table(rows: list[dict], spec: TableSpec, report: Report | None = None) -> Report:
    report = report or Report()
    seen: set[tuple] = set()

    for row in rows:
        key = tuple(str(row.get(k)) for k in spec.business_key)
        display = "|".join(key)

        for col in spec.columns:
            value = row.get(col.name)
            if value is None:
                report.add(
                    col.nullable,
                    Issue("field", spec.name, f"not_null:{col.name}", display, "关键字段为空"),
                )
                continue
            if col.enum:
                ok = str(value) in col.enum
                report.add(ok, Issue("field", spec.name, f"enum:{col.name}", display, f"非法枚举 {value}"))
            if col.minimum is not None or col.maximum is not None:
                ok = True
                if col.minimum is not None and float(value) < col.minimum:
                    ok = False
                if col.maximum is not None and float(value) > col.maximum:
                    ok = False
                report.add(ok, Issue("field", spec.name, f"range:{col.name}", display, f"越界 {value}"))

        ok = key not in seen
        seen.add(key)
        report.add(ok, Issue("table", spec.name, "unique_business_key", display, "主键重复"))

    return report


def validate_repayment_balance(rows: list[dict], report: Report) -> Report:
    """表内校验：本期已还本金不得超过应还本金。"""
    for row in rows:
        ok = float(row.get("principal_paid", 0)) <= float(row.get("principal_due", 0)) + 1e-6
        report.add(
            ok,
            Issue("table", "repayment", "principal_not_exceed_due", str(row.get("contract_no")), "已还本金大于应还"),
        )
        ok = float(row.get("interest_paid", 0)) <= float(row.get("interest_due", 0)) + 1e-6
        report.add(
            ok,
            Issue("table", "repayment", "interest_not_exceed_due", str(row.get("contract_no")), "已还利息大于应还"),
        )
    return report


def validate_cross_table(
    left_rows: list[dict],
    left_col: str,
    right_rows: list[dict],
    right_col: str,
    tolerance_ratio: float,
    name: str,
    report: Report,
) -> Report:
    """表间勾稽：两个口径的合计差异不能超过阈值。"""
    left = sum(float(r.get(left_col, 0) or 0) for r in left_rows)
    right = sum(float(r.get(right_col, 0) or 0) for r in right_rows)
    diff = abs(left - right)
    # 浮点与分位四舍五入会产生分币级尾差，1 分以内视为一致
    ok = right == 0 or diff / right <= tolerance_ratio or diff < 0.01
    report.add(
        ok,
        Issue("cross", name, "aggregate_tolerance", "total", f"差异 {diff:.2f} 超过 {tolerance_ratio:.0%}"),
    )
    return report
