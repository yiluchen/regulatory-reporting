"""只读沙箱：写语句与越权绕行都拦在数据库之前。"""
import pytest

from harness.sandbox import UnsafeQuery, apply_scope, assert_readonly, guarded_query


def test_allows_select_and_with():
    assert assert_readonly("SELECT 1") == "SELECT 1"
    assert assert_readonly("select * from t;") == "select * from t"
    assert assert_readonly("WITH x AS (SELECT 1) SELECT * FROM x").startswith("WITH")


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE dm.credit_wide SET loan_balance = 0",
        "delete from ods.loan_contract",
        "DROP TABLE dm.credit_wide",
        "select 1; delete from t",
        "select * into t2 from t",
    ],
)
def test_rejects_write_and_multi_statement(sql):
    with pytest.raises(UnsafeQuery):
        assert_readonly(sql)


def test_scope_is_injected_outside_subquery():
    sql = apply_scope("SELECT * FROM dm.credit_wide WHERE 1=1", "org_code", ["SH01", "SH02"])
    assert "org_code IN ('SH01', 'SH02')" in sql
    assert sql.startswith("SELECT * FROM (")


def test_guard_requires_permission():
    with pytest.raises(UnsafeQuery):
        apply_scope("SELECT 1", "org_code", [])


def test_guarded_query_runs_scoped_sql():
    seen = {}

    def runner(sql: str):
        seen["sql"] = sql
        return [{"org_code": "SH01"}]

    rows = guarded_query(runner, "select * from t", "org_code", ["SH01"])
    assert rows and "org_code IN ('SH01')" in seen["sql"]
