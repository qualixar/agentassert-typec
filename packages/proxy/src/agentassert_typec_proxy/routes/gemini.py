from __future__ import annotations

import uuid

import orjson
from fastapi import APIRouter, Request
from fastapi.responses import Response

from agentassert_typec_proxy.enforcement import enforce_and_forward
from agentassert_typec_proxy.normalizer.gemini_norm import normalize_gemini

router = APIRouter()


@router.api_route("/v1/models/{model}:generateContent", methods=["POST"])
async def gemini_generate(request: Request, model: str) -> Response:
    monitor = request.app.state.monitor
    body = await request.body()
    payload = orjson.loads(body)
    payload["model"] = model
    session_id = request.headers.get("X-AgentAssert-Session", str(uuid.uuid4()))
    request_id = str(uuid.uuid4())
    canonical = normalize_gemini(payload, session_id, request_id)
    return await enforce_and_forward(canonical, monitor, request)
