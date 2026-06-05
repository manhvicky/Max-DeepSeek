# Basic API tests for Max-DeepSeek

These tests cover the public/admin HTTP surface without needing a real DeepSeek account.

## What is covered

- `/health`
- admin login and protected endpoint access
- API key creation/list/delete
- `/v1/models` with a valid key
- `/v1/chat/completions` auth and validation errors

## Run

Start the app first, then run:

```bash
python3 tests/test_api.py
```

Optional env vars:

- `MAX_DEEPSEEK_URL` default `http://localhost:22218`
- `MAX_DEEPSEEK_ADMIN_PASSWORD` default `admin123`
- `MAX_DEEPSEEK_EXPECT_FRESH_SETUP` set `1` if you expect first-run setup flow
