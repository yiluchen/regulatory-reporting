"""审计：七要素结构、按会话回放、JSONL 落盘。"""
from __future__ import annotations

import json

from harness.audit import AuditLog, AuditRecord

SEVEN = (
    "session_id",
    "identity",
    "model_version",
    "tool_call",
    "control_decision",
    "data_snapshot",
    "timestamp",
)


def make_record(session_id: str, timestamp: float, tool: str = "query_report_data") -> AuditRecord:
    return AuditRecord(
        session_id=session_id,
        user_id="u001",
        role="analyst",
        model="rule-based-demo",
        tool=tool,
        params={"org": "SH01"},
        effect="auto",
        rule_id="R-READ-AUTO",
        data_snapshot="2026-03-31",
        timestamp=timestamp,
    )


def test_to_dict_contains_seven_elements():
    payload = make_record("S001", 100.0).to_dict()
    for key in SEVEN:
        assert key in payload
    assert payload["identity"] == {"user_id": "u001", "role": "analyst"}
    assert payload["tool_call"]["tool"] == "query_report_data"
    assert payload["control_decision"]["effect"] == "auto"


def test_replay_sorted_by_timestamp_and_filtered_by_session():
    log = AuditLog()
    log.append(make_record("S002", 300.0))
    log.append(make_record("S001", 999.0))
    log.append(make_record("S002", 100.0))
    log.append(make_record("S002", 200.0))

    replayed = log.replay("S002")

    assert [item["timestamp"] for item in replayed] == [100.0, 200.0, 300.0]
    assert all(item["session_id"] == "S002" for item in replayed)
    assert len(replayed) == 3


def test_to_jsonl_writes_one_valid_json_per_record(tmp_path):
    log = AuditLog()
    log.append(make_record("S001", 100.0))
    log.append(make_record("S002", 200.0, tool="submit_report"))
    log.append(make_record("S003", 300.0, tool="delete_batch"))

    path = tmp_path / "audit.jsonl"
    log.to_jsonl(path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(log.records) == 3
    parsed = [json.loads(line) for line in lines]
    assert [item["tool"] for item in parsed] == ["query_report_data", "submit_report", "delete_batch"]
