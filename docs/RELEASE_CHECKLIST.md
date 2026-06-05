# Checklist phát hành GitHub

## Trước khi commit

- [ ] `git status` không còn file data/runtime cần tránh commit
- [ ] Kiểm tra `.env.example` và `README.md` khớp với code hiện tại
- [ ] Đảm bảo `docker/data/`, DB, wasm, logs, test key đều đang bị ignore

## Validation

- [ ] `python3 -m compileall backend/app scripts/smoke_test.py tests/test_api.py`
- [ ] `cd web && npm run build`
- [ ] `python3 scripts/smoke_test.py`
- [ ] `python3 tests/test_api.py`

## Hoàn thiện repo

- [ ] Thêm screenshot dashboard vào README nếu cần
- [ ] Viết release notes: tính năng, giới hạn, hướng dẫn deploy
- [ ] Gắn tag version đầu tiên, ví dụ `v1.0.0`
- [ ] Kiểm tra lại license, mô tả repo và topics trên GitHub

## Sau khi publish

- [ ] Tạo API key mới cho production
- [ ] Đổi mật khẩu admin nếu đã test bằng mật khẩu tạm
- [ ] Backup `docker/data/` của instance đang chạy
