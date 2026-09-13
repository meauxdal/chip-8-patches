#!/usr/bin/env python3
"""Build the portable CHIP-8 fix for Hap's Keypad Test."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).with_name("KEYPAD TEST (portable fix) [Hap, 2006].ch8")

ORIGINAL_LENGTH = 114
ORIGINAL_SHA256 = "8be9c412a1c27efb72a7aa7c5f63f013b5b08af0df59febc0a909c90685caf65"
FIXED_SHA256 = "4132032f1d3874c8b6ad7728b1e402ba1b6330db1f775a5e858ae3f9599a6a23"
ORIGINAL_SHA1 = "0ebc4b92c6059d6193565644fb00108161d03d23"


def find_input() -> Path:
    for path in Path(__file__).parent.glob("*.ch8"):
        if hashlib.sha1(path.read_bytes()).hexdigest() == ORIGINAL_SHA1:
            return path
    raise FileNotFoundError(f"no input ROM with database SHA-1 {ORIGINAL_SHA1}")


DEFAULT_INPUT = find_input()


def words(*values: int) -> bytes:
    return b"".join(value.to_bytes(2, "big") for value in values)


# Each tuple is (logical address, exact original bytes, replacement bytes).
PATCHES = (
    (0x022C, words(0x820E), words(0x822E)),
    (0x0230, words(0x8206), words(0x8226)),
    (0x0238, words(0x820E), words(0x822E)),
    (0x023C, words(0x8206), words(0x8226)),
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
    parser.add_argument("--check", action="store_true")
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
