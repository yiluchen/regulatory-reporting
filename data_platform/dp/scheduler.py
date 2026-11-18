"""轻量 DAG 调度：拓扑执行、节点重试、失败告警、下游跳过。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Task:
    name: str
    fn: Callable[[], object]
    depends_on: list[str] = field(default_factory=list)
    retries: int = 1
    retry_delay: float = 0.0


@dataclass
class TaskResult:
    name: str
    status: str          # success / failed / skipped
    attempts: int = 0
    error: str | None = None
    output: object = None


class Scheduler:
    def __init__(self, alert: Callable[[str, str], None] | None = None) -> None:
        self.tasks: dict[str, Task] = {}
        self.alert = alert

    def add(self, task: Task) -> "Scheduler":
        if any(dep not in self.tasks for dep in task.depends_on):
            raise ValueError(f"{task.name} 依赖的前置任务未注册")
        self.tasks[task.name] = task
        return self

    def _order(self) -> list[str]:
        pending = {name: set(t.depends_on) for name, t in self.tasks.items()}
        order: list[str] = []
        while pending:
            ready = sorted(n for n, deps in pending.items() if not deps)
            if not ready:
                raise ValueError("检测到循环依赖")
            for name in ready:
                order.append(name)
                pending.pop(name)
            for deps in pending.values():
                deps.difference_update(ready)
        return order

    def run(self) -> dict[str, TaskResult]:
        results: dict[str, TaskResult] = {}
        for name in self._order():
            task = self.tasks[name]
            broken = [d for d in task.depends_on if results[d].status != "success"]
            if broken:
                results[name] = TaskResult(name, "skipped", error=f"上游未成功: {','.join(broken)}")
                continue

            attempts = 0
            while attempts <= task.retries:
                attempts += 1
                try:
                    results[name] = TaskResult(name, "success", attempts, output=task.fn())
                    break
                except Exception as exc:  # noqa: BLE001 - 调度层需要兜住任意任务异常
                    if attempts > task.retries:
                        results[name] = TaskResult(name, "failed", attempts, error=str(exc))
                        if self.alert:
                            self.alert(name, str(exc))
                    elif task.retry_delay:
                        time.sleep(task.retry_delay)
        return results
