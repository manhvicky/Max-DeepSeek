# Max-DeepSeek — Đặc tả kỹ thuật

API gateway tương thích OpenAI, dùng pool tài khoản DeepSeek web (miễn phí) xoay vòng.
Self-hosted, viết bằng Python (FastAPI). Giao diện admin tiếng Việt.

## 1. Tổng quan kiến trúc

```
Client (OpenAI SDK / Cursor / Cherry Studio)
        │  Authorization: Bearer sk-...
        ▼
FastAPI  ──  /v1/chat/completions, /v1/models     (OpenAI-compatible)
        ├──  /admin/api/*                           (admin panel API)
        └──  /admin (static React UI)
        │
        ▼
AccountPool  ── chọn account idle (longest-idle), failover, recovery
        │
        ▼
DeepSeekClient (curl_cffi impersonate Chrome)
        ├── login → token
        ├── create_pow_challenge → PoW solve (wasmtime)
        ├── /chat/completion (SSE stream)
        └── convert SSE patch → OpenAI chunks
```

## 2. Stack

- **Backend:** FastAPI + uvicorn
- **HTTP client:** `curl_cffi` (impersonate="chrome", BẮT BUỘC vì DeepSeek dùng TLS fingerprint check; httpx/requests bị chặn)
- **PoW:** `wasmtime` (chạy WASM DeepSeekHashV1)
- **Token đếm:** `tiktoken` (cl100k_base)
- **DB:** SQLite (`aiosqlite`)
- **Auth admin:** JWT (PyJWT) + bcrypt password hash
- **Frontend:** React + Vite + TS (dark theme tiếng Việt)

## 3. DeepSeek API (đã reverse-engineer)

Base: `https://chat.deepseek.com/api/v0`

Headers chung:
- `User-Agent: DeepSeek/2.1.1 Android/35`
- `Authorization: Bearer <token>`
- `X-Client-Version: 2.0.0`
- `X-Client-Platform: android`
- `X-Client-Locale: zh_CN`
- PoW endpoints thêm: `X-Ds-Pow-Response: <base64>`

Envelope: `{code, msg, data:{biz_code, biz_msg, biz_data}}`. code/biz_code != 0 = lỗi.
- code 1001|1201 → Overloaded
- code 40301 → INVALID_POW

Endpoints:
- `POST /users/login` body `{email?, mobile?, password, area_code?, device_id:"", os:"web"}` → `data.user.token`
- `POST /chat_session/create` `{}` → `biz_data.chat_session.id`
- `POST /chat_session/delete` `{chat_session_id}`
- `POST /chat/create_pow_challenge` `{target_path}` → `biz_data.challenge`
- `POST /chat/completion` (PoW) → SSE stream
- `POST /chat/stop_stream` `{chat_session_id, message_id}` (không PoW)

### PoW DeepSeekHashV1
1. POST create_pow_challenge `{target_path:"/api/v0/chat/completion"}` → `{algorithm, challenge, salt, signature, difficulty, expire_at, target_path}`
2. WASM: tải từ `wasm_url`. prefix = `f"{salt}_{expire_at}_"`. Gọi `wasm_solve(retptr, challenge_ptr, challenge_len, prefix_ptr, prefix_len, difficulty:f64)`. Đọc retptr: status @ offset 0 (i32), answer @ offset 8 (f64). status==0 → fail.
   - Exports: `__wbindgen_add_to_stack_pointer(i32)->i32`, `__wbindgen_malloc(i32,i32)->i32`, `wasm_solve(...)->()`
   - write_string: ptr=alloc(len,1); memory.write(ptr, bytes)
   - retptr = add_to_stack(-16)
3. Header = base64(json `{algorithm, challenge, salt, answer:int, signature, target_path}`)

## 4. Account Pool

States: `idle(0)`, `busy(1)`, `error(2)`, `invalid(3)`. 1 account = 1 concurrency.
- Chọn: longest-idle (account idle có last_released cũ nhất; chưa dùng = ưu tiên nhất). CAS idle→busy.
- Guard release busy→idle khi stream xong, set last_released=now.
- mark_error: busy→error. Recovery task mỗi 60s re-login account error.
- error_count >= 3 (MAX_ERROR_COUNT) → invalid (cần admin).
- Request retry: MAX_ATTEMPTS=3, backoff 500ms. get_account_with_wait timeout 30s, poll 200ms.
- Health check lúc init/re-login: gửi completion test "只回复`Hello, world!`", model default. Phát hiện biz_code → invalid.

## 5. Request convert (OpenAI → DeepSeek)

CompletionPayload:
```json
{"chat_session_id","parent_message_id":null,"model_type":"default",
 "prompt":"<gộp 1 string>","ref_file_ids":[],"thinking_enabled":true,
 "search_enabled":true,"preempt":false}
```

Prompt build — tag native (ký tự fullwidth `｜`=U+FF5C, `▁`=U+2581):
- system → `<｜System｜>content`
- user → `<｜end▁of▁sentence｜><｜User｜>content`
- assistant → `<｜Assistant｜>content`
- Cuối luôn đảm bảo có `<｜Assistant｜>` (nếu chưa thì thêm `<｜Assistant｜>\n`)

Model mapping: `deepseek-{type}` → model_type. default/expert/vision.
Thinking: `reasoning_effort=="none"` → false, else true. (mặc định "high" → true)
Search: mặc định true.

## 6. Response convert (DeepSeek → OpenAI)

SSE patch protocol `{p,o,v}`:
- p=path (persist), o=op (APPEND/BATCH/SET, persist), v=value
- event ready → response_message_id (cho stop_stream)
- event close → kết thúc
- Initial: v.response = {status, accumulated_token_usage, fragments:[{type:THINK|RESPONSE, content}]}
- path `response/fragments/-1/content` APPEND → content fragment cuối (THINK→reasoning_content, RESPONSE→content)
- path `response/fragments` APPEND → push fragment mới
- path `response/status` == FINISHED → finish_reason "stop"
- path `response/accumulated_token_usage` → completion_tokens

Token: prompt_tokens = tiktoken cl100k_base trên prompt build. completion_tokens = accumulated_token_usage. Stream phải inject stream_options include_usage để lấy usage.

## 7. Cấu trúc DB (SQLite)

- `accounts(id, email, mobile, area_code, password_enc, label, state, error_count, last_error, created_at)`
- `api_keys(id, key, description, is_active, created_at)`
- `request_logs(id, ts, model, api_key_masked, prompt_tokens, completion_tokens, latency_ms, success, error)`
- `settings(key, value)` — admin password_hash, jwt_secret, config json

## 8. Cổng & Deploy

- Port mặc định: 22218
- Admin UI: `http://localhost:22218/admin`
- API: `http://localhost:22218/v1`
- Docker Compose, volume `./data` (sqlite + config), `./wasm` cache.
