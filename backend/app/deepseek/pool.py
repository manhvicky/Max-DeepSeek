"""Account Pool — quản lý pool tài khoản DeepSeek, xoay vòng, failover.

1 account = 1 concurrency. State: idle/busy/error/invalid.
Chọn account longest-idle. Recovery task re-login account error mỗi 60s.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

from app.core import config
from app.deepseek.client import ClientError, DsClient
from app.deepseek.pow import Challenge, PowSolver


class State(IntEnum):
    IDLE = 0
    BUSY = 1
    ERROR = 2
    INVALID = 3
    COOLING = 4   # bị DeepSeek mute/rate-limit — nghỉ tạm, tự hồi khi hết cooldown


# Dấu hiệu account bị mute/rate-limit (lỗi TẠM THỜI, KHÔNG đánh chết).
# DeepSeek trả "user is muted" hoặc biz_code rate-limit khi 1 account bị dùng
# quá tải / nhiều session song song. Account vẫn sống, chỉ cần nghỉ rồi dùng lại.
_COOLDOWN_HINTS = (
    "muted",
    "rate_limit",
    "rate limit",
    "too many",
    "limited",
    "biz_code bất thường",
    "overloaded",
)

# Dấu hiệu credential sai → account hỏng thật, đánh INVALID luôn, không retry.
_FATAL_HINTS = (
    "wrong password",
    "incorrect password",
    "password",
    "account not exist",
    "user not exist",
    "invalid email",
    "invalid mobile",
)


def _classify_error(msg: str) -> str:
    """Phân loại lỗi: 'cooldown' (mute/limit, tự hồi) / 'fatal' (sai pass) / 'transient'."""
    low = (msg or "").lower()
    for h in _FATAL_HINTS:
        if h in low:
            return "fatal"
    for h in _COOLDOWN_HINTS:
        if h in low:
            return "cooldown"
    return "transient"


@dataclass
class Account:
    id: int
    email: str
    mobile: str
    area_code: str
    password: str
    label: str
    token: str = ""
    state: State = State.IDLE
    error_count: int = 0
    last_error: str = ""
    last_released: float = 0.0  # monotonic ms
    cooldown_until: float = 0.0  # epoch giây — hết hạn nghỉ tạm (COOLING)
    cooldown_strikes: int = 0    # số lần mute liên tiếp → backoff tăng dần
    enabled: bool = True         # công tắc admin — tắt thì pool KHÔNG dùng account này
    quarantine_until: float = 0.0  # epoch giây — quarantine account mute nặng

    @property
    def display_id(self) -> str:
        return self.email or self.mobile or f"#{self.id}"

    @property
    def cooldown_remaining(self) -> int:
        """Giây còn lại của cooldown (0 nếu đã hết)."""
        if self.state != State.COOLING:
            return 0
        return max(0, int(self.cooldown_until - time.time()))

    @property
    def quarantine_remaining(self) -> int:
        return max(0, int(self.quarantine_until - time.time()))

    @property
    def is_quarantined(self) -> bool:
        return self.quarantine_until > time.time()


def _now_ms() -> float:
    return time.monotonic() * 1000.0


def _daily_mute_delay() -> int:
    """Seconds until shortly after next local midnight for DeepSeek daily mute."""
    now = time.time()
    lt = time.localtime(now)
    next_day = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, 0, 15, 0, 0, 0, -1))
    return max(config.COOLDOWN_BASE, int(next_day - now))


def _is_daily_mute(msg: str) -> bool:
    low = (msg or "").lower()
    return "user is muted" in low or "muted" in low


class AccountPool:
    def __init__(self, client: DsClient, solver: PowSolver, on_state_change=None):
        self.client = client
        self.solver = solver
        self._accounts: dict[int, Account] = {}
        self._lock = asyncio.Lock()
        self._recovery_task: Optional[asyncio.Task] = None
        self._relogin_tasks: dict[int, asyncio.Task] = {}
        self._recovery_sem = asyncio.Semaphore(max(1, config.INIT_CONCURRENCY))
        self._on_state_change = on_state_change  # callback(account) để persist DB
        self._rr_cursor = 0  # round-robin cursor để xoay đều tài khoản

    # ── quản lý account ──────────────────────────────────────
    def add(self, account: Account) -> None:
        self._accounts[account.id] = account

    def remove(self, account_id: int) -> None:
        self._accounts.pop(account_id, None)

    def get(self, account_id: int) -> Optional[Account]:
        return self._accounts.get(account_id)

    def all(self) -> list[Account]:
        return list(self._accounts.values())

    def summary(self) -> dict:
        counts = {"total": len(self._accounts), "idle": 0, "busy": 0,
                  "error": 0, "invalid": 0, "cooling": 0, "enabled": 0,
                  "disabled": 0, "quarantined": 0, "auto_disabled": 0,
                  "next_ready_in": 0}
        cooling_left = []
        for a in self._accounts.values():
            counts[a.state.name.lower()] = counts.get(a.state.name.lower(), 0) + 1
            if a.enabled:
                counts["enabled"] += 1
            else:
                counts["disabled"] += 1
                if "auto-disabled" in (a.last_error or ""):
                    counts["auto_disabled"] += 1
            if a.is_quarantined:
                counts["quarantined"] += 1
                cooling_left.append(a.quarantine_remaining)
            elif a.state == State.COOLING:
                rem = a.cooldown_remaining
                if rem > 0:
                    cooling_left.append(rem)
        positive = [x for x in cooling_left if x > 0]
        if positive:
            counts["next_ready_in"] = min(positive)
        return counts

    async def _set_state(self, acc: Account, state: State,
                         error_count: int | None = None, last_error: str = "") -> None:
        acc.state = state
        if error_count is not None:
            acc.error_count = error_count
        acc.last_error = last_error
        if state == State.IDLE:
            acc.cooldown_until = 0.0
            acc.cooldown_strikes = 0
            acc.quarantine_until = 0.0
        elif state != State.COOLING:
            acc.cooldown_until = 0.0
        if self._on_state_change:
            await self._on_state_change(acc)

    async def _enter_cooldown(self, acc: Account, msg: str) -> None:
        """Đưa account vào nghỉ tạm (COOLING) với backoff tăng dần.

        Account bị mute lặp lại nhiều lần sẽ bị quarantine dài hơn để pool
        ưu tiên account sạch, tránh đập request liên tục vào account gần chết.
        """
        if _is_daily_mute(msg):
            delay = _daily_mute_delay()
            acc.cooldown_strikes = max(acc.cooldown_strikes, 3)
        else:
            acc.cooldown_strikes = min(acc.cooldown_strikes + 1, 16)
            delay = min(config.COOLDOWN_BASE * (2 ** (acc.cooldown_strikes - 1)),
                        config.COOLDOWN_MAX)
        acc.cooldown_until = time.time() + delay
        if acc.cooldown_strikes >= 3 or _is_daily_mute(msg):
            acc.quarantine_until = max(acc.quarantine_until, acc.cooldown_until)
        if acc.cooldown_strikes >= config.AUTO_DISABLE_AFTER_STRIKES:
            acc.enabled = False
            note = f"auto-disabled after repeated mute/limit: {msg}"[:200]
            await self._set_state(acc, State.COOLING, last_error=note)
            return
        note = f"mute/limit: {msg}"[:200]
        await self._set_state(acc, State.COOLING, last_error=note)

    # ── chọn account (longest-idle) ──────────────────────────
    async def acquire(self, wait: bool = True) -> Optional[Account]:
        deadline = _now_ms() + config.ACQUIRE_TIMEOUT_MS
        while True:
            async with self._lock:
                candidates = [
                    a for a in sorted(
                        self._accounts.values(),
                        key=lambda x: (x.is_quarantined, x.cooldown_strikes, x.id),
                    )
                    if a.state == State.IDLE and a.enabled and not a.is_quarantined
                ]
                enabled_ready = [a for a in self._accounts.values() if a.enabled and not a.is_quarantined]
                reserve = min(config.RESERVE_IDLE_MIN, max(0, len(enabled_ready) - 1))
                if len(candidates) > reserve:
                    idx = self._rr_cursor % len(candidates)
                    best = candidates[idx]
                    self._rr_cursor = (idx + 1) % len(candidates)
                    best.state = State.BUSY
                    return best
            await self._nudge_recovery()
            if not wait or _now_ms() >= deadline:
                return None
            await asyncio.sleep(config.ACQUIRE_POLL_MS / 1000.0)

    async def release(self, acc: Account) -> None:
        should_persist = False
        async with self._lock:
            if acc.state == State.BUSY:
                acc.state = State.IDLE
                acc.last_released = _now_ms()
                acc.cooldown_until = 0.0
                acc.cooldown_strikes = 0
                acc.quarantine_until = 0.0
                should_persist = True
        if should_persist and self._on_state_change:
            await self._on_state_change(acc)

    async def mark_error(self, acc: Account, msg: str = "") -> None:
        async with self._lock:
            if acc.state != State.BUSY:
                return
            kind = _classify_error(msg)
            if kind == "cooldown":
                # mute/rate-limit → nghỉ tạm, KHÔNG phạt error_count, KHÔNG đánh chết
                await self._enter_cooldown(acc, msg)
            elif kind == "fatal":
                await self._set_state(acc, State.INVALID,
                                      error_count=config.MAX_ERROR_COUNT, last_error=msg)
            else:
                await self._set_state(acc, State.ERROR, last_error=msg)

    # ── login + health check ─────────────────────────────────
    async def init_account(self, acc: Account) -> None:
        """Login + health check 1 account. Thành công → idle.

        Thất bại: mute/limit → cooling (tự hồi), sai pass → invalid, còn lại → error.
        """
        try:
            token = await self.client.login(
                acc.email, acc.mobile, acc.area_code, acc.password
            )
            acc.token = token
            if config.HEALTHCHECK_ON_LOGIN:
                await self._health_check(acc)
            await self._set_state(acc, State.IDLE, error_count=0, last_error="")
        except Exception as e:  # noqa: BLE001
            await self._handle_login_failure(acc, str(e))

    async def _handle_login_failure(self, acc: Account, msg: str) -> None:
        """Login/health-check thất bại → phân loại để quyết định state.

        mute/limit → COOLING (tự hồi, không tính error_count).
        sai pass → INVALID ngay.
        lỗi mạng transient → error_count++, ≥ MAX thì INVALID.
        """
        kind = _classify_error(msg)
        if kind == "cooldown":
            await self._enter_cooldown(acc, msg)
        elif kind == "fatal":
            await self._set_state(acc, State.INVALID,
                                  error_count=config.MAX_ERROR_COUNT, last_error=msg)
        else:
            new_count = acc.error_count + 1
            if new_count >= config.MAX_ERROR_COUNT:
                await self._set_state(acc, State.INVALID,
                                      error_count=new_count, last_error=msg)
            else:
                await self._set_state(acc, State.ERROR,
                                      error_count=new_count, last_error=msg)

    async def _health_check(self, acc: Account) -> None:
        """Gửi completion test thật để xác nhận account sống."""
        session_id = await self.client.create_session(acc.token)
        try:
            pow_resp = await self._compute_pow(acc.token)
            payload = {
                "chat_session_id": session_id,
                "parent_message_id": None,
                "model_type": "default",
                "prompt": config.HEALTHCHECK_PROMPT,
                "ref_file_ids": [],
                "thinking_enabled": False,
                "search_enabled": False,
                "preempt": False,
            }
            text = b""
            async for chunk in self.client.completion_stream(acc.token, pow_resp, payload):
                text += chunk
                if len(text) > 8192:
                    break
            decoded = text.decode("utf-8", errors="ignore")
            if '"biz_code":' in decoded and '"biz_code": 0' not in decoded and '"biz_code":0' not in decoded:
                raise ClientError("health check: biz_code bất thường")
        finally:
            await self.client.delete_session(acc.token, session_id)

    async def _compute_pow(self, token: str) -> str:
        ch_data = await self.client.create_pow_challenge(token, "/api/v0/chat/completion")
        ch = Challenge.from_json(ch_data)
        return await asyncio.to_thread(self.solver.solve, ch)

    async def init_all(self, accounts: list[Account]) -> None:
        """Login song song nhiều account (semaphore giới hạn)."""
        sem = asyncio.Semaphore(config.INIT_CONCURRENCY)

        async def _one(a: Account):
            self.add(a)
            if not a.enabled:
                return  # account tắt → không login lúc khởi động
            if a.state == State.COOLING and a.cooldown_until > time.time():
                return  # giữ trạng thái bị khóa tới khi hết cooldown, tránh báo Sẵn sàng sai
            async with sem:
                await self.init_account(a)

        await asyncio.gather(*[_one(a) for a in accounts], return_exceptions=True)

    # ── recovery task ────────────────────────────────────────
    def start_recovery(self) -> None:
        if self._recovery_task is None:
            self._recovery_task = asyncio.create_task(self._recovery_loop())

    def stop_recovery(self) -> None:
        if self._recovery_task:
            self._recovery_task.cancel()
            self._recovery_task = None

    async def _recovery_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(config.RECOVERY_INTERVAL)
                now = time.time()
                for acc in list(self._accounts.values()):
                    if not acc.enabled:
                        continue  # account tắt → không tự login lại
                    if acc.is_quarantined and now < acc.quarantine_until:
                        continue
                    if acc.state == State.ERROR:
                        self._schedule_relogin(acc)
                    elif acc.state == State.COOLING and now >= acc.cooldown_until:
                        self._schedule_relogin(acc)
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001
                continue

    async def _nudge_recovery(self) -> None:
        # Opportunistically wake accounts when requests are waiting.
        now = time.time()
        for acc in list(self._accounts.values()):
            if not acc.enabled:
                continue
            if acc.is_quarantined and now < acc.quarantine_until:
                continue
            if acc.is_quarantined and now >= acc.quarantine_until:
                acc.quarantine_until = 0.0
            if acc.state == State.ERROR:
                self._schedule_relogin(acc)
            elif acc.state == State.INVALID and not acc.last_error:
                self._schedule_relogin(acc)
            elif acc.state == State.COOLING and now >= acc.cooldown_until:
                self._schedule_relogin(acc)

    def _schedule_relogin(self, acc: Account) -> None:
        task = self._relogin_tasks.get(acc.id)
        if task and not task.done():
            return
        self._relogin_tasks[acc.id] = asyncio.create_task(self._relogin_guarded(acc))

    async def _relogin_guarded(self, acc: Account) -> None:
        try:
            async with self._recovery_sem:
                await self._relogin(acc)
        finally:
            self._relogin_tasks.pop(acc.id, None)

    async def _relogin(self, acc: Account) -> None:
        try:
            token = await self.client.login(
                acc.email, acc.mobile, acc.area_code, acc.password
            )
            acc.token = token
            if config.HEALTHCHECK_ON_LOGIN:
                await self._health_check(acc)
            await self._set_state(acc, State.IDLE, error_count=0, last_error="")
        except Exception as e:  # noqa: BLE001
            await self._handle_login_failure(acc, str(e))

    async def relogin_single(self, account_id: int) -> bool:
        """Admin gọi thủ công — cứu account error/invalid/cooling."""
        acc = self.get(account_id)
        if not acc:
            return False
        # admin chủ động → cho account cơ hội sạch (reset backoff)
        acc.cooldown_strikes = 0
        acc.cooldown_until = 0.0
        acc.quarantine_until = 0.0
        self._schedule_relogin(acc)
        task = self._relogin_tasks.get(acc.id)
        if task:
            await task
        return acc.state == State.IDLE

    async def set_enabled(self, account_id: int, enabled: bool) -> bool:
        """Bật/tắt account. Tắt → pool không chọn, recovery bỏ qua.

        Bật lại account đang lỗi/cooling → thử login lại ngay cho nhanh.
        """
        acc = self.get(account_id)
        if not acc:
            return False
        acc.enabled = enabled
        if enabled and acc.state in (State.ERROR, State.INVALID, State.COOLING):
            acc.cooldown_strikes = 0
            acc.cooldown_until = 0.0
            acc.quarantine_until = 0.0
            self._schedule_relogin(acc)
        elif not enabled:
            acc.quarantine_until = max(acc.quarantine_until, time.time() + config.COOLDOWN_BASE)
        return True

    async def test_account(self, account_id: int) -> dict:
        """Admin bấm nút Kiểm tra — gửi 1 câu chat thật qua đúng account này.

        Trả về {ok, latency_ms, reply, error}. Không đổi error_count của account
        (chỉ kiểm tra, không phạt). Nếu account đang bận thì báo lại.
        """
        acc = self.get(account_id)
        if not acc:
            return {"ok": False, "error": "Không tìm thấy tài khoản"}

        # giữ chỗ để pool không chọn account này trong lúc test
        async with self._lock:
            if acc.state == State.BUSY:
                return {"ok": False, "error": "Tài khoản đang bận, thử lại sau"}
            acc.state = State.BUSY

        t0 = time.monotonic()
        try:
            # đảm bảo có token (account invalid/chưa login → login lại)
            if not acc.token:
                acc.token = await self.client.login(
                    acc.email, acc.mobile, acc.area_code, acc.password
                )
            reply = await self._probe(acc)
            latency = int((time.monotonic() - t0) * 1000)
            # test OK → đưa về idle, xóa lỗi + reset cooldown
            async with self._lock:
                acc.cooldown_strikes = 0
                acc.cooldown_until = 0.0
                await self._set_state(acc, State.IDLE, error_count=0, last_error="")
                acc.last_released = _now_ms()
            return {"ok": True, "latency_ms": latency, "reply": reply}
        except Exception as e:  # noqa: BLE001
            # thử login lại 1 lần nếu token hết hạn
            try:
                acc.token = await self.client.login(
                    acc.email, acc.mobile, acc.area_code, acc.password
                )
                reply = await self._probe(acc)
                latency = int((time.monotonic() - t0) * 1000)
                async with self._lock:
                    acc.cooldown_strikes = 0
                    acc.cooldown_until = 0.0
                    await self._set_state(acc, State.IDLE, error_count=0, last_error="")
                    acc.last_released = _now_ms()
                return {"ok": True, "latency_ms": latency, "reply": reply}
            except Exception as e2:  # noqa: BLE001
                msg = str(e2) or str(e)
                acc.state = State.BUSY  # đảm bảo mark_error xử lý đúng
                await self.mark_error(acc, msg)
                return {"ok": False, "error": msg}

    async def _probe(self, acc: Account) -> str:
        """Gửi prompt test, trả về nội dung phản hồi (cắt ngắn)."""
        session_id = await self.client.create_session(acc.token)
        try:
            pow_resp = await self._compute_pow(acc.token)
            payload = {
                "chat_session_id": session_id,
                "parent_message_id": None,
                "model_type": "default",
                "prompt": config.HEALTHCHECK_PROMPT,
                "ref_file_ids": [],
                "thinking_enabled": False,
                "search_enabled": False,
                "preempt": False,
            }
            from app.deepseek import sse
            content = ""
            async for ev in sse.parse_sse(
                self.client.completion_stream(acc.token, pow_resp, payload)
            ):
                if isinstance(ev, sse.ContentDelta):
                    content += ev.content
                elif isinstance(ev, sse.ErrorEvent):
                    raise ClientError(ev.message)
            return content.strip()[:200] or "(rỗng)"
        finally:
            await self.client.delete_session(acc.token, session_id)
