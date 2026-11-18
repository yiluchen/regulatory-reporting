"""DWD 清洗：标准化、去重、非法值拦截。"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import TableSpec


@dataclass
class CleanStats:
    input_rows: int = 0
    output_rows: int = 0
    null_business_key: int = 0
    invalid_value: int = 0
    duplicated: int = 0
    rejects: list[dict] = field(default_factory=list)

    @property
    def dropped(self) -> int:
        return self.input_rows - self.output_rows


def _coerce(value, kind: str):
    if value is None:
        return None
    if kind == "str":
        text = str(value).strip()
        return text or None
    if kind == "int":
        return int(float(value))
    if kind == "float":
        return float(value)
    if kind == "date":
        return str(value)[:10]
    return value


def _valid(row: dict, spec: TableSpec) -> bool:
    for col in spec.columns:
        value = row.get(col.name)
        if value is None:
            if not col.nullable:
                return False
            continue
        if col.enum and str(value) not in col.enum:
            return False
        if col.minimum is not None and float(value) < col.minimum:
            return False
        if col.maximum is not None and float(value) > col.maximum:
            return False
    return True


def clean(rows: list[dict], spec: TableSpec) -> tuple[list[dict], CleanStats]:
    stats = CleanStats(input_rows=len(rows))
    cleaned: dict[tuple, dict] = {}

    for raw in rows:
        row: dict = {}
        failed = False
        for col in spec.columns:
            try:
                row[col.name] = _coerce(raw.get(col.name), col.type)
            except (TypeError, ValueError):
                failed = True
                break
        if failed or any(row.get(k) in (None, "") for k in spec.business_key):
            stats.null_business_key += 0 if failed else 1
            stats.invalid_value += 1 if failed else 0
            stats.rejects.append({"stage": "normalize", "row": raw})
            continue
        if not _valid(row, spec):
            stats.invalid_value += 1
            stats.rejects.append({"stage": "constraint", "row": row})
            continue

        key = tuple(str(row[k]) for k in spec.business_key)
        previous = cleaned.get(key)
        if previous is not None:
            stats.duplicated += 1
            if str(row.get(spec.watermark)) < str(previous.get(spec.watermark)):
                continue
        cleaned[key] = row

    stats.output_rows = len(cleaned)
    return list(cleaned.values()), stats
