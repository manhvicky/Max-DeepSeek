# Max-DeepSeek v1.0.0

Bản phát hành public đầu tiên của Max-DeepSeek.

## Điểm nổi bật

- Gateway self-hosted tương thích OpenAI, vận hành bằng pool tài khoản DeepSeek
- Dashboard admin tiếng Việt cho tài khoản, API key, logs, cấu hình và proxy
- Trung tâm cập nhật trong ứng dụng với kiểm tra phiên bản, xem changelog, lệnh cập nhật thủ công, lệnh rollback và lịch sử cập nhật
- Metadata tác giả/người duy trì hiển thị trực tiếp trong dashboard
- Mặc định an toàn hơn khi public release: lưu API key theo kiểu masked + hashed, CORS cấu hình được, admin JWT có thời hạn
- Có smoke test và test hồi quy API cơ bản

## Có gì mới trong bản này

- Thêm trang `Cập nhật` trong dashboard
- Thêm trang `Tác giả` với thông tin người duy trì
- Thêm các API cập nhật: status, check, apply, rollback, history
- Thêm `scripts/update.sh` và `scripts/rollback.sh`
- Thêm ví dụ update manifest để host metadata phát hành trên GitHub

## Đã kiểm tra

- `python3 -m compileall backend/app scripts tests`
- `cd web && npm run build`
- `docker build -f docker/Dockerfile -t max-deepseek:latest .`
- Test API end-to-end trên container sạch
- Smoke test trên container sạch

## Người duy trì

- Vũ Duy Mạnh
- manhq7@gmail.com
