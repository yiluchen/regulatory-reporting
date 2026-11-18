"""模型适配：统一接口，按配置热切换，业务代码不感知具体模型。"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


class ModelAdapter:
    """模型只需实现 plan / answer 两个动作。"""

    name: str = "base"

    def plan(self, question: str, observations: list[dict]) -> list[ToolCall]:
        raise NotImplementedError

    def answer(self, question: str, observations: list[dict]) -> str:
        raise NotImplementedError


class OpenAICompatAdapter(ModelAdapter):
    """内网 vLLM / 任意 OpenAI 兼容服务。"""

    def __init__(self, name: str, base_url: str, model: str, api_key: str = "EMPTY", timeout: float = 30) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def _chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload: dict = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            payload["tools"] = tools
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def plan(self, question: str, observations: list[dict]) -> list[ToolCall]:
        messages = [{"role": "system", "content": "只调用已登记工具，先查后答。"}]
        messages.append({"role": "user", "content": question})
        for obs in observations:
            messages.append({"role": "tool", "content": json.dumps(obs, ensure_ascii=False)})
        data = self._chat(messages)
        calls = data["choices"][0]["message"].get("tool_calls") or []
        return [ToolCall(c["function"]["name"], json.loads(c["function"]["arguments"])) for c in calls]

    def answer(self, question: str, observations: list[dict]) -> str:
        messages = [
            {"role": "system", "content": "基于工具结果作答，标明依据，不确定就说明。"},
            {"role": "user", "content": question},
            {"role": "user", "content": json.dumps(observations, ensure_ascii=False)},
        ]
        return self._chat(messages)["choices"][0]["message"]["content"]


class RuleBasedModel(ModelAdapter):
    """离线演示用的确定性模型：按问题关键词决定调用哪些工具。"""

    name = "rule-based-demo"

    def plan(self, question: str, observations: list[dict]) -> list[ToolCall]:
        if observations:
            return []
        calls: list[ToolCall] = []
        if any(w in question for w in ("余额", "数据", "多少")):
            org = "SZ01" if "深圳" in question else "SH01"
            calls.append(ToolCall("query_report_data", {"report": "G01", "org": org, "stat_date": "2026-03-31"}))
        if any(w in question for w in ("口径", "逾期", "制度")):
            calls.append(ToolCall("search_regulation", {"question": "逾期天数口径"}))
        if any(w in question for w in ("提交", "报送")):
            calls.append(ToolCall("submit_report", {"report": "G01", "stat_date": "2026-03-31"}))
        if any(w in question for w in ("删除", "清理")):
            calls.append(ToolCall("delete_batch", {"batch": "202603"}))
        return calls

    def answer(self, question: str, observations: list[dict]) -> str:
        ok = [o for o in observations if o.get("status") == "ok"]
        blocked = [o for o in observations if o.get("status") == "blocked"]
        pending = [o for o in observations if o.get("status") == "pending_human"]
        return (
            f"已完成 {len(ok)} 项工具调用，{len(blocked)} 项被拦截，{len(pending)} 项待人工确认。"
        )


class ModelRegistry:
    """按名字取模型；切换模型只改配置，不改业务代码。"""

    def __init__(self) -> None:
        self._models: dict[str, ModelAdapter] = {}
        self.active: str | None = None

    def register(self, adapter: ModelAdapter, activate: bool = False) -> "ModelRegistry":
        self._models[adapter.name] = adapter
        if activate or self.active is None:
            self.active = adapter.name
        return self

    def activate(self, name: str) -> None:
        if name not in self._models:
            raise KeyError(f"未注册的模型 {name}")
        self.active = name

    def resolve(self, name: str | None = None) -> ModelAdapter:
        key = name or self.active
        if key is None:
            raise RuntimeError("没有可用模型")
        return self._models[key]
