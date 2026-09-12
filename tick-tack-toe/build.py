#!/usr/bin/env python3
"""Build a portable VIP Tick-Tack-Toe image without changing either source copy."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_INPUT = Path(__file__).with_name("Tick-Tack-Toe (fix) [Joseph Weisbecker, 1977].ch8")
DEFAULT_OUTPUT = Path(__file__).with_name("VIP Tick-Tack-Toe (portable fix).ch8")

SOURCES = {
    "40474f473154e467ac9ece7e01656764cdbb16fe6884c6ecc4092ef5a7a7dec9": 470,
    "22d6c108415ff9ed86c7c7fcdcf29563e923f954e06ac938a171d593964072d6": 512,
}
PROGRAM_LENGTH = 470  # Manual listing ends with the opcode at 03D4-03D5.
FIXED_SHA256 = "b54cd3243b58499ad747f7b1e46e377d38d3f9470e1a50c74c18034dcfb3fcad"


def words(*values: int) -> bytes:
    result = bytearray()
    for value in values:
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"CHIP-8 word outside 16 bits: {value:#x}")
        result.extend(value.to_bytes(2, "big"))
    return bytes(result)


# This is entered with a jump, not a CHIP-8 call, because the original 0NNN
# service did not consume a CHIP-8 stack slot. V0-V2 and I are overwritten by
# the drawing routine at 032E immediately after control resumes at 0202.
CLEAR_ROUTINE = words(
    0x6000,             # V0 = first zero byte
    0x6100,             # V1 = second zero byte
    0x6200,             # V2 = board offset
    0xA3F0,             # loop: I = board base
    0xF21E,             # I += V2
    0xF155,             # store two zeros; ignore Fx55 post-increment
    0x7202,             # next pair
    0x3210,             # all 16 bytes cleared?
    0x13DC,             # loop
    0x1202,             # resume at the original next instruction
)


def apply_patch(original: bytes) -> bytes:
    digest = hashlib.sha256(original).hexdigest()
    expected_length = SOURCES.get(digest)
    if expected_length is None:
        raise ValueError(f"unexpected input SHA-256: {digest}")
    if len(original) != expected_length:
        raise ValueError(f"unexpected input length: {len(original)}")
    if original[:2] != words(0x02E4):
        raise ValueError(f"original bytes differ at 0200: {original[:2].hex()}")

    # Both accepted sources contain the exact 470-byte program printed in the
    # VIP manual. The 512-byte extraction adds bytes beyond the listing.
    fixed = bytearray(original[:PROGRAM_LENGTH])
    fixed[:2] = words(0x13D6)
    fixed.extend(CLEAR_ROUTINE)
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
