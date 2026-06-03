"""OpenAI-compatible endpoints: /v1/models, /v1/chat/completions."""
from __future__ import annotations

import time

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.deepseek.client import ClientError
from app.deepseek.engine import GatewayError

from app.core import config
from app.db import store
from app.deepseek import prompt as P

router = APIRouter(prefix="/v1", tags=["openai"])


def _openai_error(message: str, status_code: int = 500, err_type: str = "server_error", code: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": err_type, "code": code}},
    )


def _http_status_for_error(exc: Exception) -> int:
    if isinstance(exc, GatewayError) and exc.error_kind == "pool_exhausted":
        return 503
    if isinstance(exc, ClientError) and exc.http_status:
        if exc.http_status == 429:
            return 429
        if 400 <= exc.http_status < 500:
            return 502
    msg = str(exc).lower()
    if "allocation_failed_no_account" in msg or "no_account" in msg:
        return 503
    if "rate" in msg or "muted" in msg or "overloaded" in msg:
        return 429
    return 503


def _mask_key(key: str) -> str:
    if not key:
        return ""
    return key[:8] + "..." + key[-4:] if len(key) > 14 else key[:6] + "..."


async def _auth(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing API key")
    key = authorization[7:].strip()
    if not await store.api_key_valid(key):
        raise HTTPException(401, "Invalid API key")
    return key


@router.get("/models")
async def list_models(authorization: str | None = Header(default=None)):
    await _auth(authorization)
    aliases = await store.get_setting("model_aliases", {}) or {}
    ids = [config.DEFAULT_MODEL] + [f"deepseek-{t}" for t in config.MODEL_TYPES
                                    if t != "default"]
    ids += list(aliases.keys())
    data = [{"id": mid, "object": "model", "created": int(time.time()),
             "owned_by": "max-deepseek"} for mid in dict.fromkeys(ids)]
    return {"object": "list", "data": data}


@router.post("/chat/completions")
async def chat_completions(request: Request,
                           authorization: str | None = Header(default=None)):
    key = await _auth(authorization)
    body = await request.json()

    engine = request.app.state.engine
    if engine is None:
        return _openai_error("Service is not ready", 503, "service_unavailable", "engine_not_ready")

    model_id = body.get("model") or config.DEFAULT_MODEL
    messages = body.get("messages") or []
    if not messages:
        return _openai_error("Missing messages", 400, "invalid_request_error", "missing_messages")

    aliases = await store.get_setting("model_aliases", {}) or {}
    try:
        model_type = P.resolve_model(model_id, config.MODEL_TYPES, aliases)
    except ValueError as e:
        return _openai_error(str(e), 400, "invalid_request_error", "invalid_model")

    prompt = P.build_prompt(messages)
    stream = bool(body.get("stream"))
    masked = _mask_key(key)
    key_id = await store.get_api_key_id(key)
    t0 = time.time()

    # reset per-request telemetry to avoid leaking previous request state into logs
    setattr(engine, "_last_account_id", None)
    setattr(engine, "_last_usage", (0, 0))

    _proxy_url = config.API_BASE

    if stream:
        async def gen():
            log_acc_id = None
            log_pt = 0
            log_ct = 0
            log_success = True
            log_err = ""
            try:
                async for chunk in engine.stream(model_id, model_type, prompt, body):
                    yield chunk
            except Exception as e:
                log_success = False
                log_err = str(e)
                raise
            finally:
                log_pt, log_ct = getattr(engine, "_last_usage", (0, 0))
                log_acc_id = getattr(engine, "_last_account_id", None)
                await store.add_log(model_id, masked, log_pt, log_ct,
                                    int((time.time() - t0) * 1000), log_success, log_err,
                                    key_id, log_acc_id, _proxy_url)
        return StreamingResponse(gen(), media_type="text/event-stream")

    try:
        result = await engine.complete(model_id, model_type, prompt, body)
        pt, ct = getattr(engine, "_last_usage", (0, 0))
        acc_id = getattr(engine, "_last_account_id", None)
        await store.add_log(model_id, masked, pt, ct,
                            int((time.time() - t0) * 1000), True, "", key_id, acc_id, _proxy_url)
        return JSONResponse(result)
    except Exception as e:  # noqa: BLE001
        acc_id = getattr(engine, "_last_account_id", None)
        await store.add_log(model_id, masked, 0, 0,
                            int((time.time() - t0) * 1000), False, f"request_failed: {e}", key_id, acc_id, _proxy_url)
        code = getattr(e, "error_kind", "upstream_error")
        return _openai_error(f"Gateway error: {e}", _http_status_for_error(e), "gateway_error", code)
