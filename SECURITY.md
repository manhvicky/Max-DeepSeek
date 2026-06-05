# Chính sách bảo mật

Nếu bạn phát hiện vấn đề bảo mật, vui lòng **không mở public issue ngay lập tức**.

## Cách báo cáo

Gửi email tới:

- Vũ Duy Mạnh
- manhq7@gmail.com

Kèm theo:

- mô tả ngắn gọn về lỗ hổng
- cách tái hiện
- mức độ ảnh hưởng
- log/ảnh để nhận diện nếu có

## Phạm vi ưu tiên

Ưu tiên xử lý cho các vấn đề:

- bỏ qua xác thực admin
- rò rỉ API key, mật khẩu hoặc token
- SSRF/proxy abuse
- thực thi lệnh trái phép trong flow update
- lỗi cho phép đọc/sửa dữ liệu runtime của instance khác

## Lưu ý

- Đây là dự án self-hosted; người vận hành cần tự bảo vệ `.env`, backup và host runtime.
- Vui lòng cho phép một khoảng thời gian hợp lý để xác nhận và khắc phục trước khi công khai chi tiết.
