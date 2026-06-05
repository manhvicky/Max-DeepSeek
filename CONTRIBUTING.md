# Đóng góp

Cảm ơn bạn đã quan tâm đến Max-DeepSeek.

## Nguyên tắc đóng góp

- Tạo issue mô tả bug, regression hoặc đề xuất tính năng trước khi mở PR lớn.
- Giữ thay đổi nhỏ, tập trung và có khả năng review.
- Không commit secret, token, database runtime, log hoặc dữ liệu cá nhân.
- Nếu thay đổi hành vi API, hãy cập nhật `README.md`, `.env.example` và test liên quan.

## Quy trình đề xuất

1. Fork repo và tạo branch mới từ `master`.
2. Cài đặt môi trường local theo hướng dẫn trong `README.md`.
3. Chạy validate tối thiểu trước khi gửi PR:

```bash
python3 -m compileall backend/app scripts tests
cd web && npm run build && cd ..
python3 tests/test_api.py
```

4. Nếu thay đổi giao diện, nên kèm screenshot hoặc GIF ngắn.
5. Mở PR mô tả rõ lý do thay đổi, cách test và ảnh hưởng đến deploy.

## Phạm vi ưu tiên cho PR

- Fix bug gây ảnh hưởng đến self-hosted deployment
- Cải thiện tài liệu sử dụng/deploy
- Thêm test cho hành vi đang có
- Nâng cấp bảo mật mà không phá vỡ setup hiện tại

## Không nên đưa vào PR

- Secret thật, cookie, tài khoản DeepSeek thật
- File runtime trong `docker/data/`
- Build artifact trong `web/dist/`
- Thay đổi unrelated lớn không có mô tả hoặc test
