"""审计：七个要素全量留痕，可按会话回放。

审计由 Harness 写，Agent 没有"不写"的选项。
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

FIELDS = (
    "session_id",       # 会话
    "identity",         # 用户与岗位
    "model_version",    # 模型与版本
    "tool_call",        # 工具与参数
    "control_decision", # 控制点结论
    "data_snapshot",    # 数据版本/时点
    "timestamp",        # 时间
)


@dataclass
class AuditRecord:
    session_id: str
    user_id: str
    role: str
    model: str
    tool: str
    params: dict
    effect: str
    rule_id: str
    data_snapshot: str
    timestamp: float = field(default_factory=time.time)
    status: str = "ok"
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "identity": {"user_id": self.user_id, "role": self.role},
            "model_version": self.model,
            "tool_call": {"tool": self.tool, "params": self.params},
            "control_decision": {"effect": self.effect, "rule_id": self.rule_id},
            "data_snapshot": self.data_snapshot,
            "timestamp": self.timestamp,
            "status": self.status,
            "detail": self.detail,
        }


class AuditLog:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)

    def by_session(self, session_id: str) -> list[dict]:
        return [r.to_dict() for r in self.records if r.session_id == session_id]

    def replay(self, session_id: str) -> list[dict]:
        """按时间顺序回放一次运行：每一步的模型、工具、处置、数据版本。"""
        items = [r for r in self.records if r.session_id == session_id]
        return [r.to_dict() for r in sorted(items, key=lambda r: r.timestamp)]

    def to_jsonl(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            for record in self.records:
                fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
