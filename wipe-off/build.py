#!/usr/bin/env python3
"""Build the manual-corrected Wipe Off preservation image."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).with_name("Wipe Off (fix) [Joseph Weisbecker, 19xx].ch8")

ORIGINAL_SHA256 = "4304cafe94cc85802ec52b330f7ab3dcd7aee3a91b2c653aa441aad3cc741420"
FIXED_SHA256 = "3e5e87255c96369e41a16499b47229b973cfdfc2972d371f4a4f725e52c50412"
ORIGINAL_SHA1 = "d666688a8fce468a7d88b536bc1ef5f35ba12031"


def find_input() -> Path:
    for path in Path(__file__).parent.glob("*.ch8"):
        if hashlib.sha1(path.read_bytes()).hexdigest() == ORIGINAL_SHA1:
            return path
    raise FileNotFoundError(f"no input ROM with database SHA-1 {ORIGINAL_SHA1}")


DEFAULT_INPUT = find_input()


def apply_patch(original: bytes) -> bytes:
    digest = hashlib.sha256(original).hexdigest()
    if len(original) != 206 or digest != ORIGINAL_SHA256:
        raise ValueError(f"unexpected 206-byte input SHA-256: {digest}")

    fixed = bytearray(original)
    offset = 0x021F - 0x0200
    if fixed[offset] != 0x10:
        raise ValueError(f"original byte differs at 021F: {fixed[offset]:02x}")
    fixed[offset] = 0x14

    result = bytes(fixed)
    if hashlib.sha256(result).hexdigest() != FIXED_SHA256:
        raise AssertionError("unexpected output SHA-256")
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
