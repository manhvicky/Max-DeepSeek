"""Build prompt native DeepSeek từ messages OpenAI.

Tag fullwidth: ｜ = U+FF5C, ▁ = U+2581.
Gộp toàn bộ hội thoại thành 1 prompt string (DeepSeek web chỉ nhận 1 prompt).
"""
from __future__ import annotations

from typing import Any

BAR = "\uff5c"   # ｜
LOW = "\u2581"   # ▁
EOS = f"<{BAR}end{LOW}of{LOW}sentence{BAR}>"
SYSTEM = f"<{BAR}System{BAR}>"
USER = f"<{BAR}User{BAR}>"
ASSISTANT = f"<{BAR}Assistant{BAR}>"

TOOL_OUTPUTS_BEGIN = f"<{BAR}tool{LOW}outputs{LOW}begin{BAR}>"
TOOL_OUTPUT_BEGIN = f"<{BAR}tool{LOW}output{LOW}begin{BAR}>"
TOOL_OUTPUT_END = f"<{BAR}tool{LOW}output{LOW}end{BAR}>"


def _content_to_text(content: Any) -> str:
    """Multimodal content parts → text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                parts.append(str(part))
                continue
            t = part.get("type")
            if t == "text":
                parts.append(part.get("text", ""))
            elif t == "refusal":
                parts.append(part.get("refusal", ""))
            elif t == "image_url":
                url = (part.get("image_url") or {}).get("url", "")
                if url.startswith("http"):
                    parts.append(f"[请访问这个链接: {url}]")
                else:
                    detail = (part.get("image_url") or {}).get("detail", "auto")
                    parts.append(f"[图片: detail={detail}]")
            elif t == "input_audio":
                fmt = (part.get("input_audio") or {}).get("format", "")
                parts.append(f"[音频: format={fmt}]")
            elif t == "file":
                fn = (part.get("file") or {}).get("filename", "file")
                parts.append(f"[文件: filename={fn}]")
    return "".join(parts)


def _merge_consecutive(messages: list[dict]) -> list[dict]:
    """Gộp message liên tiếp cùng role (trừ tool)."""
    merged: list[dict] = []
    for msg in messages:
        role = msg.get("role")
        if (merged and role != "tool" and merged[-1].get("role") == role
                and "tool_calls" not in msg and "tool_calls" not in merged[-1]):
            prev = merged[-1]
            prev_text = _content_to_text(prev.get("content"))
            cur_text = _content_to_text(msg.get("content"))
            prev["content"] = f"{prev_text}\n{cur_text}"
        else:
            merged.append(dict(msg))
    return merged


def build_prompt(messages: list[dict]) -> str:
    """Build prompt string từ messages OpenAI."""
    merged = _merge_consecutive(messages)
    out: list[str] = []
    i = 0
    while i < len(merged):
        msg = merged[i]
        role = msg.get("role")
        text = _content_to_text(msg.get("content"))

        if role == "system":
            out.append(f"{SYSTEM}{text}")
        elif role == "user":
            out.append(f"{EOS}{USER}{text}")
        elif role == "assistant":
            out.append(f"{ASSISTANT}{text}")
        elif role == "function":
            name = msg.get("name", "")
            out.append(f"(name: {name})\n{text}")
        elif role == "tool":
            # group các tool message liên tiếp
            tool_msgs = [msg]
            j = i + 1
            while j < len(merged) and merged[j].get("role") == "tool":
                tool_msgs.append(merged[j])
                j += 1
            blocks = "".join(
                f"{TOOL_OUTPUT_BEGIN}{_content_to_text(t.get('content'))}{TOOL_OUTPUT_END}"
                for t in tool_msgs
            )
            out.append(f"{TOOL_OUTPUTS_BEGIN}{blocks}<｜tool▁outputs▁end｜>")
            i = j
            continue
        i += 1

    prompt = "".join(out)
    # luôn kết thúc bằng Assistant để model sinh tiếp
    if not prompt.rstrip().endswith(ASSISTANT):
        prompt += f"{ASSISTANT}\n"
    return prompt


def resolve_model(model_id: str, model_types: list[str], aliases: dict | None = None) -> str:
    """deepseek-{type} → model_type. Trả model_type hoặc raise."""
    aliases = aliases or {}
    mid = (model_id or "").lower()
    if mid in aliases:
        return aliases[mid]
    for mt in model_types:
        if mid == f"deepseek-{mt}":
            return mt
    # fallback: deepseek-chat/reasoner → default
    if mid in ("deepseek-chat", "deepseek-reasoner", "deepseek-default", ""):
        return "default"
    raise ValueError(f"不支持的模型: {model_id}")


def thinking_enabled(body: dict, model_type: str) -> bool:
    effort = body.get("reasoning_effort")
    if effort == "none":
        return False
    if model_type == "expert":
        return True
    return False  # default chat should be fast and stable; expert enables thinking
