"""DeepSeek HTTP client — gọi API web chat.

Dùng curl_cffi impersonate Chrome (BẮT BUỘC: DeepSeek check TLS fingerprint,
httpx/requests bị WAF chặn). Tầng này stateless: không cache, không retry.
"""
from __future__ import annotations

from typing import AsyncIterator, Optional

from curl_cffi.requests import AsyncSession

from app.core import config


class ClientError(Exception):
    def __init__(self, message: str, code: int | None = None, http_status: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


class DsClient:
    def __init__(self):
        pass  # api_base đọc động từ config
        self.wasm_url = config.WASM_URL
        kwargs = {"impersonate": config.IMPERSONATE, "timeout": 120}
        if config.PROXY_URL:
            kwargs["proxies"] = {"http": config.PROXY_URL, "https": config.PROXY_URL}
        self._session_kwargs = kwargs

    def _session(self) -> AsyncSession:
        return AsyncSession(**self._session_kwargs)

    def _auth_headers(self, token: str, pow_response: Optional[str] = None) -> dict:
        h = {
            "User-Agent": config.USER_AGENT,
            "Authorization": f"Bearer {token}",
            "X-Client-Version": config.CLIENT_VERSION,
            "X-Client-Platform": config.CLIENT_PLATFORM,
            "X-Client-Locale": config.CLIENT_LOCALE,
            "Content-Type": "application/json",
        }
        if pow_response:
            h["X-Ds-Pow-Response"] = pow_response
        return h

    @staticmethod
    def _check_envelope(data: dict) -> dict:
        """Bóc envelope {code,msg,data:{biz_code,biz_msg,biz_data}}."""
        code = data.get("code", 0)
        if code != 0:
            raise ClientError(data.get("msg", "lỗi"), code=code)
        inner = data.get("data") or {}
        biz_code = inner.get("biz_code", 0)
        if biz_code != 0:
            raise ClientError(inner.get("biz_msg", "biz error"), code=biz_code)
        return inner.get("biz_data") or {}

    async def login(self, email: str, mobile: str, area_code: str, password: str) -> str:
        """Đăng nhập, trả về token."""
        payload = {
            "password": password,
            "device_id": "",
            "os": "web",
        }
        if email:
            payload["email"] = email
        if mobile:
            payload["mobile"] = mobile
        if area_code:
            payload["area_code"] = area_code

        async with self._session() as s:
            r = await s.post(
                f"{config.API_BASE}/users/login",
                json=payload,
                headers={"User-Agent": config.USER_AGENT, "Content-Type": "application/json"},
            )
            if r.status_code == 202 and r.headers.get("x-amzn-waf-action"):
                raise ClientError("WAF Challenge: cần proxy non-US", http_status=202)
            if r.status_code != 200:
                raise ClientError(f"HTTP {r.status_code}: {r.text[:200]}", http_status=r.status_code)
            biz = self._check_envelope(r.json())
            user = biz.get("user") or {}
            token = user.get("token")
            if not token:
                raise ClientError("login không trả token")
            return token

    async def create_session(self, token: str) -> str:
        async with self._session() as s:
            r = await s.post(
                f"{config.API_BASE}/chat_session/create",
                json={},
                headers=self._auth_headers(token),
            )
            if r.status_code != 200:
                raise ClientError(f"create_session HTTP {r.status_code}", http_status=r.status_code)
            biz = self._check_envelope(r.json())
            return biz["chat_session"]["id"]

    async def delete_session(self, token: str, session_id: str) -> None:
        try:
            async with self._session() as s:
                await s.post(
                    f"{config.API_BASE}/chat_session/delete",
                    json={"chat_session_id": session_id},
                    headers=self._auth_headers(token),
                )
        except Exception:
            pass  # cleanup best-effort

    async def create_pow_challenge(self, token: str, target_path: str) -> dict:
        async with self._session() as s:
            r = await s.post(
                f"{config.API_BASE}/chat/create_pow_challenge",
                json={"target_path": target_path},
                headers=self._auth_headers(token),
            )
            if r.status_code != 200:
                raise ClientError(f"pow_challenge HTTP {r.status_code}", http_status=r.status_code)
            biz = self._check_envelope(r.json())
            return biz["challenge"]

    async def completion_stream(
        self, token: str, pow_response: str, payload: dict
    ) -> AsyncIterator[bytes]:
        """Mở SSE stream /chat/completion. Yield raw bytes."""
        async with self._session() as s:
            r = await s.post(
                f"{config.API_BASE}/chat/completion",
                json=payload,
                headers=self._auth_headers(token, pow_response),
                stream=True,
            )
            if r.status_code != 200:
                body = await r.atext() if hasattr(r, "atext") else r.text
                raise ClientError(f"completion HTTP {r.status_code}: {str(body)[:200]}",
                                  http_status=r.status_code)
            async for chunk in r.aiter_content():
                if chunk:
                    yield chunk

    async def stop_stream(self, token: str, session_id: str, message_id: int) -> None:
        try:
            async with self._session() as s:
                await s.post(
                    f"{config.API_BASE}/chat/stop_stream",
                    json={"chat_session_id": session_id, "message_id": message_id},
                    headers=self._auth_headers(token),
                )
        except Exception:
            pass

    async def get_wasm(self) -> bytes:
        async with self._session() as s:
            r = await s.get(self.wasm_url)
            if r.status_code != 200:
                raise ClientError(f"tải WASM HTTP {r.status_code}", http_status=r.status_code)
            return r.content
