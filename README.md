# Max-DeepSeek

Cổng API miễn phí tương thích OpenAI, dùng pool tài khoản DeepSeek web xoay vòng tự động. Self-hosted, giao diện quản trị tiếng Việt.

Thêm nhiều tài khoản DeepSeek → hệ thống tự đăng nhập, xoay vòng, failover khi một tài khoản bị giới hạn. Ứng dụng của bạn gọi vào qua chuẩn OpenAI (`/v1/chat/completions`) như dùng OpenAI thật.

## Tính năng

- Tương thích OpenAI: `/v1/models`, `/v1/chat/completions` (stream + non-stream)
- Pool tài khoản DeepSeek: tự đăng nhập, xoay vòng theo tải, tự khôi phục tài khoản lỗi
- Hỗ trợ chế độ suy luận (thinking) qua `reasoning_content`
- Quản lý API key cho ứng dụng bên ngoài
- Bảng điều khiển: thống kê, nhật ký yêu cầu, quản lý tài khoản và cấu hình
- Giao diện tiếng Việt, dark theme
- Triển khai một lệnh bằng Docker Compose

## Yêu cầu

- Docker + Docker Compose
- Tài khoản DeepSeek (email hoặc số điện thoại + mật khẩu) tại https://chat.deepseek.com

## Cài đặt

```bash
git clone https://github.com/manhvicky/Max-DeepSeek
cd Max-DeepSeek
docker compose -f docker/docker-compose.yml up -d
```

Mở trình duyệt: `http://localhost:22218/admin`

Lần đầu vào sẽ yêu cầu **đặt mật khẩu quản trị**.

## Sử dụng

1. Đăng nhập bảng điều khiển
2. Vào **Tài khoản DeepSeek** → thêm tài khoản (email/SĐT + mật khẩu). Hệ thống tự đăng nhập nền.
3. Vào **API Key** → tạo key (`sk-...`)
4. Gọi API:

```bash
curl http://localhost:22218/v1/chat/completions \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-default",
    "messages": [{"role": "user", "content": "Xin chào"}]
  }'
```

Dùng với OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:22218/v1",
    api_key="sk-your-key",
)
resp = client.chat.completions.create(
    model="deepseek-default",
    messages=[{"role": "user", "content": "Xin chào"}],
)
print(resp.choices[0].message.content)
```

## Mô hình

| Model | Mô tả |
|-------|-------|
| `deepseek-default` | Trò chuyện tiêu chuẩn |
| `deepseek-expert` | Suy luận sâu (thinking) |
| `deepseek-vision` | Đầu vào hình ảnh |

## Cấu hình

Biến môi trường (trong `docker/docker-compose.yml`):

- `DS_PROXY_URL` — proxy non-US. Nếu máy chủ đặt tại Mỹ, DeepSeek có thể chặn (WAF), cần proxy để khắc phục.

Dữ liệu (tài khoản, key, log) lưu trong `docker/data/` (SQLite). Mật khẩu tài khoản được mã hóa.

## Kiến trúc

- **Backend**: Python FastAPI — account pool, PoW solver (WASM), proxy OpenAI ↔ DeepSeek
- **Frontend**: React + Vite + TypeScript
- **Lưu trữ**: SQLite

## Phát triển

```bash
# Backend
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 22218

# Frontend
cd web
npm install && npm run dev
```

## Giấy phép

MIT
