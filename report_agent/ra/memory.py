"""分层记忆：短期滑动窗口 + 超阈值压缩，长期偏好跨会话保留。"""
from __future__ import annotations

from collections import deque


class LayeredMemory:
    def __init__(self, window: int = 6, compress_at: int = 8) -> None:
        self.window = window
        self.compress_at = compress_at
        self.recent: deque[str] = deque(maxlen=window)
        self.summary: str = ""
        self.long_term: dict[str, list[str]] = {}

    def add_turn(self, user_id: str, question: str, answer: str) -> None:
        self.recent.append(f"Q: {question}\nA: {answer}")
        if len(self.recent) >= self.compress_at:
            self._compress()

    def _compress(self) -> None:
        """压缩为一句摘要，控制上下文长度，避免 token 随会话线性增长。"""
        if not self.recent:
            return
        topics = []
        for item in self.recent:
            first = item.splitlines()[0].replace("Q: ", "").strip()
            topics.append(first[:20])
        merged = "；".join(topics[-4:])
        self.summary = (self.summary + "；" + merged).strip("；")[-300:]

    def remember(self, user_id: str, preference: str) -> None:
        bucket = self.long_term.setdefault(user_id, [])
        if preference not in bucket:
            bucket.append(preference)

    def context(self, user_id: str) -> str:
        parts = []
        if self.summary:
            parts.append(f"历史摘要：{self.summary}")
        if self.recent:
            parts.append("近期会话：\n" + "\n".join(self.recent))
        prefs = self.long_term.get(user_id, [])
        if prefs:
            parts.append("长期偏好：" + "；".join(prefs))
        return "\n".join(parts)
