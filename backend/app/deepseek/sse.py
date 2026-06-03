"""Parser SSE patch protocol của DeepSeek → StreamEvent.

DeepSeek stream các frame ngăn bởi \\n\\n, mỗi frame có event:/data:.
Data frame chứa JSON patch {p,o,v} (path/op/value). p và o persist xuyên frame.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


# ── Stream events (chuẩn hóa) ────────────────────────────────
@dataclass
class Meta:
    response_message_id: Optional[int] = None


@dataclass
class ThinkDelta:
    content: str


@dataclass
class ContentDelta:
    content: str


@dataclass
class Done:
    finish_reason: Optional[str]
    completion_tokens: int = 0


@dataclass
class ErrorEvent:
    message: str
    overloaded: bool = False


@dataclass
class _PatchState:
    """Giữ p/o persist và fragments."""
    cur_path: str = ""
    cur_op: str = "SET"
    fragments: list[dict] = field(default_factory=list)  # [{type, content}]
    status: str = ""
    completion_tokens: int = 0
    response_message_id: Optional[int] = None


def _frag_type(state: _PatchState) -> str:
    if state.fragments:
        return state.fragments[-1].get("type", "RESPONSE")
    return "RESPONSE"


async def parse_sse(byte_iter: AsyncIterator[bytes]) -> AsyncIterator[object]:
    """Nhận raw bytes, yield Meta/ThinkDelta/ContentDelta/Done/ErrorEvent."""
    state = _PatchState()
    buffer = b""
    meta_sent = False
    checked_envelope = False

    async for chunk in byte_iter:
        buffer += chunk

        # DeepSeek có thể trả JSON envelope thẳng (không phải SSE) khi lỗi:
        # account muted, biz_code != 0... Bắt sớm ở chunk đầu.
        if not checked_envelope and b'"event:' not in buffer and buffer.lstrip()[:1] == b"{":
            stripped = buffer.lstrip()
            try:
                env = json.loads(stripped)
            except json.JSONDecodeError:
                env = None
            if isinstance(env, dict) and ("code" in env or "biz_code" in env):
                checked_envelope = True
                data = env.get("data") or {}
                biz_code = data.get("biz_code", env.get("biz_code", 0))
                if env.get("code", 0) != 0 or biz_code != 0:
                    msg = data.get("biz_msg") or env.get("msg") or f"biz_code={biz_code}"
                    over = biz_code in (1001, 1201) or env.get("code") in (1001, 1201)
                    yield ErrorEvent(str(msg), overloaded=over)
                    return

        while b"\n\n" in buffer:
            frame, buffer = buffer.split(b"\n\n", 1)
            text = frame.decode("utf-8", errors="ignore")
            event, data_str = _parse_frame(text)

            if event == "ready":
                try:
                    d = json.loads(data_str) if data_str else {}
                    rid = d.get("response_message_id")
                    if rid is not None:
                        state.response_message_id = int(rid)
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
                if not meta_sent:
                    meta_sent = True
                    yield Meta(state.response_message_id)
                continue

            if event == "hint":
                low = data_str.lower()
                if "rate_limit" in low:
                    yield ErrorEvent("rate_limit_reached", overloaded=True)
                    return
                if "input_exceeds_limit" in low:
                    yield ErrorEvent("input quá dài")
                    return
                yield ErrorEvent(f"hint: {data_str[:120]}")
                return

            if event == "close":
                fr = "stop" if state.status == "FINISHED" else None
                yield Done(fr, state.completion_tokens)
                return

            if not data_str or data_str == "[DONE]":
                continue

            try:
                obj = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            # JSON error trong stream
            if isinstance(obj, dict) and "biz_code" in obj and obj.get("biz_code"):
                code = obj.get("biz_code")
                over = code in (1001, 1201)
                yield ErrorEvent(f"biz_code={code}", overloaded=over)
                return

            if not meta_sent:
                meta_sent = True
                yield Meta(state.response_message_id)

            async for ev in _apply_patch(obj, state):
                yield ev

    # buffer hết mà chưa close
    fr = "stop" if state.status == "FINISHED" else None
    yield Done(fr, state.completion_tokens)


def _parse_frame(text: str) -> tuple[str, str]:
    """Tách event: và data: từ 1 frame SSE."""
    event = ""
    data_lines = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    return event, "\n".join(data_lines)


async def _apply_patch(obj: dict, state: _PatchState):
    """Xử lý 1 patch {p,o,v}. Hỗ trợ BATCH (đệ quy)."""
    p = obj.get("p")
    o = obj.get("o")
    v = obj.get("v")

    if p is not None:
        state.cur_path = p
    if o is not None:
        state.cur_op = o

    path = p if p is not None else state.cur_path
    op = o if o is not None else state.cur_op

    # BATCH: v là list các patch con
    if op == "BATCH" and isinstance(v, list):
        for item in v:
            if isinstance(item, dict):
                child = dict(item)
                # full path = parent/sub nếu con có p
                if "p" in child and path:
                    child["p"] = f"{path}/{child['p']}" if child["p"] else path
                async for ev in _apply_patch(child, state):
                    yield ev
        return

    norm = (path or "").lstrip("/")

    # Initial snapshot: v.response chứa fragments
    if isinstance(v, dict) and "response" in v:
        resp = v["response"]
        if isinstance(resp, dict):
            frags = resp.get("fragments")
            if isinstance(frags, list):
                state.fragments = []
                for f in frags:
                    ftype = f.get("type", "RESPONSE")
                    fcontent = f.get("content", "") or ""
                    state.fragments.append({"type": ftype, "content": fcontent})
                    # emit content có sẵn trong snapshot
                    if fcontent:
                        if ftype == "THINK":
                            yield ThinkDelta(fcontent)
                        else:
                            yield ContentDelta(fcontent)
            st = resp.get("status")
            if st:
                state.status = st
            tu = resp.get("accumulated_token_usage")
            if isinstance(tu, int):
                state.completion_tokens = tu
        return

    # content append vào fragment cuối
    if "fragments" in norm and norm.endswith("content"):
        if isinstance(v, str):
            if not state.fragments:
                state.fragments.append({"type": "RESPONSE", "content": ""})
            state.fragments[-1]["content"] += v
            if _frag_type(state) == "THINK":
                yield ThinkDelta(v)
            else:
                yield ContentDelta(v)
        return

    # push fragment mới (v có thể là 1 dict hoặc list các dict)
    if norm.endswith("response/fragments") and op == "APPEND":
        items = v if isinstance(v, list) else [v]
        for item in items:
            if not isinstance(item, dict):
                continue
            ftype = item.get("type", "RESPONSE")
            fcontent = item.get("content", "") or ""
            state.fragments.append({"type": ftype, "content": fcontent})
            if fcontent:
                if ftype == "THINK":
                    yield ThinkDelta(fcontent)
                else:
                    yield ContentDelta(fcontent)
        return

    # status
    if norm.endswith("response/status"):
        if isinstance(v, str):
            state.status = v
        return

    # token usage
    if norm.endswith("accumulated_token_usage"):
        if isinstance(v, int):
            state.completion_tokens = v
        return
