from __future__ import annotations

import uuid

import orjson
from fastapi import APIRouter, Request
from fastapi.responses import Response

from agentassert_typec_proxy.enforcement import enforce_and_forward
from agentassert_typec_proxy.normalizer.openai_norm import normalize_openai

router = APIRouter()


@router.api_route("/v1/chat/completions", methods=["POST"])
async def completions(request: Request) -> Response:
    monitor = request.app.state.monitor
    body = await request.body()
    payload = orjson.loads(body)
    session_id = request.headers.get("X-AgentAssert-Session", str(uuid.uuid4()))
    request_id = str(uuid.uuid4())
    canonical = normalize_openai(payload, session_id, request_id)
    return await enforce_and_forward(canonical, monitor, request, "/v1/chat/completions", request.app.state.upstream_overrides)
