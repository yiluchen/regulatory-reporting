"""证据裁判：过滤、去重、冲突检测、信源标注。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .state import Evidence

NUM_RE = re.compile(r"\d+(?:\.\d+)?%?")
TOPICS = {
    "逾期天数": ["逾期天数", "自然日"],
    "逾期账龄": ["逾期账龄", "账龄"],
    "不良认定": ["不良", "次级", "可疑", "损失"],
    "重组资产": ["重组", "观察期"],
    "报送时点": ["报送", "工作日", "季度"],
}


def _numbers(text: str) -> set[str]:
    return set(NUM_RE.findall(text))


def _topics(text: str) -> set[str]:
    return {name for name, words in TOPICS.items() if any(w in text for w in words)}


@dataclass
class JudgeResult:
    kept: list[Evidence] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    dropped: int = 0

    def summary(self) -> str:
        return f"保留 {len(self.kept)} 条，冲突 {len(self.conflicts)} 组，丢弃 {self.dropped} 条"


def judge(evidences: list[Evidence], as_of: str | None = None) -> JudgeResult:
    result = JudgeResult()
    seen: dict[str, Evidence] = {}

    for ev in evidences:
        if ev.get("effective_date") and as_of and ev["effective_date"] > as_of:
            result.dropped += 1
            continue
        cid = ev["chunk_id"]
        if cid in seen:
            result.dropped += 1
            if ev.get("score", 0) > seen[cid].get("score", 0):
                seen[cid] = ev
            continue
        seen[cid] = ev

    result.kept = sorted(seen.values(), key=lambda e: e.get("score", 0), reverse=True)

    # 冲突：不同信源、同一主题、关键数字不一致 → 显式打标，不强行合并
    for i, left in enumerate(result.kept):
        for right in result.kept[i + 1:]:
            if left["source"] == right["source"]:
                continue
            shared = _topics(left["text"]) & _topics(right["text"])
            if not shared:
                continue
            if _numbers(left["text"]) != _numbers(right["text"]):
                result.conflicts.append(
                    {
                        "topic": sorted(shared),
                        "left": left["chunk_id"],
                        "right": right["chunk_id"],
                        "note": "监管口径与行内口径存在差异，报告需分别标注",
                    }
                )

    # 冲突去重（同一对只保留一次）
    unique: dict[tuple, dict] = {}
    for item in result.conflicts:
        key = tuple(sorted((item["left"], item["right"])))
        unique[key] = item
    result.conflicts = list(unique.values())
    return result


def evidence_ids(evidences: list[Evidence]) -> set[str]:
    return {e["chunk_id"] for e in evidences}
