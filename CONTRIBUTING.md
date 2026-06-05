# Contributing

Cam on ban da quan tam den Max-DeepSeek.

## Nguyen tac dong gop

- Tao issue mo ta bug, regression hoac de xuat tinh nang truoc khi mo PR lon.
- Giu thay doi nho, tap trung va co kha nang review.
- Khong commit secret, token, database runtime, log hoac du lieu ca nhan.
- Neu thay doi hanh vi API, hay cap nhat `README.md`, `.env.example` va test lien quan.

## Quy trinh de xuat

1. Fork repo va tao branch moi tu `master`.
2. Cai dat moi truong local theo huong dan trong `README.md`.
3. Chay validate toi thieu truoc khi gui PR:

```bash
python3 -m compileall backend/app scripts tests
cd web && npm run build && cd ..
python3 tests/test_api.py
```

4. Neu thay doi giao dien, nen kem screenshot hoac gif ngan.
5. Mo PR mo ta ro ly do thay doi, cach test va anh huong den deploy.

## Pham vi uu tien cho PR

- Fix bug gay anh huong den self-hosted deployment
- Cai thien tai lieu su dung/deploy
- Them test cho hanh vi dang co
- Nang cap bao mat ma khong pha vo setup hien tai

## Khong nen dua vao PR

- Secret that, cookie, account DeepSeek that
- File runtime trong `docker/data/`
- Build artifact trong `web/dist/`
- Thay doi unrelated lon khong co mo ta hoac test
