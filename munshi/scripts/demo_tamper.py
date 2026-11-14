#!/usr/bin/env python3
"""Flip ONE byte of a file to show that verification fails.  python scripts/demo_tamper.py pack.pdf [out.pdf]"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def flip_one_byte(data: bytes, offset: int | None = None) -> bytes:
    i = len(data) // 2 if offset is None else offset
    b = bytearray(data)
    b[i] ^= 0x01
    return bytes(b)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name(src.stem + "-tampered" + src.suffix)
    data = src.read_bytes()
    tampered = flip_one_byte(data)
    dst.write_bytes(tampered)
    print(f"original  sha256 {hashlib.sha256(data).hexdigest()}")
    print(f"tampered  sha256 {hashlib.sha256(tampered).hexdigest()}  (1 byte flipped at offset {len(data) // 2})")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
