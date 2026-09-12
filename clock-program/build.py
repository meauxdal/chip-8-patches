#!/usr/bin/env python3
"""Build the portable CHIP-8 fix for Bill Fisher's Clock Program."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_INPUT = Path(__file__).with_name("Clock Program [Bill Fisher, 1981].ch8")
DEFAULT_OUTPUT = Path(__file__).with_name("Clock Program [Bill Fisher, 1981] (portable fix).ch8")

ORIGINAL_LENGTH = 280
ORIGINAL_SHA256 = "f6773f7385982165d693febc7e26826dead4a66cd2376f603a66fcb775ca1a34"
FIXED_SHA256 = "bf2d6d3bdcaefa4997ac81d40790adccb58be5c264b917b8f6a3c355123d98a7"


def words(*values: int) -> bytes:
    result = bytearray()
    for value in values:
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"CHIP-8 word outside 16 bits: {value:#x}")
        result.extend(value.to_bytes(2, "big"))
    return bytes(result)


# Each tuple is (logical address, exact original bytes, replacement bytes).
PATCHES = (
    # Replace 59 timer ticks plus a VIP-speed native pad with 60 timer ticks.
    (0x0252, words(0x6D3B), words(0x6D3C)),
    # Skip the now-unneeded CDP1802 routine and begin the next interval.
    (0x0266, words(0x02D8), words(0x1252)),
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
