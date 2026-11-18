"""ODS 抽取：全量初始化、按水位增量、按业务主键幂等 upsert。"""
from __future__ import annotations

from dataclasses import dataclass

from .config import TableSpec

Store = dict[tuple, dict]


def row_key(row: dict, spec: TableSpec) -> tuple:
    return tuple(str(row[k]) for k in spec.business_key)


def _watermark(row: dict, spec: TableSpec) -> str:
    return str(row.get(spec.watermark) or "")


def load_full(rows: list[dict], spec: TableSpec) -> list[dict]:
    """全量初始化：同主键保留水位最新的一条。"""
    latest: dict[tuple, dict] = {}
    for row in rows:
        key = row_key(row, spec)
        if key not in latest or _watermark(row, spec) >= _watermark(latest[key], spec):
            latest[key] = row
    return list(latest.values())


def load_incremental(
    rows: list[dict], spec: TableSpec, watermark: str | None
) -> tuple[list[dict], str | None]:
    """增量：只取水位之后的变更，返回 (变更行, 新水位)。"""
    if watermark is None:
        picked = rows
    else:
        picked = [r for r in rows if _watermark(r, spec) > watermark]
    new_watermark = max((_watermark(r, spec) for r in picked), default=watermark)
    return picked, new_watermark


@dataclass
class UpsertStats:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0

    @property
    def touched(self) -> int:
        return self.inserted + self.updated


def upsert(store: Store, rows: list[dict], spec: TableSpec) -> UpsertStats:
    """幂等落库：主键不存在则插入；存在且水位更新才覆盖，否则跳过。

    重放同一批次时 inserted/updated 都为 0，数据不变，因而可以安全重跑。
    """
    stats = UpsertStats()
    for row in rows:
        key = row_key(row, spec)
        old = store.get(key)
        if old is None:
            store[key] = dict(row)
            stats.inserted += 1
            continue
        if _watermark(row, spec) > _watermark(old, spec):
            store[key] = dict(row)
            stats.updated += 1
        else:
            stats.skipped += 1
    return stats


def to_rows(store: Store) -> list[dict]:
    return sorted(store.values(), key=lambda r: tuple(str(r.get(k)) for k in sorted(r)))
