#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = os.getenv("MAX_DEEPSEEK_URL", "http://localhost:22218").rstrip("/")
ADMIN_PASSWORD = os.getenv("MAX_DEEPSEEK_ADMIN_PASSWORD", "admin123")
EXPECT_FRESH_SETUP = os.getenv("MAX_DEEPSEEK_EXPECT_FRESH_SETUP", "0") == "1"


def request(method: str, path: str, body: dict[str, Any] | None = None, token: str = "", api_key: str = "") -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def get_admin_token() -> str:
    if EXPECT_FRESH_SETUP:
        status, payload = request("POST", "/admin/api/setup", {"password": ADMIN_PASSWORD})
        ensure(status == 200 and isinstance(payload, dict) and bool(payload.get("token")), f"setup failed: {status} {payload}")
        return str(payload["token"])

    status, payload = request("POST", "/admin/api/login", {"password": ADMIN_PASSWORD})
    if status == 403:
        status, payload = request("POST", "/admin/api/setup", {"password": ADMIN_PASSWORD})
    ensure(status == 200 and isinstance(payload, dict) and bool(payload.get("token")), f"admin auth failed: {status} {payload}")
    return str(payload["token"])


def main() -> int:
    status, health = request("GET", "/health")
    ensure(status == 200 and isinstance(health, dict) and health.get("status") == "ok", f"/health failed: {status} {health}")
    print("ok /health")

    token = get_admin_token()
    print("ok admin auth")

    status, stats = request("GET", "/admin/api/stats", token=token)
    ensure(status == 200 and isinstance(stats, dict), f"/admin/api/stats failed: {status} {stats}")
    print("ok /admin/api/stats")

    status, created = request("POST", "/admin/api/keys", {"description": "test-api"}, token=token)
    ensure(status == 200 and isinstance(created, dict) and bool(created.get("key")), f"create key failed: {status} {created}")
    key_id = int(created["id"])
    api_key = str(created["key"])
    print("ok create api key")

    status, keys = request("GET", "/admin/api/keys", token=token)
    ensure(status == 200 and isinstance(keys, list) and any(isinstance(row, dict) and int(row["id"]) == key_id for row in keys), f"list keys failed: {status} {keys}")
    print("ok list api keys")

    status, models = request("GET", "/v1/models", api_key=api_key)
    ensure(status == 200 and isinstance(models, dict) and models.get("object") == "list", f"/v1/models failed: {status} {models}")
    print("ok /v1/models")

    status, unauthorized = request("GET", "/v1/models")
    ensure(status == 401, f"/v1/models without key should be 401, got: {status} {unauthorized}")
    print("ok /v1/models unauthorized")

    status, missing_messages = request(
        "POST",
        "/v1/chat/completions",
        {"model": "deepseek-default"},
        api_key=api_key,
    )
    ensure(status == 400 and isinstance(missing_messages, dict), f"chat validation failed: {status} {missing_messages}")
    print("ok /v1/chat/completions validation")

    status, deleted = request("DELETE", f"/admin/api/keys/{key_id}", token=token)
    ensure(status == 200 and isinstance(deleted, dict) and deleted.get("ok") is True, f"delete key failed: {status} {deleted}")
    print("ok delete api key")

    status, invalid_after_delete = request("GET", "/v1/models", api_key=api_key)
    ensure(status == 401, f"deleted key should be invalid, got: {status} {invalid_after_delete}")
    print("ok deleted key invalidation")

    print("basic API tests passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"basic API tests failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
