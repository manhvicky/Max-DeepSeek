"""PoW solver — DeepSeekHashV1 qua WASM (wasmtime).

Port từ cơ chế của ds-free-api: dò export theo tên + chữ ký, gọi wasm_solve,
đọc kết quả từ retptr (status @ offset 0, answer f64 @ offset 8).
"""
from __future__ import annotations

import base64
import json
import struct
from dataclasses import dataclass

from wasmtime import Engine, Instance, Linker, Module, Store


@dataclass
class Challenge:
    algorithm: str
    challenge: str
    salt: str
    signature: str
    difficulty: int
    expire_at: int
    target_path: str

    @classmethod
    def from_json(cls, d: dict) -> "Challenge":
        return cls(
            algorithm=d["algorithm"],
            challenge=d["challenge"],
            salt=d["salt"],
            signature=d["signature"],
            difficulty=int(d["difficulty"]),
            expire_at=int(d["expire_at"]),
            target_path=d["target_path"],
        )


class PowError(Exception):
    pass


class PowSolver:
    """Giải PoW DeepSeekHashV1. Khởi tạo 1 lần với wasm_bytes, solve nhiều lần."""

    def __init__(self, wasm_bytes: bytes):
        self.engine = Engine()
        self.module = Module(self.engine, wasm_bytes)
        self.linker = Linker(self.engine)

        exports = {e.name: e for e in self.module.exports}

        self.add_to_stack_name = self._find(
            exports, ["__wbindgen_add_to_stack_pointer"]
        ) or "__wbindgen_add_to_stack_pointer"
        self.alloc_name = self._find(
            exports, ["__wbindgen_malloc"], prefix="__wbindgen_export_"
        )
        self.solve_name = self._find(exports, ["wasm_solve"])
        if not self.alloc_name or not self.solve_name:
            raise PowError("Không tìm thấy export allocator/wasm_solve trong WASM")

    @staticmethod
    def _find(exports: dict, names: list[str], prefix: str | None = None) -> str | None:
        for n in names:
            if n in exports:
                return n
        if prefix:
            for name in exports:
                if name.startswith(prefix):
                    return name
        return None

    def solve(self, ch: Challenge) -> str:
        """Trả về base64 header X-Ds-Pow-Response."""
        if ch.algorithm != "DeepSeekHashV1":
            raise PowError(f"Thuật toán không hỗ trợ: {ch.algorithm}")

        store = Store(self.engine)
        instance = self.linker.instantiate(store, self.module)
        exports = instance.exports(store)

        memory = exports["memory"]
        add_to_stack = exports[self.add_to_stack_name]
        alloc = exports[self.alloc_name]
        wasm_solve = exports[self.solve_name]

        prefix = f"{ch.salt}_{ch.expire_at}_"

        retptr = add_to_stack(store, -16)

        ptr_ch, len_ch = self._write_string(store, memory, alloc, ch.challenge)
        ptr_pfx, len_pfx = self._write_string(store, memory, alloc, prefix)

        wasm_solve(store, retptr, ptr_ch, len_ch, ptr_pfx, len_pfx,
                   float(ch.difficulty))

        data = memory.read(store, retptr, retptr + 16)
        status = struct.unpack("<i", data[0:4])[0]
        value = struct.unpack("<d", data[8:16])[0]

        # khôi phục stack pointer
        add_to_stack(store, 16)

        if status == 0:
            raise PowError("WASM không tìm được lời giải")

        answer = int(value)
        header = {
            "algorithm": ch.algorithm,
            "challenge": ch.challenge,
            "salt": ch.salt,
            "answer": answer,
            "signature": ch.signature,
            "target_path": ch.target_path,
        }
        return base64.b64encode(
            json.dumps(header, ensure_ascii=False).encode()
        ).decode()

    @staticmethod
    def _write_string(store, memory, alloc, s: str) -> tuple[int, int]:
        data = s.encode()
        length = len(data)
        ptr = alloc(store, length, 1)
        memory.write(store, data, ptr)
        return ptr, length
