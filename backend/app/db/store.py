"""SQLite async layer cho Max-DeepSeek."""
from __future__ import annotations

import datetime as _dt
import json
import time
from typing import Any, Optional

import aiosqlite

from app.core import config

_db: Optional[aiosqlite.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT DEFAULT '',
    mobile      TEXT DEFAULT '',
    area_code   TEXT DEFAULT '',
    password_enc TEXT DEFAULT '',
    label       TEXT DEFAULT '',
    state       INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_error  TEXT DEFAULT '',
    enabled     INTEGER DEFAULT 1,
    created_at  INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS api_keys (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    is_active   INTEGER DEFAULT 1,
    created_at  INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS request_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            INTEGER,
    model         TEXT,
    api_key_masked TEXT,
    api_key_id    INTEGER DEFAULT NULL,
    account_id    INTEGER DEFAULT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    latency_ms    INTEGER DEFAULT 0,
    success       INTEGER DEFAULT 1,
    error         TEXT DEFAULT '',
    proxy_url     TEXT DEFAULT '',
    proxy_id      INTEGER DEFAULT NULL,
    proxy_name    TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS proxy_daily_hits (
    date           TEXT NOT NULL,
    url_key        TEXT NOT NULL DEFAULT 'default',
    hits           INTEGER DEFAULT 0,
    limit_per_day  INTEGER DEFAULT 100000,
    PRIMARY KEY (date, url_key)
);
CREATE TABLE IF NOT EXISTS proxy_pool (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT DEFAULT '',
    url         TEXT DEFAULT '',
    enabled     INTEGER DEFAULT 1,
    is_active   INTEGER DEFAULT 0,
    created_at  INTEGER DEFAULT 0
);
"""


async def init_db() -> None:
    global _db
    _db = await aiosqlite.connect(config.DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _migrate()
    await _db.commit()


async def _migrate() -> None:
    """Migration cho DB cũ."""
    # thêm cột enabled vào accounts
    cols = await db().execute("PRAGMA table_info(accounts)")
    col_names = {r[1] for r in await cols.fetchall()}
    if "enabled" not in col_names:
        await db().execute("ALTER TABLE accounts ADD COLUMN enabled INTEGER DEFAULT 1")
        await db().commit()
    # thêm api_key_id, account_id vào request_logs
    cols2 = await db().execute("PRAGMA table_info(request_logs)")
    log_cols = {r[1] for r in await cols2.fetchall()}
    if "api_key_id" not in log_cols:
        await db().execute("ALTER TABLE request_logs ADD COLUMN api_key_id INTEGER DEFAULT NULL")
    if "account_id" not in log_cols:
        await db().execute("ALTER TABLE request_logs ADD COLUMN account_id INTEGER DEFAULT NULL")
    # cooldown persist
    cols3 = await db().execute("PRAGMA table_info(accounts)")
    acc_cols = {r[1] for r in await cols3.fetchall()}
    if "cooldown_until" not in acc_cols:
        await db().execute("ALTER TABLE accounts ADD COLUMN cooldown_until REAL DEFAULT 0.0")
    if "cooldown_strikes" not in acc_cols:
        await db().execute("ALTER TABLE accounts ADD COLUMN cooldown_strikes INTEGER DEFAULT 0")
    if "quarantine_until" not in acc_cols:
        await db().execute("ALTER TABLE accounts ADD COLUMN quarantine_until REAL DEFAULT 0.0")
    # thêm proxy fields vào request_logs
    cols4 = await db().execute("PRAGMA table_info(request_logs)")
    log_cols2 = {r[1] for r in await cols4.fetchall()}
    if "proxy_url" not in log_cols2:
        await db().execute("ALTER TABLE request_logs ADD COLUMN proxy_url TEXT DEFAULT ''")
    if "proxy_id" not in log_cols2:
        await db().execute("ALTER TABLE request_logs ADD COLUMN proxy_id INTEGER DEFAULT NULL")
    if "proxy_name" not in log_cols2:
        await db().execute("ALTER TABLE request_logs ADD COLUMN proxy_name TEXT DEFAULT ''")
    await db().commit()
    # proxy_daily_hits table (migration cho DB cũ chưa có)
    await db().execute(
        "CREATE TABLE IF NOT EXISTS proxy_daily_hits ("
        "date TEXT NOT NULL, url_key TEXT NOT NULL DEFAULT 'default', "
        "hits INTEGER DEFAULT 0, limit_per_day INTEGER DEFAULT 100000, "
        "PRIMARY KEY (date, url_key))"
    )
    # indexes cho logs/dashboard
    await db().execute("CREATE INDEX IF NOT EXISTS idx_request_logs_ts ON request_logs(ts)")
    await db().execute("CREATE INDEX IF NOT EXISTS idx_request_logs_api_key_id ON request_logs(api_key_id)")
    await db().execute("CREATE INDEX IF NOT EXISTS idx_request_logs_account_id ON request_logs(account_id)")
    await db().execute("CREATE INDEX IF NOT EXISTS idx_request_logs_proxy_id ON request_logs(proxy_id)")
    await db().execute("CREATE INDEX IF NOT EXISTS idx_request_logs_proxy_url ON request_logs(proxy_url)")
    # hashed API keys for public releases; legacy plaintext keys are migrated lazily.
    cols5 = await db().execute("PRAGMA table_info(api_keys)")
    key_cols = {r[1] for r in await cols5.fetchall()}
    if "key_hash" not in key_cols:
        await db().execute("ALTER TABLE api_keys ADD COLUMN key_hash TEXT DEFAULT ''")
    if "key_masked" not in key_cols:
        await db().execute("ALTER TABLE api_keys ADD COLUMN key_masked TEXT DEFAULT ''")
    rows = await db().execute("SELECT id, key FROM api_keys WHERE key_hash='' AND key!=''")
    import hashlib as _hashlib
    for row in await rows.fetchall():
        raw = row[1]
        masked = raw[:8] + "..." + raw[-4:] if len(raw) > 14 else raw[:6] + "..."
        await db().execute("UPDATE api_keys SET key=?, key_hash=?, key_masked=? WHERE id=?", (masked, _hashlib.sha256(raw.encode()).hexdigest(), masked, row[0]))
    await db().execute("CREATE INDEX IF NOT EXISTS idx_proxy_daily_hits_date_key ON proxy_daily_hits(date, url_key)")
    await db().execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
    await db().commit()
    # proxy_pool table
    await db().execute(
        "CREATE TABLE IF NOT EXISTS proxy_pool ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT DEFAULT '', url TEXT DEFAULT '', "
        "enabled INTEGER DEFAULT 1, is_active INTEGER DEFAULT 0, "
        "created_at INTEGER DEFAULT 0)"
    )
    await db().commit()


def db() -> aiosqlite.Connection:
    assert _db is not None, "DB chưa init"
    return _db


# ── settings ─────────────────────────────────────────────────
async def get_setting(key: str, default: Any = None) -> Any:
    async with db().execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
        row = await cur.fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


async def set_setting(key: str, value: Any) -> None:
    val = json.dumps(value, ensure_ascii=False)
    await db().execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, val),
    )
    await db().commit()


# ── accounts ─────────────────────────────────────────────────
async def list_accounts() -> list[dict]:
    async with db().execute("SELECT * FROM accounts ORDER BY id") as cur:
        return [dict(r) for r in await cur.fetchall()]


async def account_request_counts() -> dict[int, int]:
    async with db().execute(
        "SELECT account_id, COUNT(*) FROM request_logs WHERE account_id IS NOT NULL GROUP BY account_id"
    ) as cur:
        return {int(row[0]): int(row[1]) for row in await cur.fetchall()}


async def add_account(email: str, mobile: str, area_code: str,
                      password_enc: str, label: str) -> int:
    cur = await db().execute(
        "INSERT INTO accounts(email,mobile,area_code,password_enc,label,state,created_at) "
        "VALUES(?,?,?,?,?,0,?)",
        (email, mobile, area_code, password_enc, label, int(time.time())),
    )
    await db().commit()
    return cur.lastrowid


async def delete_account(account_id: int) -> None:
    await db().execute("DELETE FROM accounts WHERE id=?", (account_id,))
    await db().commit()


async def update_account_state(account_id: int, state: int,
                               error_count: int, last_error: str = "",
                               cooldown_until: float = 0.0,
                               cooldown_strikes: int = 0,
                               quarantine_until: float = 0.0) -> None:
    await db().execute(
        "UPDATE accounts SET state=?, error_count=?, last_error=?, cooldown_until=?, cooldown_strikes=?, quarantine_until=? WHERE id=?",
        (state, error_count, last_error, cooldown_until, cooldown_strikes, quarantine_until, account_id),
    )
    await db().commit()


async def update_account_enabled_state(account_id: int, state: int,
                                       error_count: int, enabled: bool,
                                       last_error: str = "",
                                       cooldown_until: float = 0.0,
                                       cooldown_strikes: int = 0,
                                       quarantine_until: float = 0.0) -> None:
    await db().execute(
        "UPDATE accounts SET state=?, error_count=?, enabled=?, last_error=?, cooldown_until=?, cooldown_strikes=?, quarantine_until=? WHERE id=?",
        (state, error_count, 1 if enabled else 0, last_error, cooldown_until, cooldown_strikes, quarantine_until, account_id),
    )
    await db().commit()


async def set_account_enabled(account_id: int, enabled: bool) -> None:
    await db().execute(
        "UPDATE accounts SET enabled=? WHERE id=?",
        (1 if enabled else 0, account_id),
    )
    await db().commit()


# ── api keys ─────────────────────────────────────────────────
async def list_api_keys() -> list[dict]:
    """List API keys kèm thống kê usage từ request_logs."""
    async with db().execute(
        "SELECT k.*, "
        "COUNT(l.id) AS request_count, "
        "COALESCE(SUM(l.prompt_tokens + l.completion_tokens), 0) AS total_tokens, "
        "COALESCE(SUM(l.prompt_tokens), 0) AS prompt_tokens_used, "
        "COALESCE(SUM(l.completion_tokens), 0) AS completion_tokens_used, "
        "COALESCE(SUM(l.success), 0) AS success_count, "
        "COALESCE(AVG(l.latency_ms), 0) AS avg_latency_ms, "
        "MAX(l.ts) AS last_used_at "
        "FROM api_keys k "
        "LEFT JOIN request_logs l ON l.api_key_id = k.id "
        "GROUP BY k.id "
        "ORDER BY k.id"
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    # Lấy proxy_url gần nhất cho từng key
    for row in rows:
        async with db().execute(
            "SELECT proxy_url, proxy_name FROM request_logs WHERE api_key_id=? ORDER BY id DESC LIMIT 1",
            (row["id"],),
        ) as cur:
            last = await cur.fetchone()
        row["key"] = row.get("key_masked") or (_mask_key(row.get("key") or "") if row.get("key") else "")
        row["last_proxy_url"] = last["proxy_url"] if last else ""
        row["last_proxy_name"] = last["proxy_name"] if last else ""
    return rows


def _mask_key(key: str) -> str:
    return key[:8] + "..." + key[-4:] if len(key) > 14 else key[:6] + "..."


async def add_api_key(key: str, description: str) -> int:
    from app.core import crypto
    cur = await db().execute(
        "INSERT INTO api_keys(key,key_hash,key_masked,description,is_active,created_at) VALUES(?,?,?,?,1,?)",
        (_mask_key(key), crypto.hash_api_key(key), _mask_key(key), description, int(time.time())),
    )
    await db().commit()
    return cur.lastrowid


async def delete_api_key(key_id: int) -> None:
    await db().execute("DELETE FROM api_keys WHERE id=?", (key_id,))
    await db().commit()


async def api_key_valid(key: str) -> bool:
    from app.core import crypto
    key_hash = crypto.hash_api_key(key)
    async with db().execute(
        "SELECT 1 FROM api_keys WHERE (key_hash=? OR key=?) AND is_active=1", (key_hash, key)
    ) as cur:
        return await cur.fetchone() is not None


async def get_api_key_id(key: str) -> int | None:
    """Lấy ID của API key."""
    from app.core import crypto
    key_hash = crypto.hash_api_key(key)
    async with db().execute("SELECT id FROM api_keys WHERE key_hash=? OR key=?", (key_hash, key)) as cur:
        row = await cur.fetchone()
        return row[0] if row else None


# ── logs ─────────────────────────────────────────────────────
async def add_log(model: str, api_key_masked: str, prompt_tokens: int,
                  completion_tokens: int, latency_ms: int,
                  success: bool, error: str = "", api_key_id: int | None = None,
                  account_id: int | None = None, proxy_url: str = "") -> None:
    proxy_id = None
    proxy_name = "Direct"
    url_key = "default"
    try:
        from app.core import config as _cfg
        import os as _os
        default_base = _os.getenv("DS_API_BASE", "https://chat.deepseek.com/api/v0")
        active = await get_active_proxy()
        if active:
            proxy_id = active["id"]
            proxy_name = active["name"]
            url_key = f"proxy_{active['id']}"
        elif _cfg.API_BASE != default_base:
            proxy_name = "Custom"
            url_key = "custom"
    except Exception:
        pass

    await db().execute(
        "INSERT INTO request_logs(ts,model,api_key_masked,api_key_id,account_id,prompt_tokens,"
        "completion_tokens,latency_ms,success,error,proxy_url,proxy_id,proxy_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (int(time.time()), model, api_key_masked, api_key_id, account_id, prompt_tokens,
         completion_tokens, latency_ms, 1 if success else 0, error, proxy_url, proxy_id, proxy_name),
    )
    await db().commit()
    try:
        await increment_proxy_hits(url_key)
    except Exception:
        pass


async def recent_logs(limit: int = 100) -> list[dict]:
    async with db().execute(
        "SELECT l.*, k.description as key_desc, "
        "COALESCE(a.label, a.email, a.mobile) as account_name "
        "FROM request_logs l "
        "LEFT JOIN api_keys k ON l.api_key_id = k.id "
        "LEFT JOIN accounts a ON l.account_id = a.id "
        "ORDER BY l.id DESC LIMIT ?", (limit,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


async def stats_summary() -> dict:
    async with db().execute(
        "SELECT COUNT(*) c, "
        "SUM(success) ok, "
        "SUM(prompt_tokens) pt, "
        "SUM(completion_tokens) ct, "
        "AVG(latency_ms) lat FROM request_logs"
    ) as cur:
        row = await cur.fetchone()
    total = row["c"] or 0
    ok = row["ok"] or 0
    return {
        "total_requests": total,
        "success_requests": ok,
        "failed_requests": total - ok,
        "total_prompt_tokens": row["pt"] or 0,
        "total_completion_tokens": row["ct"] or 0,
        "avg_latency_ms": int(row["lat"] or 0),
    }


# ── proxy daily usage ─────────────────────────────────────────
def _today_utc7() -> str:
    """Ngày hôm nay theo UTC+7 (Asia/Ho_Chi_Minh)."""
    utc7 = _dt.timezone(_dt.timedelta(hours=7))
    return _dt.datetime.now(utc7).strftime("%Y-%m-%d")


async def increment_proxy_hits(url_key: str = "default") -> None:
    """Tăng counter request proxy hôm nay +1. Tự tạo row nếu chưa có."""
    today = _today_utc7()
    # Lấy limit đã lưu cho url_key này (có thể admin đã đổi)
    saved_limit = await get_setting(f"proxy_limit_{url_key}", 100000)
    await db().execute(
        "INSERT INTO proxy_daily_hits(date, url_key, hits, limit_per_day) VALUES(?,?,1,?) "
        "ON CONFLICT(date, url_key) DO UPDATE SET hits = hits + 1",
        (today, url_key, saved_limit),
    )
    await db().commit()


async def get_proxy_today(url_key: str = "default") -> dict:
    """Lấy usage hôm nay cho một proxy key."""
    today = _today_utc7()
    saved_limit = await get_setting(f"proxy_limit_{url_key}", 100000)
    async with db().execute(
        "SELECT hits, limit_per_day FROM proxy_daily_hits WHERE date=? AND url_key=?",
        (today, url_key)
    ) as cur:
        row = await cur.fetchone()
    hits = row["hits"] if row else 0
    limit = row["limit_per_day"] if row else saved_limit
    return {
        "date": today,
        "url_key": url_key,
        "hits": hits,
        "limit": limit,
        "remaining": max(0, limit - hits),
        "percent_used": round(hits / limit * 100, 1) if limit > 0 else 0,
    }


async def get_proxy_usage_history(url_key: str = "default", days: int = 7) -> list[dict]:
    """Lấy usage N ngày gần đây."""
    utc7 = _dt.timezone(_dt.timedelta(hours=7))
    today = _dt.datetime.now(utc7)
    saved_limit = await get_setting(f"proxy_limit_{url_key}", 100000)
    result = []
    for i in range(days - 1, -1, -1):
        d = (today - _dt.timedelta(days=i)).strftime("%Y-%m-%d")
        async with db().execute(
            "SELECT hits, limit_per_day FROM proxy_daily_hits WHERE date=? AND url_key=?",
            (d, url_key)
        ) as cur:
            row = await cur.fetchone()
        hits = row["hits"] if row else 0
        limit = row["limit_per_day"] if row else saved_limit
        result.append({
            "date": d,
            "hits": hits,
            "limit": limit,
            "remaining": max(0, limit - hits),
            "percent_used": round(hits / limit * 100, 1) if limit > 0 else 0,
        })
    return result


# ── proxy pool ───────────────────────────────────────────────
async def list_proxies() -> list[dict]:
    async with db().execute("SELECT * FROM proxy_pool ORDER BY id") as cur:
        return [dict(r) for r in await cur.fetchall()]


async def add_proxy(name: str, url: str) -> int:
    cur = await db().execute(
        "INSERT INTO proxy_pool(name, url, enabled, is_active, created_at) VALUES(?,?,1,0,?)",
        (name, url, int(time.time())),
    )
    await db().commit()
    return cur.lastrowid


async def delete_proxy(proxy_id: int) -> None:
    await db().execute("DELETE FROM proxy_pool WHERE id=?", (proxy_id,))
    await db().commit()


async def set_proxy_active(proxy_id: int | None) -> None:
    """Đặt proxy active. proxy_id=None = dùng direct (không proxy)."""
    await db().execute("UPDATE proxy_pool SET is_active=0")
    if proxy_id is not None:
        await db().execute("UPDATE proxy_pool SET is_active=1 WHERE id=?", (proxy_id,))
    await db().commit()


async def get_active_proxy() -> dict | None:
    """Lấy proxy đang active. None = direct."""
    async with db().execute("SELECT * FROM proxy_pool WHERE is_active=1 AND enabled=1 LIMIT 1") as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def update_proxy(proxy_id: int, name: str | None = None, url: str | None = None, enabled: bool | None = None) -> None:
    if name is not None:
        await db().execute("UPDATE proxy_pool SET name=? WHERE id=?", (name, proxy_id))
    if url is not None:
        await db().execute("UPDATE proxy_pool SET url=? WHERE id=?", (url, proxy_id))
    if enabled is not None:
        await db().execute("UPDATE proxy_pool SET enabled=? WHERE id=?", (1 if enabled else 0, proxy_id))
    await db().commit()


async def set_proxy_limit(url_key: str, limit: int) -> None:
    """Đặt giới hạn request/ngày cho proxy key."""
    await set_setting(f"proxy_limit_{url_key}", limit)
    # cập nhật row hôm nay nếu đã có
    today = _today_utc7()
    await db().execute(
        "UPDATE proxy_daily_hits SET limit_per_day=? WHERE url_key=?",
        (limit, url_key),
    )
    await db().commit()
