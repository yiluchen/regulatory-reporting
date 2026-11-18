"""数据中台 - 配置模型与加载。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Column:
    name: str
    type: str = "str"          # str / int / float / date
    nullable: bool = True
    enum: list[str] = field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None


@dataclass
class TableSpec:
    name: str
    source: str
    target: str
    business_key: list[str]
    watermark: str
    columns: list[Column]

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def column(self, name: str) -> Column:
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(f"{self.name} 未定义字段 {name}")


def load_specs(path: str | Path) -> list[TableSpec]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    specs: list[TableSpec] = []
    for item in raw["tables"]:
        cols = [
            Column(
                name=c["name"],
                type=c.get("type", "str"),
                nullable=c.get("nullable", True),
                enum=c.get("enum", []),
                minimum=c.get("min"),
                maximum=c.get("max"),
            )
            for c in item["columns"]
        ]
        specs.append(
            TableSpec(
                name=item["name"],
                source=item["source"],
                target=item["target"],
                business_key=item["business_key"],
                watermark=item["watermark"],
                columns=cols,
            )
        )
    return specs
