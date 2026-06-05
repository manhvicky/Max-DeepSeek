# Max-DeepSeek

Max-DeepSeek la cong API self-hosted tuong thich OpenAI, dung pool tai khoan DeepSeek web de xoay vong, failover va quan tri bang dashboard tieng Viet.

> Muc dich chinh: tu host cho ca nhan/nhom nho. Truoc khi public instance cho nguoi khac dung, hay tu kiem tra dieu khoan dich vu cua DeepSeek va chinh sach cua ben proxy/upstream ban dang su dung.

## Tinh nang

- Tuong thich OpenAI: `/v1/models`, `/v1/chat/completions`, ho tro stream va non-stream
- Pool tai khoan DeepSeek: login nen, xoay vong theo tai, cooldown/recovery khi account bi gioi han
- Hien thi thong ke request, token, do tre, log va tinh trang account
- Quan ly API key, proxy/API base va usage proxy theo ngay
- Dashboard React/Vite tieng Viet, phu hop van hanh self-hosted
- Trien khai nhanh bang Docker Compose

## Kien truc nhanh

- `backend/`: FastAPI gateway, account pool, PoW solver, OpenAI-compatible API
- `web/`: React + Vite + TypeScript cho admin dashboard
- `docker/`: Dockerfile, Compose va du lieu runtime local
- `scripts/`: smoke test va tien ich validate nhanh

## Yeu cau

- Docker + Docker Compose
- Tai khoan DeepSeek tai `https://chat.deepseek.com`
- Neu server dat o khu vuc de bi WAF/rate limit, nen co proxy non-US hoac API base trung gian

## Cai dat nhanh

```bash
git clone https://github.com/manhvicky/Max-DeepSeek.git
cd Max-DeepSeek
cp .env.example .env
docker compose -f docker/docker-compose.yml up -d --build
```

Mo dashboard: `http://localhost:22218/admin`

Lan dau vao se yeu cau dat mat khau quan tri.

## Quy trinh su dung

1. Dang nhap dashboard admin.
2. Vao **Tai khoan DeepSeek** -> them mot hoac nhieu tai khoan.
3. Vao **API Key** -> tao key moi va luu lai ngay. Key day du chi hien mot lan.
4. Goi API qua chuan OpenAI.

Vi du curl:

```bash
export MAX_DEEPSEEK_API_KEY=<YOUR_API_KEY>
curl -X POST http://localhost:22218/v1/chat/completions \
  -H "Authorization: Bearer ${MAX_DEEPSEEK_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-default",
    "messages": [{"role": "user", "content": "Xin chao"}]
  }'
```

Vi du voi OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:22218/v1",
    api_key="<YOUR_API_KEY>",
)

resp = client.chat.completions.create(
    model="deepseek-default",
    messages=[{"role": "user", "content": "Xin chao"}],
)
print(resp.choices[0].message.content)
```

## Models mac dinh

| Model | Mo ta |
|-------|-------|
| `deepseek-default` | Tro chuyen tieu chuan |
| `deepseek-expert` | Suy luan sau / thinking |
| `deepseek-vision` | Dau vao hinh anh neu upstream ho tro |

## Cau hinh quan trong

Khai bao trong `.env` hoac sua truc tiep `docker/docker-compose.yml`:

- `CORS_ORIGINS` - danh sach origin, tach boi dau phay; khong nen de `*` khi public
- `ADMIN_JWT_EXPIRE_SECONDS` - thoi gian song cua token admin; mac dinh 86400 giay
- `DS_API_BASE` - DeepSeek API base hoac proxy compatible
- `DS_PROXY_URL` - proxy HTTP neu can
- `DS_MIN_ACCOUNT_INTERVAL_MS` - do gian cach giua 2 request tren cung account
- `DS_MAX_ATTEMPTS` - so lan failover sang account khac
- `DS_INIT_CONCURRENCY` - muc login dong thoi khi khoi dong/recovery

Du lieu runtime khi chay Compose duoc luu trong `docker/data/` va da duoc ignore khoi git.

## Phat trien local

```bash
# Backend
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 22218

# Frontend
cd web
npm install
npm run dev
```

## Validate truoc khi push

```bash
python3 -m compileall backend/app scripts/smoke_test.py
cd web && npm run build && cd ..
python3 scripts/smoke_test.py
```

Neu da co instance va muon test sau deploy:

```bash
MAX_DEEPSEEK_URL=http://localhost:22218 \
MAX_DEEPSEEK_ADMIN_PASSWORD='<ADMIN_PASSWORD>' \
MAX_DEEPSEEK_API_KEY='<YOUR_API_KEY>' \
python3 scripts/smoke_test.py
```

## Public an toan hon

- Khong commit `.env`, `docker/data/`, DB SQLite, WASM cache, log hay test key
- Dat `CORS_ORIGINS` theo domain that
- Doi API key sau khi deploy production
- Dat mat khau admin manh va khong dung chung voi tai khoan DeepSeek
- Backup `docker/data/` neu day la instance van hanh quan trong

## Release checklist

- [ ] `git status` sach, khong con data/runtime file
- [ ] `.env.example` cap nhat day du
- [ ] `npm run build` pass
- [ ] `python3 -m compileall backend/app scripts/smoke_test.py` pass
- [ ] `python3 scripts/smoke_test.py` pass
- [ ] README, license, screenshot/dashboard docs day du
- [ ] Tao tag/release note va mo ta ro cach deploy

## License

MIT
