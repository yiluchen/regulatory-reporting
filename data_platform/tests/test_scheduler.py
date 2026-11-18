"""调度：重试、告警、下游跳过。"""
from dp.scheduler import Scheduler, Task


def test_retry_then_success():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("临时失败")
        return "ok"

    results = Scheduler().add(Task("extract", flaky, retries=2)).run()
    assert results["extract"].status == "success"
    assert results["extract"].attempts == 2


def test_failure_skips_downstream_and_alerts():
    alerts = []

    def boom():
        raise RuntimeError("上游断数")

    sched = Scheduler(alert=lambda name, err: alerts.append((name, err)))
    sched.add(Task("ods_load", boom, retries=1))
    sched.add(Task("dm_build", lambda: "never", depends_on=["ods_load"]))
    results = sched.run()

    assert results["ods_load"].status == "failed"
    assert results["ods_load"].attempts == 2
    assert results["dm_build"].status == "skipped"
    assert alerts and alerts[0][0] == "ods_load"


def test_topological_order():
    order = []
    sched = Scheduler()
    sched.add(Task("a", lambda: order.append("a")))
    sched.add(Task("b", lambda: order.append("b"), depends_on=["a"]))
    sched.add(Task("c", lambda: order.append("c"), depends_on=["b"]))
    sched.run()
    assert order == ["a", "b", "c"]
