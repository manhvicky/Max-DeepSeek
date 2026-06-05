#!/usr/bin/env python3
"""Basic smoke test for a running Max-DeepSeek server.

Usage:
  MAX_DEEPSEEK_URL=http://localhost:22218 python scripts/smoke_test.py
  MAX_DEEPSEEK_ADMIN_PASSWORD=... python scripts/smoke_test.py
  MAX_DEEPSEEK_API_KEY=sk-... python scripts/smoke_test.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = os.getenv("MAX_DEEPSEEK_URL", "http://localhost:22218").rstrip("/")
ADMIN_PASSWORD = os.getenv("MAX_DEEPSEEK_ADMIN_PASSWORD", "")
API_KEY = os.getenv("MAX_DEEPSEEK_API_KEY", "")


def request(method: str, path: str, body: dict[str, Any] | None = None, token: str = "", api_key: str = "") -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload


def assert_ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    status, health = request("GET", "/health")
    assert_ok(status == 200 and isinstance(health, dict) and health.get("status") == "ok", f"/health failed: {status} {health}")
    print("ok /health")

    if ADMIN_PASSWORD:
        status, login = request("POST", "/admin/api/login", {"password": ADMIN_PASSWORD})
        assert_ok(status == 200 and isinstance(login, dict) and bool(login.get("token")), f"admin login failed: {status} {login}")
        token = str(login["token"])
        print("ok admin login")

        status, stats = request("GET", "/admin/api/stats", token=token)
        assert_ok(status == 200 and isinstance(stats, dict), f"admin stats failed: {status} {stats}")
        print("ok admin stats")

    if API_KEY:
        status, models = request("GET", "/v1/models", api_key=API_KEY)
        assert_ok(status == 200 and isinstance(models, dict) and models.get("object") == "list", f"/v1/models failed: {status} {models}")
        print("ok /v1/models")

    print("smoke test passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
