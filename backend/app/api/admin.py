"""Admin API: login JWT, status, stats, accounts, api keys, logs, config."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.core import config, crypto
from app.db import store
from app.deepseek.pool import Account, State

router = APIRouter(prefix="/admin/api", tags=["admin"])

JWT_ALGO = "HS256"


# ── auth ─────────────────────────────────────────────────────
async def _jwt_secret() -> str:
    secret = await store.get_setting("jwt_secret")
    if not secret:
        secret = crypto.random_secret()
        await store.set_setting("jwt_secret", secret)
    return secret


async def require_admin(authorization: str | None = Header(default=None)) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Chưa đăng nhập")
    token = authorization[7:]
    secret = await _jwt_secret()
    try:
        jwt.decode(token, secret, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        raise HTTPException(401, "Token không hợp lệ")
    return True


class LoginReq(BaseModel):
    password: str


class SetupReq(BaseModel):
    password: str


@router.post("/login")
async def login(req: LoginReq):
    pw_hash = await store.get_setting("admin_password_hash")
    if not pw_hash:
        raise HTTPException(403, "Chưa đặt mật khẩu admin")
    if req.password == "__check__":
        raise HTTPException(401, "check")
    if not crypto.verify_password(req.password, pw_hash):
        raise HTTPException(401, "Sai mật khẩu")
    secret = await _jwt_secret()
    now = int(time.time())
    token = jwt.encode({"sub": "admin", "iat": now, "exp": now + config.ADMIN_JWT_EXPIRE_SECONDS}, secret, algorithm=JWT_ALGO)
    return {"token": token}


@router.post("/setup")
async def setup(req: SetupReq):
    pw_hash = await store.get_setting("admin_password_hash")
    if pw_hash:
        raise HTTPException(403, "Mật khẩu đã được đặt")
    if len(req.password) < 6:
        raise HTTPException(400, "Mật khẩu tối thiểu 6 ký tự")
    await store.set_setting("admin_password_hash", crypto.hash_password(req.password))
    secret = await _jwt_secret()
    now = int(time.time())
    token = jwt.encode({"sub": "admin", "iat": now, "exp": now + config.ADMIN_JWT_EXPIRE_SECONDS}, secret, algorithm=JWT_ALGO)
    return {"token": token}


# ── status & stats ───────────────────────────────────────────
@router.get("/status")
async def status(request: Request, _: bool = Depends(require_admin)):
    pool = request.app.state.pool
    accounts = []
    summary = {"total": 0, "idle": 0, "busy": 0, "error": 0, "invalid": 0}
    if pool:
        summary = pool.summary()
        for a in pool.all():
            accounts.append({
                "email": a.email, "mobile": a.mobile,
                "state": a.state.name.lower(), "last_error": a.last_error,
                "cooldown_remaining": a.cooldown_remaining,
                "quarantine_remaining": a.quarantine_remaining,
                "enabled": a.enabled,
            })
    return {**summary, "accounts": accounts,
            "uptime_secs": int(time.time() - request.app.state.start_time)}


@router.get("/stats")
async def stats(request: Request, _: bool = Depends(require_admin)):
    summary = await store.stats_summary()
    summary["uptime_secs"] = int(time.time() - request.app.state.start_time)
    return summary


# ── accounts ─────────────────────────────────────────────────
class AccountReq(BaseModel):
    email: str = ""
    mobile: str = ""
    area_code: str = ""
    password: str
    label: str = ""


@router.get("/accounts")
async def get_accounts(request: Request, _: bool = Depends(require_admin)):
    pool = request.app.state.pool
    rows = await store.list_accounts()
    request_counts = await store.account_request_counts()
    state_map = {}
    if pool:
        for a in pool.all():
            state_map[a.id] = (a.state.name.lower(), a.error_count, a.last_error,
                               a.cooldown_remaining, a.quarantine_remaining)
    out = []
    for r in rows:
        st, ec, le, cd, qd = state_map.get(r["id"],
                                       ("idle", r["error_count"], r["last_error"], 0, int(float(r.get("quarantine_until", 0) - time.time())) if r.get("quarantine_until") else 0))
        out.append({
            "id": r["id"], "email": r["email"], "mobile": r["mobile"],
            "area_code": r["area_code"], "label": r["label"],
            "state": st, "error_count": ec, "last_error": le,
            "request_count": request_counts.get(r["id"], 0),
            "cooldown_remaining": cd,
            "quarantine_remaining": max(0, qd),
            "enabled": bool(r["enabled"]) if "enabled" in r.keys() else True,
        })
    return out


@router.post("/accounts")
async def create_account(req: AccountReq, request: Request, _: bool = Depends(require_admin)):
    if not req.email and not req.mobile:
        raise HTTPException(400, "Cần email hoặc số điện thoại")
    secret = await _jwt_secret()
    pw_enc = crypto.encrypt(req.password, secret)
    acc_id = await store.add_account(req.email, req.mobile, req.area_code, pw_enc, req.label)
    pool = request.app.state.pool
    if pool:
        acc = Account(id=acc_id, email=req.email, mobile=req.mobile,
                      area_code=req.area_code, password=req.password,
                      label=req.label, state=State.IDLE)
        pool.add(acc)
        # login nền (không chặn response)
        import asyncio
        asyncio.create_task(pool.init_account(acc))
    return {"id": acc_id, "ok": True}


@router.delete("/accounts/{account_id}")
async def remove_account(account_id: int, request: Request, _: bool = Depends(require_admin)):
    await store.delete_account(account_id)
    pool = request.app.state.pool
    if pool:
        pool.remove(account_id)
    return {"ok": True}


@router.post("/accounts/{account_id}/relogin")
async def relogin_account(account_id: int, request: Request, _: bool = Depends(require_admin)):
    pool = request.app.state.pool
    if not pool:
        raise HTTPException(503, "Pool chưa sẵn sàng")
    ok = await pool.relogin_single(account_id)
    return {"ok": ok}


@router.post("/accounts/{account_id}/test")
async def test_account(account_id: int, request: Request, _: bool = Depends(require_admin)):
    pool = request.app.state.pool
    if not pool:
        raise HTTPException(503, "Pool chưa sẵn sàng")
    return await pool.test_account(account_id)


@router.post("/accounts/disable-blocked")
async def disable_blocked_accounts(request: Request, _: bool = Depends(require_admin)):
    pool = request.app.state.pool
    ids: set[int] = set()
    if pool:
        for acc in pool.all():
            if acc.enabled and acc.state == State.COOLING:
                ids.add(acc.id)
    # Fallback theo DB để vẫn tắt được nếu runtime state chưa sync.
    for r in await store.list_accounts():
        if int(r.get("enabled", 1)) and int(r.get("state", 0)) == 4:
            ids.add(int(r["id"]))
    for account_id in ids:
        await store.set_account_enabled(account_id, False)
        if pool:
            await pool.set_enabled(account_id, False)
    return {"ok": True, "count": len(ids), "ids": sorted(ids)}


@router.post("/accounts/disable-busy")
async def disable_busy_accounts(request: Request, _: bool = Depends(require_admin)):
    pool = request.app.state.pool
    ids: set[int] = set()
    if pool:
        for acc in pool.all():
            if acc.enabled and acc.state in (State.BUSY, State.COOLING):
                ids.add(acc.id)
    # Fallback theo DB để vẫn tắt được nếu runtime state chưa sync.
    for r in await store.list_accounts():
        if int(r.get("enabled", 1)) and int(r.get("state", 0)) in (1, 4):
            ids.add(int(r["id"]))
    for account_id in ids:
        await store.set_account_enabled(account_id, False)
        if pool:
            await pool.set_enabled(account_id, False)
    return {"ok": True, "count": len(ids), "ids": sorted(ids)}


class EnableReq(BaseModel):
    enabled: bool


@router.post("/accounts/{account_id}/enable")
async def enable_account(account_id: int, req: EnableReq, request: Request,
                         _: bool = Depends(require_admin)):
    await store.set_account_enabled(account_id, req.enabled)
    pool = request.app.state.pool
    if pool:
        await pool.set_enabled(account_id, req.enabled)
    return {"ok": True, "enabled": req.enabled}


# ── api keys ─────────────────────────────────────────────────
class ApiKeyReq(BaseModel):
    description: str = ""


@router.get("/keys")
async def get_keys(_: bool = Depends(require_admin)):
    rows = await store.list_api_keys()
    return [{
        "id": r["id"],
        "key": r["key"],
        "description": r["description"],
        "is_active": bool(r["is_active"]),
        "created_at": r["created_at"],
        "request_count": r.get("request_count", 0) or 0,
        "total_tokens": r.get("total_tokens", 0) or 0,
        "prompt_tokens_used": r.get("prompt_tokens_used", 0) or 0,
        "completion_tokens_used": r.get("completion_tokens_used", 0) or 0,
        "success_count": r.get("success_count", 0) or 0,
        "avg_latency_ms": int(r.get("avg_latency_ms", 0) or 0),
        "last_used_at": r.get("last_used_at") or 0,
        "last_proxy_url": r.get("last_proxy_url") or "",
        "last_proxy_name": r.get("last_proxy_name") or "",
    } for r in rows]


@router.post("/keys")
async def create_key(req: ApiKeyReq, _: bool = Depends(require_admin)):
    key = crypto.new_api_key()
    kid = await store.add_api_key(key, req.description)
    return {"id": kid, "key": key}


@router.delete("/keys/{key_id}")
async def remove_key(key_id: int, _: bool = Depends(require_admin)):
    await store.delete_api_key(key_id)
    return {"ok": True}


# ── logs ─────────────────────────────────────────────────────
@router.get("/logs")
async def get_logs(limit: int = 100, _: bool = Depends(require_admin)):
    rows = await store.recent_logs(limit)
    return [{
        "timestamp": r["ts"], "model": r["model"], "api_key": r["api_key_masked"],
        "key_description": r["key_desc"] or "", "account_label": r["account_name"] or "",
        "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"],
        "latency_ms": r["latency_ms"], "success": bool(r["success"]), "error": r["error"],
        "proxy_url": r["proxy_url"] or "",
        "proxy_name": r["proxy_name"] or "",
    } for r in rows]


# ── models ───────────────────────────────────────────────────
@router.get("/models")
async def admin_models(_: bool = Depends(require_admin)):
    ids = [config.DEFAULT_MODEL] + [f"deepseek-{t}" for t in config.MODEL_TYPES if t != "default"]
    return {"object": "list",
            "data": [{"id": m, "object": "model", "owned_by": "max-deepseek"} for m in ids]}


# ── config ───────────────────────────────────────────────────
@router.get("/config")
async def get_config(_: bool = Depends(require_admin)):
    aliases = await store.get_setting("model_aliases", config.MODEL_ALIASES)
    return {
        "deepseek": {
            "api_base": config.API_BASE,
            "wasm_url": config.WASM_URL,
            "user_agent": config.USER_AGENT,
            "client_version": config.CLIENT_VERSION,
            "client_platform": config.CLIENT_PLATFORM,
            "client_locale": config.CLIENT_LOCALE,
            "model_types": config.MODEL_TYPES,
            "max_input_tokens": config.MAX_INPUT_TOKENS,
            "max_output_tokens": config.MAX_OUTPUT_TOKENS,
            "input_character_limits": config.INPUT_CHAR_LIMITS,
            "model_aliases": aliases,
        },
        "tool_call": {
            "extra_starts": await store.get_setting("tool_call_extra_starts", config.TOOL_CALL_EXTRA_STARTS),
            "extra_ends": await store.get_setting("tool_call_extra_ends", config.TOOL_CALL_EXTRA_ENDS),
        },
        "server": {
            "host": config.HOST,
            "port": config.PORT,
            "cors_origins": await store.get_setting("cors_origins", config.CORS_ORIGINS),
            "healthcheck_on_login": config.HEALTHCHECK_ON_LOGIN,
            "init_concurrency": config.INIT_CONCURRENCY,
            "recovery_interval": config.RECOVERY_INTERVAL,
            "acquire_timeout_ms": config.ACQUIRE_TIMEOUT_MS,
            "max_attempts": config.MAX_ATTEMPTS,
            "min_account_interval_ms": config.MIN_ACCOUNT_INTERVAL_MS,
        },
        "proxy_url": await store.get_setting("proxy_url", ""),
        "model_aliases": aliases,
        "password_set": bool(await store.get_setting("admin_password_hash")),
    }


class ConfigReq(BaseModel):
    proxy_url: str | None = None
    old_password: str | None = None
    new_password: str | None = None
    api_base: str | None = None
    wasm_url: str | None = None
    user_agent: str | None = None
    client_version: str | None = None
    client_platform: str | None = None
    client_locale: str | None = None
    model_types: list[str] | None = None
    max_input_tokens: dict[str, int] | None = None
    max_output_tokens: dict[str, int] | None = None
    input_character_limits: dict[str, int] | None = None
    model_aliases: dict[str, str] | None = None
    tool_call_extra_starts: list[str] | None = None
    tool_call_extra_ends: list[str] | None = None
    cors_origins: list[str] | None = None
    healthcheck_on_login: bool | None = None
    init_concurrency: int | None = None
    recovery_interval: int | None = None
    acquire_timeout_ms: int | None = None
    max_attempts: int | None = None
    min_account_interval_ms: int | None = None


def _clean_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL phải bắt đầu bằng http:// hoặc https://")
    return url


def _positive_int_map(name: str, value: dict[str, int]) -> dict[str, int]:
    cleaned = {}
    for k, v in value.items():
        if not k or int(v) <= 0:
            raise HTTPException(400, f"{name} không hợp lệ")
        cleaned[str(k)] = int(v)
    return cleaned


@router.post("/config")
async def save_config(req: ConfigReq, _: bool = Depends(require_admin)):
    if req.proxy_url is not None:
        await store.set_setting("proxy_url", req.proxy_url)
    if req.api_base is not None:
        config.API_BASE = _clean_url(req.api_base) or import_default_api_base()
        await store.set_setting("ds_api_base", "" if not req.api_base.strip() else config.API_BASE)
    if req.wasm_url is not None:
        config.WASM_URL = _clean_url(req.wasm_url) or config.WASM_URL
        await store.set_setting("wasm_url", config.WASM_URL)
    if req.user_agent is not None:
        config.USER_AGENT = req.user_agent.strip() or config.USER_AGENT
        await store.set_setting("user_agent", config.USER_AGENT)
    if req.client_version is not None:
        config.CLIENT_VERSION = req.client_version.strip() or config.CLIENT_VERSION
        await store.set_setting("client_version", config.CLIENT_VERSION)
    if req.client_platform is not None:
        config.CLIENT_PLATFORM = req.client_platform.strip() or config.CLIENT_PLATFORM
        await store.set_setting("client_platform", config.CLIENT_PLATFORM)
    if req.client_locale is not None:
        config.CLIENT_LOCALE = req.client_locale.strip() or config.CLIENT_LOCALE
        await store.set_setting("client_locale", config.CLIENT_LOCALE)
    if req.model_types is not None:
        types = [x.strip() for x in req.model_types if x.strip()]
        if not types:
            raise HTTPException(400, "model_types không được trống")
        config.MODEL_TYPES = types
        await store.set_setting("model_types", types)
    if req.max_input_tokens is not None:
        config.MAX_INPUT_TOKENS = _positive_int_map("max_input_tokens", req.max_input_tokens)
        await store.set_setting("max_input_tokens", config.MAX_INPUT_TOKENS)
    if req.max_output_tokens is not None:
        config.MAX_OUTPUT_TOKENS = _positive_int_map("max_output_tokens", req.max_output_tokens)
        await store.set_setting("max_output_tokens", config.MAX_OUTPUT_TOKENS)
    if req.input_character_limits is not None:
        config.INPUT_CHAR_LIMITS = _positive_int_map("input_character_limits", req.input_character_limits)
        await store.set_setting("input_character_limits", config.INPUT_CHAR_LIMITS)
    if req.model_aliases is not None:
        aliases = {k.strip(): v.strip() for k, v in req.model_aliases.items() if k.strip() and v.strip()}
        config.MODEL_ALIASES = aliases
        await store.set_setting("model_aliases", aliases)
    if req.tool_call_extra_starts is not None:
        config.TOOL_CALL_EXTRA_STARTS = [x for x in req.tool_call_extra_starts if x]
        await store.set_setting("tool_call_extra_starts", config.TOOL_CALL_EXTRA_STARTS)
    if req.tool_call_extra_ends is not None:
        config.TOOL_CALL_EXTRA_ENDS = [x for x in req.tool_call_extra_ends if x]
        await store.set_setting("tool_call_extra_ends", config.TOOL_CALL_EXTRA_ENDS)
    if req.cors_origins is not None:
        config.CORS_ORIGINS = [x.strip() for x in req.cors_origins if x.strip()]
        await store.set_setting("cors_origins", config.CORS_ORIGINS)
    if req.healthcheck_on_login is not None:
        config.HEALTHCHECK_ON_LOGIN = bool(req.healthcheck_on_login)
        await store.set_setting("healthcheck_on_login", config.HEALTHCHECK_ON_LOGIN)
    if req.init_concurrency is not None:
        if req.init_concurrency < 1 or req.init_concurrency > 20:
            raise HTTPException(400, "init_concurrency phải từ 1 đến 20")
        config.INIT_CONCURRENCY = req.init_concurrency
        await store.set_setting("init_concurrency", config.INIT_CONCURRENCY)
    if req.recovery_interval is not None:
        if req.recovery_interval < 10:
            raise HTTPException(400, "recovery_interval tối thiểu 10 giây")
        config.RECOVERY_INTERVAL = req.recovery_interval
        await store.set_setting("recovery_interval", config.RECOVERY_INTERVAL)
    if req.acquire_timeout_ms is not None:
        if req.acquire_timeout_ms < 1000:
            raise HTTPException(400, "acquire_timeout_ms tối thiểu 1000")
        config.ACQUIRE_TIMEOUT_MS = req.acquire_timeout_ms
        await store.set_setting("acquire_timeout_ms", config.ACQUIRE_TIMEOUT_MS)
    if req.max_attempts is not None:
        if req.max_attempts < 1 or req.max_attempts > 10:
            raise HTTPException(400, "max_attempts phải từ 1 đến 10")
        config.MAX_ATTEMPTS = req.max_attempts
        await store.set_setting("max_attempts", config.MAX_ATTEMPTS)
    if req.min_account_interval_ms is not None:
        if req.min_account_interval_ms < 0 or req.min_account_interval_ms > 10 * 60 * 1000:
            raise HTTPException(400, "min_account_interval_ms phải từ 0 đến 600000")
        config.MIN_ACCOUNT_INTERVAL_MS = req.min_account_interval_ms
        await store.set_setting("min_account_interval_ms", config.MIN_ACCOUNT_INTERVAL_MS)
    if req.new_password:
        pw_hash = await store.get_setting("admin_password_hash")
        if pw_hash and not crypto.verify_password(req.old_password or "", pw_hash):
            raise HTTPException(400, "Mật khẩu cũ không đúng")
        if len(req.new_password) < 6:
            raise HTTPException(400, "Mật khẩu mới tối thiểu 6 ký tự")
        await store.set_setting("admin_password_hash", crypto.hash_password(req.new_password))
    return {"ok": True}




class UpdateApplyReq(BaseModel):
    version: str | None = None


def _version_path() -> Path:
    return Path(__file__).resolve().parents[3] / "VERSION"


def _current_version() -> str:
    path = _version_path()
    if path.exists():
        value = path.read_text().strip()
        if value:
            return value
    return config.APP_VERSION


def _app_info() -> dict:
    return {
        "name": config.APP_NAME,
        "version": _current_version(),
        "repository": config.APP_REPOSITORY,
        "channel": config.UPDATE_CHANNEL,
        "author": {
            "name": config.APP_AUTHOR_NAME,
            "email": config.APP_AUTHOR_EMAIL,
        },
    }


def _parse_semver(value: str) -> tuple[int, ...]:
    parts = []
    for item in value.strip().lstrip("v").split("."):
        num = ''.join(ch for ch in item if ch.isdigit())
        parts.append(int(num or 0))
    return tuple(parts or [0])


def _default_manifest() -> dict:
    current = _current_version()
    return {
        "version": current,
        "channel": config.UPDATE_CHANNEL,
        "published_at": "",
        "download_url": config.APP_REPOSITORY,
        "release_url": config.APP_REPOSITORY,
        "changelog": ["Ban dang o phien ban moi nhat."],
        "notes": "Khong tim thay manifest tu xa. Dang dung metadata noi bo.",
        "author": {
            "name": config.APP_AUTHOR_NAME,
            "email": config.APP_AUTHOR_EMAIL,
        },
    }


def _load_update_manifest() -> dict:
    manifest = _default_manifest()
    url = (config.UPDATE_MANIFEST_URL or "").strip()
    if not url:
        return manifest
    try:
        with urlopen(url, timeout=config.UPDATE_CHECK_TIMEOUT) as res:
            data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, dict):
            manifest.update({k: v for k, v in data.items() if v not in (None, "")})
    except Exception as exc:
        manifest["notes"] = f"Khong the tai manifest: {exc}"
    manifest.setdefault("author", {"name": config.APP_AUTHOR_NAME, "email": config.APP_AUTHOR_EMAIL})
    return manifest


def _update_status() -> dict:
    current = _current_version()
    manifest = _load_update_manifest()
    latest = str(manifest.get("version") or current)
    update_available = _parse_semver(latest) > _parse_semver(current)
    return {
        "current_version": current,
        "latest_version": latest,
        "update_available": update_available,
        "channel": manifest.get("channel") or config.UPDATE_CHANNEL,
        "published_at": manifest.get("published_at") or "",
        "download_url": manifest.get("download_url") or config.APP_REPOSITORY,
        "release_url": manifest.get("release_url") or config.APP_REPOSITORY,
        "changelog": manifest.get("changelog") or [],
        "notes": manifest.get("notes") or "",
        "author": manifest.get("author") or {"name": config.APP_AUTHOR_NAME, "email": config.APP_AUTHOR_EMAIL},
        "allow_self_update": config.ALLOW_SELF_UPDATE,
        "update_command": config.UPDATE_COMMAND,
        "rollback_command": config.ROLLBACK_COMMAND,
    }


def _run_update_command(command: str, env_extra: dict[str, str] | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env["MAX_DEEPSEEK_CURRENT_VERSION"] = _current_version()
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(command, shell=True, capture_output=True, text=True, env=env, cwd=str(Path(__file__).resolve().parents[3]))
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, output.strip()


@router.get("/app")
async def app_info(_: bool = Depends(require_admin)):
    return _app_info()


@router.get("/update/status")
async def get_update_status(_: bool = Depends(require_admin)):
    return _update_status()


@router.post("/update/check")
async def check_update(_: bool = Depends(require_admin)):
    status = _update_status()
    await store.add_update_history(
        action="check",
        from_version=status["current_version"],
        to_version=status["latest_version"],
        status="available" if status["update_available"] else "up-to-date",
        notes=status.get("notes", ""),
    )
    return status


@router.get("/update/history")
async def update_history(limit: int = 20, _: bool = Depends(require_admin)):
    return await store.list_update_history(limit)


@router.post("/update/apply")
async def apply_update(req: UpdateApplyReq, _: bool = Depends(require_admin)):
    status = _update_status()
    target = (req.version or status["latest_version"]).strip()
    if not config.ALLOW_SELF_UPDATE:
        notes = "Self-update dang tat; hay dung lenh thu cong tu README."
        await store.add_update_history("apply", status["current_version"], target, "blocked", notes=notes, command=config.UPDATE_COMMAND)
        return {"ok": False, "status": "blocked", "message": notes, **status}
    rc, output = _run_update_command(config.UPDATE_COMMAND, {"MAX_DEEPSEEK_TARGET_VERSION": target})
    ok = rc == 0
    await store.add_update_history("apply", status["current_version"], target, "success" if ok else "failed", command=config.UPDATE_COMMAND, output=output)
    return {"ok": ok, "status": "success" if ok else "failed", "message": output or ("Cap nhat thanh cong" if ok else "Cap nhat that bai"), **status, "target_version": target}


@router.post("/update/rollback")
async def rollback_update(_: bool = Depends(require_admin)):
    status = _update_status()
    if not config.ALLOW_SELF_UPDATE:
        notes = "Self-update dang tat; rollback thu cong bang script."
        await store.add_update_history("rollback", status["current_version"], status["current_version"], "blocked", notes=notes, command=config.ROLLBACK_COMMAND)
        return {"ok": False, "status": "blocked", "message": notes}
    rc, output = _run_update_command(config.ROLLBACK_COMMAND)
    ok = rc == 0
    await store.add_update_history("rollback", status["current_version"], status["current_version"], "success" if ok else "failed", command=config.ROLLBACK_COMMAND, output=output)
    return {"ok": ok, "status": "success" if ok else "failed", "message": output or ("Rollback thanh cong" if ok else "Rollback that bai")}

# ── proxy (CF Worker URL) ────────────────────────────────────
import httpx as _httpx

class ProxyUrlReq(BaseModel):
    url: str


@router.get("/proxy")
async def get_proxy(request: Request, _: bool = Depends(require_admin)):
    db_url = await store.get_setting("ds_api_base", "")
    current = db_url or config.API_BASE
    return {
        "url": current,
        "default": config.API_BASE,
        "is_custom": bool(db_url),
        "source": "database" if db_url else "env/default",
    }


@router.put("/proxy")
async def update_proxy(req: ProxyUrlReq, request: Request, _: bool = Depends(require_admin)):
    url = req.url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL phải bắt đầu bằng http:// hoặc https://")
    old_url = await store.get_setting("ds_api_base", "")
    await store.set_setting("ds_api_base", url)
    # reload runtime config
    if url:
        config.API_BASE = url
    else:
        config.API_BASE = import_default_api_base()
    # Khi chuyển sang proxy mới, đảm bảo limit được khởi tạo
    if url and url != old_url:
        saved_limit = await store.get_setting("proxy_limit_custom", 100000)
        await store.set_proxy_limit("custom", saved_limit)
    return {"ok": True, "url": config.API_BASE}


def import_default_api_base() -> str:
    import os
    return os.getenv("DS_API_BASE", "https://chat.deepseek.com/api/v0")


# ── proxy pool CRUD ───────────────────────────────────────────────────
@router.get("/proxies")
async def list_proxies(_: bool = Depends(require_admin)):
    proxies = await store.list_proxies()
    # Gắn usage hôm nay cho mỗi proxy
    result = []
    for p in proxies:
        url_key = f"proxy_{p['id']}"
        usage = await store.get_proxy_today(url_key)
        result.append({**p, "usage_today": usage["hits"], "usage_limit": usage["limit"]})
    return result


class ProxyAddReq(BaseModel):
    name: str
    url: str


@router.post("/proxies")
async def add_proxy(req: ProxyAddReq, _: bool = Depends(require_admin)):
    name = req.name.strip()
    url = req.url.strip().rstrip("/")
    if not name:
        raise HTTPException(400, "Tên proxy không được trống")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL phải bắt đầu bằng http:// hoặc https://")
    pid = await store.add_proxy(name, url)
    return {"ok": True, "id": pid}


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(proxy_id: int, _: bool = Depends(require_admin)):
    await store.delete_proxy(proxy_id)
    # Nếu đang active proxy này thì reset về direct
    active = await store.get_active_proxy()
    if active is None:
        config.API_BASE = import_default_api_base()
        await store.set_setting("ds_api_base", "")
    return {"ok": True}


@router.post("/proxies/deactivate")
async def deactivate_proxy(_: bool = Depends(require_admin)):
    await store.set_proxy_active(None)
    config.API_BASE = import_default_api_base()
    await store.set_setting("ds_api_base", "")
    return {"ok": True}


@router.post("/proxies/{proxy_id}/activate")
async def activate_proxy(proxy_id: int, _: bool = Depends(require_admin)):
    proxies = await store.list_proxies()
    p = next((x for x in proxies if x["id"] == proxy_id), None)
    if not p:
        raise HTTPException(404, "Proxy không tồn tại")
    await store.set_proxy_active(proxy_id)
    config.API_BASE = p["url"]
    await store.set_setting("ds_api_base", p["url"])
    return {"ok": True, "url": p["url"]}


@router.post("/proxies/{proxy_id}/test")
async def test_proxy_pool(proxy_id: int, _: bool = Depends(require_admin)):
    proxies = await store.list_proxies()
    p = next((x for x in proxies if x["id"] == proxy_id), None)
    if not p:
        raise HTTPException(404, "Proxy không tồn tại")
    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            r = await client.get(p["url"] + "/health", follow_redirects=True)
            return {"ok": True, "status": r.status_code, "latency_ms": int(r.elapsed.total_seconds() * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class ProxyUpdateReq(BaseModel):
    name: str | None = None
    url: str | None = None
    enabled: bool | None = None


@router.patch("/proxies/{proxy_id}")
async def patch_proxy(proxy_id: int, req: ProxyUpdateReq, _: bool = Depends(require_admin)):
    await store.update_proxy(proxy_id, name=req.name, url=req.url, enabled=req.enabled)
    # Nếu đang dùng proxy này và URL thay đổi thì reload
    active = await store.get_active_proxy()
    if active and active["id"] == proxy_id and req.url:
        config.API_BASE = req.url.strip().rstrip("/")
        await store.set_setting("ds_api_base", config.API_BASE)
    return {"ok": True}


@router.post("/proxy/test")
async def test_proxy(req: ProxyUrlReq, _: bool = Depends(require_admin)):
    url = req.url.strip().rstrip("/")
    if not url:
        raise HTTPException(400, "URL không được trống")
    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url + "/health", follow_redirects=True)
            return {"ok": True, "status": r.status_code, "latency_ms": int(r.elapsed.total_seconds() * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── proxy usage tracking ──────────────────────────────────────
@router.get("/proxy/usage")
async def get_proxy_usage(_: bool = Depends(require_admin)):
    """Lấy usage hôm nay + 7 ngày gần đây cho proxy đang dùng."""
    active = await store.get_active_proxy()
    if active:
        url_key = f"proxy_{active['id']}"
    else:
        db_url = await store.get_setting("ds_api_base", "")
        url_key = "custom" if db_url else "default"
    today = await store.get_proxy_today(url_key)
    history = await store.get_proxy_usage_history(url_key, days=7)
    return {
        "url_key": url_key,
        "today": today,
        "history": history,
        "is_custom_proxy": url_key != "default",
    }


class ProxyLimitReq(BaseModel):
    limit: int


@router.put("/proxy/usage/limit")
async def set_proxy_usage_limit(req: ProxyLimitReq, _: bool = Depends(require_admin)):
    """Đặt giới hạn request/ngày cho proxy hiện tại."""
    if req.limit < 1000:
        raise HTTPException(400, "Giới hạn tối thiểu 1,000 request/ngày")
    active = await store.get_active_proxy()
    if active:
        url_key = f"proxy_{active['id']}"
    else:
        db_url = await store.get_setting("ds_api_base", "")
        url_key = "custom" if db_url else "default"
    await store.set_proxy_limit(url_key, req.limit)
    return {"ok": True, "url_key": url_key, "limit": req.limit}
