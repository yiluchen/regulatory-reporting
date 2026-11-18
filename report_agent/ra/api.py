"""HTTP 接口：缓存命中直接返回，研究线 SSE 流式输出。"""
from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .cache import SemanticCache
from .memory import LayeredMemory
from .nodes import ReportNodes
from .retrieval import DualRetriever

app = FastAPI(title="ReportAgent")

# 生产环境从容器注入真实检索器；此处留出装配点，避免接口层依赖具体实现
_state: dict = {}


class Ask(BaseModel):
    question: str
    user_id: str = "anonymous"


def configure(dual: DualRetriever) -> None:
    _state["nodes"] = ReportNodes(dual, cache=SemanticCache(), memory=LayeredMemory())


def _ensure_ready() -> ReportNodes:
    """未显式注入检索器时，用离线默认装配启动，保证服务开箱可跑。"""
    if "nodes" not in _state:
        from .demo import build_dual

        configure(build_dual())
    return _state["nodes"]


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ready": "nodes" in _state}


@app.post("/chat/stream")
async def chat_stream(payload: Ask) -> StreamingResponse:
    nodes = _ensure_ready()
    state = {"question": payload.question, "user_id": payload.user_id, "trace": []}
    state.update(nodes.route(state))

    async def events():
        if state["route"] == "cache":
            yield f"event: cache\ndata: {json.dumps({'layer': state.get('cache_layer')}, ensure_ascii=False)}\n\n"
            for piece in _chunks(state["answer"]):
                yield f"data: {piece}\n\n"
                await asyncio.sleep(0)
            yield "event: done\ndata: end\n\n"
            return

        yield "event: state\ndata: research_line\n\n"
        result = nodes.run_research(state)
        for piece in _chunks(result.get("draft", "")):
            yield f"data: {piece}\n\n"
            await asyncio.sleep(0)
        yield f"event: done\ndata: {json.dumps({'unverified': result.get('unverified', [])})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


def _chunks(text: str, size: int = 24) -> list[str]:
    return [text[i:i + size].replace("\n", "\\n") for i in range(0, len(text), size)] or [""]
