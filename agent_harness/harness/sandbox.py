"""只读沙箱：语法白名单 + 强制注入机构过滤。

写语句在任何调用路径上都到不了数据库；机构范围由运行时注入，
不依赖 Agent 在参数里"自觉"带上。
"""
from __future__ import annotations

import re

WRITE_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|into)\b", re.I
)
ALLOWED_PREFIX = re.compile(r"^\s*(select|with)\b", re.I)


class UnsafeQuery(ValueError):
    pass


def assert_readonly(sql: str) -> str:
    if not ALLOWED_PREFIX.match(sql):
        raise UnsafeQuery("只允许 SELECT / WITH 查询")
    if WRITE_RE.search(sql):
        raise UnsafeQuery("检测到写操作关键字")
    if ";" in sql.rstrip().rstrip(";"):
        raise UnsafeQuery("不允许多语句")
    return sql.strip().rstrip(";")


def apply_scope(sql: str, org_column: str, allowed_orgs: list[str]) -> str:
    """包一层外层查询强制限机构，避免子查询里绕过过滤。"""
    if not allowed_orgs:
        raise UnsafeQuery("没有任何机构权限")
    quoted = ", ".join("'" + org.replace("'", "''") + "'" for org in allowed_orgs)
    return f"SELECT * FROM ({sql}) AS scoped WHERE scoped.{org_column} IN ({quoted})"


def guarded_query(runner, sql: str, org_column: str, allowed_orgs: list[str]):
    safe = assert_readonly(sql)
    scoped = apply_scope(safe, org_column, allowed_orgs)
    return runner(scoped)
