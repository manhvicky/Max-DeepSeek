"""Mã hóa credential (Fernet) + hash mật khẩu admin."""
from __future__ import annotations

import base64
import hashlib
import os

import bcrypt
from cryptography.fernet import Fernet


def _fernet(secret: str) -> Fernet:
    """Sinh khóa Fernet ổn định từ 1 secret tùy ý."""
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt(plaintext: str, secret: str) -> str:
    if plaintext is None:
        plaintext = ""
    return _fernet(secret).encrypt(plaintext.encode()).decode()


def decrypt(token: str, secret: str) -> str:
    if not token:
        return ""
    return _fernet(secret).decrypt(token.encode()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def random_secret(nbytes: int = 32) -> str:
    return base64.urlsafe_b64encode(os.urandom(nbytes)).decode().rstrip("=")


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_api_key() -> str:
    return "sk-" + os.urandom(24).hex()
