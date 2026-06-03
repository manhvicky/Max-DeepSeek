"""Chat engine — ghép pool + prompt + sse, sinh response OpenAI (stream/non-stream)."""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import AsyncIterator, Optional

import tiktoken

from app.core import config
from app.deepseek import prompt as P
from app.deepseek import sse
from app.deepseek.client import ClientError


class GatewayError(ClientError):
    def __init__(self, message: str, error_kind: str = "upstream_error", retryable: bool = True, **kwargs):
        super().__init__(message, **kwargs)
        self.error_kind = error_kind
        self.retryable = retryable

from app.deepseek.pool import Account, AccountPool

_enc = None


_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def _extract_tool_calls(content: str) -> tuple[str, list[dict]]:
    """Convert DeepSeek <tool_call>{...}</tool_call> text into OpenAI tool_calls."""
    calls: list[dict] = []
    def repl(match: re.Match) -> str:
        raw = match.group(1)
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return match.group(0)
        name = obj.get("name")
        if not name:
            return match.group(0)
        args = obj.get("arguments", {})
        if not isinstance(args, str):
            args = json.dumps(args, ensure_ascii=False)
        calls.append({
            "id": obj.get("id") or f"call_{len(calls) + 1}",
            "type": "function",
            "function": {"name": name, "arguments": args},
        })
        return ""
    cleaned = _TOOL_CALL_RE.sub(repl, content).strip()
    return cleaned, calls


def _count_tokens(text: str) -> int:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return len(_enc.encode(text, allowed_special="all"))


def _chatcmpl_id() -> str:
    return "chatcmpl-" + format(int(time.time() * 1000) % (16**16), "016x")


class ChatEngine:
    def __init__(self, pool: AccountPool):
        self.pool = pool

    async def _run_once(self, model_type: str, prompt: str, body: dict,
                        first_try: bool) -> tuple[Account, str, str, dict]:
        """Chọn account, mở session, trả (account, session_id, pow_resp, payload)."""
        acc = await self.pool.acquire(wait=first_try)
        if acc is None:
            raise GatewayError("allocation_failed_no_account", error_kind="pool_exhausted", retryable=False, code=1001)
        session_id = await self.pool.client.create_session(acc.token)
        pow_resp = await self.pool._compute_pow(acc.token)
        payload = {
            "chat_session_id": session_id,
            "parent_message_id": None,
            "model_type": model_type,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": P.thinking_enabled(body, model_type),
            "search_enabled": body.get("_search_enabled", True),
            "preempt": False,
        }
        return acc, session_id, pow_resp, payload

    async def stream(self, model_id: str, model_type: str, prompt: str,
                     body: dict) -> AsyncIterator[str]:
        """Sinh OpenAI SSE chunks (data: {...}\\n\\n)."""
        prompt_tokens = _count_tokens(prompt)
        include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        cmpl_id = _chatcmpl_id()
        created = int(time.time())

        last_err = None
        for attempt in range(config.MAX_ATTEMPTS):
            first_try = attempt == 0
            acc = None
            session_id = None
            try:
                acc, session_id, pow_resp, payload = await self._run_once(
                    model_type, prompt, body, first_try)

                # chunk role đầu tiên
                yield self._chunk(cmpl_id, created, model_id,
                                  {"role": "assistant"},
                                  usage={"prompt_tokens": prompt_tokens,
                                         "completion_tokens": 0,
                                         "total_tokens": prompt_tokens})

                completion_tokens = 0
                finish = "stop"
                # Stream content immediately. Some clients (notably OpenClaw) send
                # a tools list but still expect visible tokens while the model runs;
                # buffering until the end makes the UI look like it never answers.
                buffer_for_tools = False
                content_parts = []
                byte_iter = self.pool.client.completion_stream(acc.token, pow_resp, payload)
                async for ev in sse.parse_sse(byte_iter):
                    if isinstance(ev, sse.Meta):
                        continue
                    if isinstance(ev, sse.ThinkDelta):
                        yield self._chunk(cmpl_id, created, model_id,
                                          {"reasoning_content": ev.content})
                    elif isinstance(ev, sse.ContentDelta):
                        if buffer_for_tools:
                            content_parts.append(ev.content)
                        else:
                            yield self._chunk(cmpl_id, created, model_id,
                                              {"content": ev.content})
                    elif isinstance(ev, sse.Done):
                        completion_tokens = ev.completion_tokens
                        finish = ev.finish_reason or "stop"
                    elif isinstance(ev, sse.ErrorEvent):
                        raise ClientError(ev.message, code=1001 if ev.overloaded else None)

                if buffer_for_tools:
                    content, tool_calls = _extract_tool_calls("".join(content_parts))
                    if tool_calls:
                        yield self._chunk(cmpl_id, created, model_id,
                                          {"tool_calls": tool_calls})
                        finish = "tool_calls"
                    elif content:
                        yield self._chunk(cmpl_id, created, model_id,
                                          {"content": content})

                # chunk kết thúc
                usage = None
                if include_usage:
                    usage = {"prompt_tokens": prompt_tokens,
                             "completion_tokens": completion_tokens,
                             "total_tokens": prompt_tokens + completion_tokens}
                yield self._chunk(cmpl_id, created, model_id, {},
                                  finish_reason=finish, usage=usage)
                yield "data: [DONE]\n\n"

                await self.pool.client.delete_session(acc.token, session_id)
                await self.pool.release(acc)
                self._last_usage = (prompt_tokens, completion_tokens)
                self._last_account_id = acc.id
                return

            except Exception as e:  # noqa: BLE001
                last_err = e
                if acc is not None:
                    await self.pool.mark_error(acc, str(e))
                    if session_id:
                        await self.pool.client.delete_session(acc.token, session_id)
                if attempt < config.MAX_ATTEMPTS - 1:
                    await asyncio.sleep(config.RETRY_BACKOFF_MS / 1000.0)
                    continue
                # hết lượt — emit error chunk
                summary = self.pool.summary()
                yield self._chunk(cmpl_id, created, model_id,
                                  {"content": f"[Lỗi: {last_err}; idle={summary['idle']} cooling={summary['cooling']} next_ready_in={summary['next_ready_in']}s]"},
                                  finish_reason="stop")
                yield "data: [DONE]\n\n"
                self._last_usage = (prompt_tokens, 0)
                self._last_account_id = acc.id if acc else None
                return

    async def complete(self, model_id: str, model_type: str, prompt: str,
                       body: dict) -> dict:
        """Non-stream: gom hết → 1 object OpenAI."""
        prompt_tokens = _count_tokens(prompt)
        last_err = None
        for attempt in range(config.MAX_ATTEMPTS):
            first_try = attempt == 0
            acc = None
            session_id = None
            try:
                acc, session_id, pow_resp, payload = await self._run_once(
                    model_type, prompt, body, first_try)
                content_parts = []
                reasoning_parts = []
                completion_tokens = 0
                finish = "stop"
                byte_iter = self.pool.client.completion_stream(acc.token, pow_resp, payload)
                async for ev in sse.parse_sse(byte_iter):
                    if isinstance(ev, sse.ThinkDelta):
                        reasoning_parts.append(ev.content)
                    elif isinstance(ev, sse.ContentDelta):
                        content_parts.append(ev.content)
                    elif isinstance(ev, sse.Done):
                        completion_tokens = ev.completion_tokens
                        finish = ev.finish_reason or "stop"
                    elif isinstance(ev, sse.ErrorEvent):
                        raise ClientError(ev.message, code=1001 if ev.overloaded else None)

                await self.pool.client.delete_session(acc.token, session_id)
                await self.pool.release(acc)

                content = "".join(content_parts)
                reasoning = "".join(reasoning_parts)
                content, tool_calls = _extract_tool_calls(content)
                msg = {"role": "assistant", "content": content or None}
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                    finish = "tool_calls"
                if reasoning:
                    msg["reasoning_content"] = reasoning
                self._last_usage = (prompt_tokens, completion_tokens)
                self._last_account_id = acc.id
                return {
                    "id": _chatcmpl_id(),
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model_id,
                    "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
                    "usage": {"prompt_tokens": prompt_tokens,
                              "completion_tokens": completion_tokens,
                              "total_tokens": prompt_tokens + completion_tokens},
                }
            except Exception as e:  # noqa: BLE001
                last_err = e
                if acc is not None:
                    await self.pool.mark_error(acc, str(e))
                    if session_id:
                        await self.pool.client.delete_session(acc.token, session_id)
                if attempt < config.MAX_ATTEMPTS - 1:
                    await asyncio.sleep(config.RETRY_BACKOFF_MS / 1000.0)
                    continue
                summary = self.pool.summary()
                raise ClientError(
                    f"{last_err}; pool idle={summary['idle']} busy={summary['busy']} cooling={summary['cooling']} error={summary['error']} next_ready_in={summary['next_ready_in']}s"
                )

    @staticmethod
    def _chunk(cmpl_id: str, created: int, model: str, delta: dict,
               finish_reason: Optional[str] = None,
               usage: Optional[dict] = None) -> str:
        obj = {
            "id": cmpl_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        if usage is not None:
            obj["usage"] = usage
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
