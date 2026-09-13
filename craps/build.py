#!/usr/bin/env python3
"""Build the self-contained CHIP-8 fix for Carmelo Cortez's Craps."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).with_name("Craps (portable fix) [Carmelo Cortez, 1978].ch8")

ORIGINAL_LENGTH = 0xC0
ORIGINAL_SHA256 = "d482fcc8536bbcf20045063c404df1a005a688c8c814bd22db5c6f11277edd03"
FIXED_SHA256 = "2dee82081ef51e77187ff83d931288f2ec3c732b382f7c43ed068b4809ae735a"
ORIGINAL_SHA1 = "35158696bd94ea22ef34e899fff1f15f7154d4fd"


def find_input() -> Path:
    for path in Path(__file__).parent.glob("*.ch8"):
        if hashlib.sha1(path.read_bytes()).hexdigest() == ORIGINAL_SHA1:
            return path
    raise FileNotFoundError(f"no input ROM with database SHA-1 {ORIGINAL_SHA1}")


DEFAULT_INPUT = find_input()

PROGRAM_START = 0x0200
FRAME_ADDRESS = 0x02F0
FRAME = bytes.fromhex("FF 81 81 81 81 81 FF")
FRAME_CALL = bytes.fromhex("A2 F0 62 08 D1 27 00 EE")


def apply_patch(original: bytes) -> bytes:
    digest = hashlib.sha256(original).hexdigest()
    if digest != ORIGINAL_SHA256:
        raise ValueError(f"unexpected input SHA-256: {digest}")
    if len(original) != ORIGINAL_LENGTH:
        raise ValueError(f"unexpected input length: {len(original)}")

    call_offset = 0x0258 - PROGRAM_START
    actual = original[call_offset : call_offset + len(FRAME_CALL)]
    if actual != FRAME_CALL:
        raise ValueError(f"original bytes differ at 0258: {actual.hex()}")

    fixed = bytearray(original)
    frame_offset = FRAME_ADDRESS - PROGRAM_START
    fixed.extend(bytes(frame_offset - len(fixed)))
    fixed.extend(FRAME)

    result = bytes(fixed)
    digest = hashlib.sha256(result).hexdigest()
    if digest != FIXED_SHA256:
        raise AssertionError(f"unexpected output SHA-256: {digest}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="verify an existing output instead of writing it")
    args = parser.parse_args()

    original = args.input.read_bytes()
    fixed = apply_patch(original)
    if args.check:
        if args.output.read_bytes() != fixed:
            raise SystemExit(f"{args.output} is stale or differs from the reproducible build")
    else:
        args.output.write_bytes(fixed)

    print(f"input  sha256 {hashlib.sha256(original).hexdigest()}")
    print(f"output sha256 {hashlib.sha256(fixed).hexdigest()}")
    print(f"output bytes  {len(fixed)}")


if __name__ == "__main__":
    main()
