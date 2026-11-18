"""演示：四种处置 + 七要素审计回放。"""
from __future__ import annotations

from pathlib import Path

from .audit import AuditLog
from .control_point import ControlPoint
from .loop import AgentLoop
from .models import ModelRegistry, RuleBasedModel
from .registry import ToolRegistry, ToolSpec
from .rules import RuleSet

CONFIG = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


def build_registry() -> ToolRegistry:
    def query_report_data(report: str, org: str, stat_date: str) -> dict:
        return {"rows": [{"org": org, "report": report, "loan_balance": 1_280_000_000.0}]}

    def search_regulation(question: str) -> dict:
        return {"hits": [{"chunk_id": "金监发〔2026〕1号#第五条", "score": 0.91}]}

    def submit_report(report: str, stat_date: str) -> dict:
        return {"submitted": True, "report": report}

    def delete_batch(batch: str) -> dict:
        return {"deleted": batch}

    registry = ToolRegistry()
    registry.register(ToolSpec("query_report_data", query_report_data, readonly=True, risk="low",
                               required=["report", "org", "stat_date"], description="只读查数"))
    registry.register(ToolSpec("search_regulation", search_regulation, readonly=True, risk="low",
                               required=["question"], category="kb", description="制度检索"))
    registry.register(ToolSpec("submit_report", submit_report, readonly=False, risk="high",
                               required=["report", "stat_date"], description="提交报送"))
    registry.register(ToolSpec("delete_batch", delete_batch, readonly=False, risk="high",
                               required=["batch"], description="删除批次"))
    return registry


def main() -> None:
    rules = RuleSet.load(CONFIG)
    audit = AuditLog()
    loop = AgentLoop(
        registry=build_registry(),
        models=ModelRegistry().register(RuleBasedModel(), activate=True),
        control=ControlPoint(rules),
        audit=audit,
        max_steps=4,
    )

    scenarios = [
        ("查询上海分行 G01 贷款余额", "analyst", ["SH01", "SH02"]),
        ("查询深圳分行 G01 贷款余额", "analyst", ["SH01", "SH02"]),
        ("提交本月 1104 报送", "analyst", ["SH01", "SH02"]),
        ("删除 202603 批次数据", "analyst", ["SH01", "SH02"]),
    ]

    for index, (question, role, orgs) in enumerate(scenarios, start=1):
        session = f"S{index:03d}"
        result = loop.run(question, session_id=session, user_id=f"u{index:03d}", role=role, allowed_orgs=orgs)
        print(f"\n[{session}] {question}  （权限机构 {orgs}）")
        for obs in result.observations:
            print(f"  {obs['tool']:<20} 处置={obs['effect']:<10} 状态={obs['status']:<13} 规则={obs['rule_id']}")
        print(f"  模型输出：{result.answer}")
        print(f"  结束原因：{result.stopped_reason}，步数：{result.steps}")

    print("\n=== 审计回放 S002（跨机构查询）===")
    for item in audit.replay("S002"):
        print(
            f"  {item['session_id']} | {item['identity']['user_id']}/{item['identity']['role']} | "
            f"{item['model_version']} | {item['tool_call']} | "
            f"{item['control_decision']} | {item['data_snapshot']} | ts={item['timestamp']:.0f}"
        )
    print(f"\n审计要素：{list(audit.replay('S002')[0].keys())[:7]}")


if __name__ == "__main__":
    main()
