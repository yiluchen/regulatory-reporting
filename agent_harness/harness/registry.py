"""工具登记制：权限、只读标记、参数 schema、风险级别全部显式声明。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., dict]
    permission: str = "report.read"
    readonly: bool = True
    risk: str = "low"                       # low / medium / high
    description: str = ""
    required: list[str] = field(default_factory=list)
    category: str = "data"


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> "ToolRegistry":
        if spec.name in self._tools:
            raise ValueError(f"工具重复登记: {spec.name}")
        self._tools[spec.name] = spec
        return self

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"未登记的工具 {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def call(self, name: str, **kwargs) -> dict:
        spec = self.get(name)
        missing = [k for k in spec.required if k not in kwargs]
        if missing:
            raise ValueError(f"{name} 缺少参数 {missing}")
        return spec.fn(**kwargs)

    def describe(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "readonly": t.readonly,
                "risk": t.risk,
                "required": t.required,
            }
            for t in self._tools.values()
        ]


def tool(name: str, **options):
    """装饰器写法：@tool("search_regulation", readonly=True)。"""

    def decorator(fn: Callable[..., dict]) -> Callable[..., dict]:
        fn.__tool_spec__ = ToolSpec(name=name, fn=fn, **options)  # type: ignore[attr-defined]
        return fn

    return decorator


def collect(module) -> ToolRegistry:
    registry = ToolRegistry()
    for value in vars(module).values():
        spec = getattr(value, "__tool_spec__", None)
        if isinstance(spec, ToolSpec):
            registry.register(spec)
    return registry
