"""Agent Loop：并行工具调用、错误回灌、步数与超时熔断、全程审计。"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .audit import AuditLog, AuditRecord
from .control_point import ControlPoint
from .models import ModelRegistry, ToolCall
from .registry import ToolRegistry


@dataclass
class LoopResult:
    answer: str
    observations: list[dict] = field(default_factory=list)
    steps: int = 0
    stopped_reason: str = "model_done"
    session_id: str = ""


class AgentLoop:
    def __init__(
        self,
        registry: ToolRegistry,
        models: ModelRegistry,
        control: ControlPoint,
        audit: AuditLog,
        max_steps: int = 6,
        max_seconds: float = 15.0,
    ) -> None:
        self.registry = registry
        self.models = models
        self.control = control
        self.audit = audit
        self.max_steps = max_steps
        self.max_seconds = max_seconds

    def _execute(
        self,
        call: ToolCall,
        *,
        session_id: str,
        user_id: str,
        role: str,
        model: str,
        allowed_orgs: list[str],
    ) -> dict:
        call_org = call.args.get("org")
        ctx = {"cross_org": bool(call_org and call_org not in allowed_orgs)}
        snapshot = str(call.args.get("stat_date") or "2026-03-31")

        try:
            spec = self.registry.get(call.name)
        except KeyError:
            return self._record(
                session_id, user_id, role, model, call, "blocked", "UNREGISTERED",
                snapshot, "error", "工具未登记",
            )

        decision = self.control.review(spec, call.args, ctx)
        if decision.effect == "block":
            return self._record(
                session_id, user_id, role, model, call, decision.effect, decision.rule_id,
                snapshot, "blocked", decision.reason,
            )
        if decision.effect == "escalate":
            return self._record(
                session_id, user_id, role, model, call, decision.effect, decision.rule_id,
                snapshot, "pending_human", decision.reason,
            )

        try:
            result = self.registry.call(call.name, **call.args)
            status = "ok"
            detail = ""
        except Exception as exc:  # noqa: BLE001 - 工具异常回灌给模型，不中断整个循环
            result = {}
            status = "error"
            detail = str(exc)

        observation = self._record(
            session_id, user_id, role, model, call, decision.effect, decision.rule_id,
            snapshot, status, detail,
        )
        observation["result"] = result
        if decision.effect == "observe":
            observation["observed"] = True
        return observation

    def _record(
        self, session_id: str, user_id: str, role: str, model: str, call: ToolCall,
        effect: str, rule_id: str, snapshot: str, status: str, detail: str,
    ) -> dict:
        self.audit.append(
            AuditRecord(
                session_id=session_id,
                user_id=user_id,
                role=role,
                model=model,
                tool=call.name,
                params=call.args,
                effect=effect,
                rule_id=rule_id,
                data_snapshot=snapshot,
                status=status,
                detail=detail,
            )
        )
        return {
            "tool": call.name,
            "args": call.args,
            "status": status,
            "effect": effect,
            "rule_id": rule_id,
            "detail": detail,
        }

    def run(
        self,
        question: str,
        *,
        session_id: str,
        user_id: str,
        role: str,
        allowed_orgs: list[str],
    ) -> LoopResult:
        observations: list[dict] = []
        started = time.time()
        steps = 0
        stopped = "model_done"

        for step in range(1, self.max_steps + 1):
            if time.time() - started > self.max_seconds:
                stopped = "timeout"
                break
            model_adapter = self.models.resolve()
            calls = model_adapter.plan(question, observations)
            if not calls:
                break
            steps = step

            with ThreadPoolExecutor(max_workers=4) as pool:
                batch = list(
                    pool.map(
                        lambda c: self._execute(
                            c,
                            session_id=session_id,
                            user_id=user_id,
                            role=role,
                            model=model_adapter.name,
                            allowed_orgs=allowed_orgs,
                        ),
                        calls,
                    )
                )
            observations.extend(batch)

            # 整批都被拦或转人工：没有新信息可回灌，避免模型原地重试
            if not any(o["status"] == "ok" for o in batch):
                stopped = "no_progress"
                break
        else:
            stopped = "max_steps"

        answer = self.models.resolve().answer(question, observations)
        return LoopResult(
            answer=answer,
            observations=observations,
            steps=steps,
            stopped_reason=stopped,
            session_id=session_id,
        )
