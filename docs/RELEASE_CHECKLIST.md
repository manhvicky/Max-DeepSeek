# GitHub Release Checklist

## Before commit

- [ ] `git status` khong con file data/runtime can tranh commit
- [ ] Kiem tra `.env.example` va `README.md` khop voi code hien tai
- [ ] Dam bao `docker/data/`, DB, wasm, logs, test key deu dang bi ignore

## Validation

- [ ] `python3 -m compileall backend/app scripts/smoke_test.py tests/test_api.py`
- [ ] `cd web && npm run build`
- [ ] `python3 scripts/smoke_test.py`
- [ ] `python3 tests/test_api.py`

## Repo polish

- [ ] Them screenshot dashboard vao README neu can
- [ ] Viet release notes: tinh nang, gioi han, huong dan deploy
- [ ] Gan tag version dau tien, vi du `v1.0.0`
- [ ] Kiem tra lai license, mo ta repo va topics tren GitHub

## After publish

- [ ] Tao API key moi cho production
- [ ] Doi mat khau admin neu da test bang mat khau tam
- [ ] Backup `docker/data/` cua instance dang chay
