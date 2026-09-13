#!/usr/bin/env python3
"""Build a portable CHIP-8 fix for the archival Videodraw payload."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).with_name(
    "Videodraw (portable fix) [AUD_2464_09_B41_ID19_01].ch8"
)

ORIGINAL_LENGTH = 256
ORIGINAL_SHA256 = "c3d5e465fdba6c275ab02fbef114fa4f69f9cac26edddc10d05326e195d8a9be"
FIXED_SHA256 = "2e2f85723f85786b668f37e7989b743f4f7f75dae89e098b714c9f8ba51ba1be"
ORIGINAL_SHA1 = "87939f2c59bf27d30fdc53dc53161b6c9ef8085c"


def find_input() -> Path:
    for path in Path(__file__).parent.glob("*.ch8"):
        if hashlib.sha1(path.read_bytes()).hexdigest() == ORIGINAL_SHA1:
            return path
    raise FileNotFoundError(f"no input ROM with database SHA-1 {ORIGINAL_SHA1}")


DEFAULT_INPUT = find_input()


def words(*values: int) -> bytes:
    result = bytearray()
    for value in values:
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"CHIP-8 word outside 16 bits: {value:#x}")
        result.extend(value.to_bytes(2, "big"))
    return bytes(result)


# Each tuple is (logical address, exact original bytes, replacement bytes).
PATCHES = (
    # The VIP helper only selects framebuffer page $03 and restores X=2.
    # A portable interpreter already owns its framebuffer; V0 is known zero.
    (0x0206, words(0x0236), words(0x6000)),
    # Normalize coordinates before the next draw so wrapping and clipping
    # interpreters produce the same visible behavior at all four edges.
    (0x0234, words(0x120A), words(0x1250)),
    (0x0250, bytes.fromhex("00D40000FFFBF3FB983B"), words(
        0x6B3F,             # VB = horizontal coordinate mask
        0x81B2,             # V1 &= VB
        0x6B1F,             # VB = vertical coordinate mask
        0x82B2,             # V2 &= VB
        0x120A,             # begin the next cursor interval
    )),
)


def apply_patch(original: bytes) -> bytes:
    digest = hashlib.sha256(original).hexdigest()
    if digest != ORIGINAL_SHA256:
        raise ValueError(f"unexpected input SHA-256: {digest}")
    if len(original) != ORIGINAL_LENGTH:
        raise ValueError(f"unexpected input length: {len(original)}")

    fixed = bytearray(original)
    for address, expected, replacement in PATCHES:
        offset = address - 0x0200
        actual = bytes(fixed[offset : offset + len(expected)])
        if actual != expected:
            raise ValueError(f"original bytes differ at {address:04X}: {actual.hex()}")
        if len(replacement) != len(expected):
            raise AssertionError(f"in-place patch size changed at {address:04X}")
        fixed[offset : offset + len(replacement)] = replacement

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
