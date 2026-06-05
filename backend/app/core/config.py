"""Cấu hình mặc định cho Max-DeepSeek."""
from __future__ import annotations

import os

# ── DeepSeek API ─────────────────────────────────────────────
API_BASE = os.getenv("DS_API_BASE", "https://chat.deepseek.com/api/v0")
WASM_URL = os.getenv(
    "DS_WASM_URL",
    "https://fe-static.deepseek.com/chat/static/sha3_wasm_bg.7b9ca65ddd.wasm",
)
USER_AGENT = os.getenv("DS_USER_AGENT", "DeepSeek/2.0.4 Android/35")
CLIENT_VERSION = os.getenv("DS_CLIENT_VERSION", "2.1.0")
CLIENT_PLATFORM = os.getenv("DS_CLIENT_PLATFORM", "android")
CLIENT_LOCALE = os.getenv("DS_CLIENT_LOCALE", "zh_CN")
PROXY_URL = os.getenv("DS_PROXY_URL", "") or None

# curl_cffi impersonate target (BẮT BUỘC — DeepSeek check TLS fingerprint)
IMPERSONATE = os.getenv("DS_IMPERSONATE", "chrome")

# ── Account pool ─────────────────────────────────────────────
MAX_ERROR_COUNT = 3          # error_count >= 3 → invalid (chỉ cho lỗi mạng/transient)
RECOVERY_INTERVAL = int(os.getenv("DS_RECOVERY_INTERVAL", "20"))       # giây — recovery task quét account error/cooling
ACQUIRE_TIMEOUT_MS = int(os.getenv("DS_ACQUIRE_TIMEOUT_MS", "10000"))  # chờ account idle tối đa
ACQUIRE_POLL_MS = 200
MIN_ACCOUNT_INTERVAL_MS = int(os.getenv("DS_MIN_ACCOUNT_INTERVAL_MS", "45000"))  # giãn cách tối thiểu giữa 2 request/account
MAX_ATTEMPTS = int(os.getenv("DS_MAX_ATTEMPTS", "2"))             # retry sang account khác
RETRY_BACKOFF_MS = 500
INIT_CONCURRENCY = int(os.getenv("DS_INIT_CONCURRENCY", "2"))  # tránh login dồn dập làm DeepSeek mute

# Cooldown khi account bị DeepSeek mute / rate-limit (KHÔNG đánh chết, tự hồi)
COOLDOWN_BASE = 600          # giây — nghỉ tạm lần đầu (10 phút)
COOLDOWN_MAX = 6 * 3600      # trần cooldown (6 giờ); backoff ×2 mỗi lần lặp lại
AUTO_DISABLE_AFTER_STRIKES = int(os.getenv("DS_AUTO_DISABLE_AFTER_STRIKES", "6"))
WARM_SPARE_MIN_IDLE = int(os.getenv("DS_WARM_SPARE_MIN_IDLE", "2"))
WARM_SPARE_RELOGIN_BATCH = int(os.getenv("DS_WARM_SPARE_RELOGIN_BATCH", "2"))
RESERVE_IDLE_MIN = int(os.getenv("DS_RESERVE_IDLE_MIN", "1"))

# ── Models ───────────────────────────────────────────────────
MODEL_TYPES = ["default", "expert", "vision"]
INPUT_CHAR_LIMITS = {"default": 2_621_440, "expert": 163_840, "vision": 2_621_440}
DEFAULT_MODEL = "deepseek-default"

# DS Free API-compatible configuration values exposed in MaxDeepSeek admin.
MAX_INPUT_TOKENS = {"default": 1_048_576, "expert": 1_048_576, "vision": 1_048_576}
MAX_OUTPUT_TOKENS = {"default": 384_000, "expert": 384_000, "vision": 384_000}
MODEL_ALIASES: dict[str, str] = {}
TOOL_CALL_EXTRA_STARTS = ["<|tool_call_begin|>", "<tool_calls>", "<tool_call>"]
TOOL_CALL_EXTRA_ENDS = ["<|tool_call_end|>", "</tool_calls>", "</tool_call>"]
def _csv_env(name: str, default: str) -> list[str]:
    values = [x.strip() for x in os.getenv(name, default).split(",")]
    return [x for x in values if x]

CORS_ORIGINS = _csv_env("CORS_ORIGINS", os.getenv("CORS_ORIGIN", "http://localhost:22218"))
ADMIN_JWT_EXPIRE_SECONDS = int(os.getenv("ADMIN_JWT_EXPIRE_SECONDS", "86400"))

# ── Server ───────────────────────────────────────────────────
PORT = int(os.getenv("PORT", "22218"))
HOST = os.getenv("HOST", "0.0.0.0")
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "max-deepseek.db")
WASM_CACHE = os.path.join(DATA_DIR, "pow.wasm")

# Healthcheck prompt khi admin chủ động test account.
# Mặc định KHÔNG chat-test khi startup/recovery để tránh tự làm account bị mute/rate-limit.
HEALTHCHECK_ON_LOGIN = os.getenv("DS_HEALTHCHECK_ON_LOGIN", "0").lower() in ("1", "true", "yes")
HEALTHCHECK_PROMPT = "只回复`Hello, world!`"



APP_NAME = "Max-DeepSeek"
APP_VERSION = os.getenv("MAX_DEEPSEEK_VERSION", "1.0.0")
APP_REPOSITORY = os.getenv("MAX_DEEPSEEK_REPOSITORY", "https://github.com/manhvicky/Max-DeepSeek")
APP_AUTHOR_NAME = os.getenv("MAX_DEEPSEEK_AUTHOR_NAME", "Vu Duy Manh")
APP_AUTHOR_EMAIL = os.getenv("MAX_DEEPSEEK_AUTHOR_EMAIL", "manhq7@gmail.com")
UPDATE_CHANNEL = os.getenv("MAX_DEEPSEEK_UPDATE_CHANNEL", "stable")
UPDATE_MANIFEST_URL = os.getenv("MAX_DEEPSEEK_UPDATE_MANIFEST_URL", "")
UPDATE_COMMAND = os.getenv("MAX_DEEPSEEK_UPDATE_COMMAND", "bash /app/scripts/update.sh")
ROLLBACK_COMMAND = os.getenv("MAX_DEEPSEEK_ROLLBACK_COMMAND", "bash /app/scripts/rollback.sh")
ALLOW_SELF_UPDATE = os.getenv("MAX_DEEPSEEK_ALLOW_SELF_UPDATE", "0").strip().lower() in {"1", "true", "yes", "on"}
UPDATE_CHECK_TIMEOUT = float(os.getenv("MAX_DEEPSEEK_UPDATE_CHECK_TIMEOUT", "6"))
