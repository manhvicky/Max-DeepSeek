"""Max-DeepSeek — entrypoint FastAPI."""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin as admin_api
from app.api import openai as openai_api
from app.core import config, crypto
from app.db import store
from app.deepseek.client import DsClient
from app.deepseek.engine import ChatEngine
from app.deepseek.pool import Account, AccountPool, State
from app.deepseek.pow import PowSolver

WEB_DIST = os.path.join(os.path.dirname(__file__), "..", "web_dist")


async def _load_pool(app: FastAPI) -> None:
    """Khởi tạo DeepSeek client, PoW solver, account pool từ DB."""
    client = DsClient()
    # tải + cache WASM
    wasm_bytes = None
    if os.path.exists(config.WASM_CACHE):
        with open(config.WASM_CACHE, "rb") as f:
            wasm_bytes = f.read()
    if not wasm_bytes:
        try:
            wasm_bytes = await client.get_wasm()
            os.makedirs(config.DATA_DIR, exist_ok=True)
            with open(config.WASM_CACHE, "wb") as f:
                f.write(wasm_bytes)
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Không tải được WASM: {e}")
            app.state.pool = None
            app.state.engine = None
            return

    solver = PowSolver(wasm_bytes)
    secret = await store.get_setting("jwt_secret")
    if not secret:
        secret = crypto.random_secret()
        await store.set_setting("jwt_secret", secret)

    async def on_state_change(acc: Account) -> None:
        await store.update_account_enabled_state(acc.id, int(acc.state),
                                                 acc.error_count, acc.enabled,
                                                 acc.last_error, acc.cooldown_until,
                                                 acc.cooldown_strikes, acc.quarantine_until)

    pool = AccountPool(client, solver, on_state_change=on_state_change)

    # nạp account từ DB
    rows = await store.list_accounts()
    accounts = []
    for r in rows:
        pw = crypto.decrypt(r["password_enc"], secret)
        enabled = bool(r["enabled"]) if "enabled" in r.keys() else True
        import time as _t
        cd_until = float(r["cooldown_until"]) if "cooldown_until" in r.keys() else 0.0
        cd_strikes = int(r["cooldown_strikes"]) if "cooldown_strikes" in r.keys() else 0
        q_until = float(r["quarantine_until"]) if "quarantine_until" in r.keys() else 0.0
        # Restore COOLING nếu cooldown hoặc quarantine chưa hết, ngược lại IDLE để recovery tự login lại
        restore_state = State.COOLING if (State(int(r["state"])) == State.COOLING and max(cd_until, q_until) > _t.time()) else State.IDLE
        accounts.append(Account(
            id=r["id"], email=r["email"], mobile=r["mobile"],
            area_code=r["area_code"], password=pw, label=r["label"],
            state=restore_state, enabled=enabled,
            cooldown_until=cd_until, cooldown_strikes=cd_strikes,
            quarantine_until=q_until,
        ))
    app.state.pool = pool
    app.state.engine = ChatEngine(pool)

    if accounts:
        import asyncio
        asyncio.create_task(_init_accounts_bg(pool, accounts))
    pool.start_recovery()


async def _init_accounts_bg(pool: AccountPool, accounts: list) -> None:
    await pool.init_all(accounts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    await store.init_db()
    # Load runtime config saved from the admin Configuration page.
    _saved_base = await store.get_setting("ds_api_base", "")
    if _saved_base:
        config.API_BASE = _saved_base
    for _key, _attr in {
        "wasm_url": "WASM_URL",
        "user_agent": "USER_AGENT",
        "client_version": "CLIENT_VERSION",
        "client_platform": "CLIENT_PLATFORM",
        "client_locale": "CLIENT_LOCALE",
        "model_types": "MODEL_TYPES",
        "max_input_tokens": "MAX_INPUT_TOKENS",
        "max_output_tokens": "MAX_OUTPUT_TOKENS",
        "input_character_limits": "INPUT_CHAR_LIMITS",
        "model_aliases": "MODEL_ALIASES",
        "tool_call_extra_starts": "TOOL_CALL_EXTRA_STARTS",
        "tool_call_extra_ends": "TOOL_CALL_EXTRA_ENDS",
        "cors_origins": "CORS_ORIGINS",
        "healthcheck_on_login": "HEALTHCHECK_ON_LOGIN",
        "init_concurrency": "INIT_CONCURRENCY",
        "recovery_interval": "RECOVERY_INTERVAL",
        "acquire_timeout_ms": "ACQUIRE_TIMEOUT_MS",
        "max_attempts": "MAX_ATTEMPTS",
        "min_account_interval_ms": "MIN_ACCOUNT_INTERVAL_MS",
    }.items():
        _val = await store.get_setting(_key, None)
        if _val is not None:
            setattr(config, _attr, _val)
    app.state.start_time = time.time()
    app.state.pool = None
    app.state.engine = None
    await _load_pool(app)
    yield
    if app.state.pool:
        app.state.pool.stop_recovery()


app = FastAPI(title="Max-DeepSeek", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(openai_api.router)
app.include_router(admin_api.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── static UI ────────────────────────────────────────────────
if os.path.isdir(WEB_DIST):
    app.mount("/admin/assets", StaticFiles(directory=os.path.join(WEB_DIST, "assets")),
              name="assets")

    @app.get("/")
    async def root():
        return RedirectResponse("/admin")

    @app.get("/admin/{path:path}")
    @app.get("/admin")
    async def admin_spa(path: str = ""):
        index = os.path.join(WEB_DIST, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"error": "UI chưa build"}
