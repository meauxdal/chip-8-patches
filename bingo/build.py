#!/usr/bin/env python3
"""Build the portable CHIP-8 fix for VIP Bingo without changing the original."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).with_name("Bingo (portable fix) [TCNJ S.572.2, 3, 197x].ch8")
ORIGINAL_SHA256 = "702676f43590720f95e5fc3c334a00a58478b0fca5c082f25c772f54abcaa65a"
ORIGINAL_SHA1 = "08f70fe1c228d15a7a5f456840b5e0e56a51fd99"


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
    (0x0200, words(0x604F, 0xA454, 0x2386), words(0x24B0, 0x1206, 0x7000)),
    (0x0220, words(0x237A), words(0x2528)),
    (0x0222, words(0x237A), words(0x7000)),
    (0x0238, words(0xA454), words(0x14D0)),
    (0x024A, words(0x239C), words(0x2550)),
    (0x0270, words(0x600A, 0x70FF, 0x3000, 0x1272), words(0x251A, 0x1278, 0x7000, 0x7000)),
    (0x0286, words(0x2392), words(0x25D0)),
    (0x02B0, words(0x87E0), words(0x14F4)),
    (0x02C8, words(0x0414, 0xFE00), words(0x2510, 0x6000)),
    (0x02DA, words(0x237A), words(0x25F4)),
    (0x02E2, words(0x040E, 0xF100), words(0x25E8, 0x6F00)),
    (0x02F6, words(0x040E, 0xFC00), words(0x24E8, 0x6003)),
    (0x02FE, words(0x040E, 0xF100), words(0x25E8, 0x6F00)),
    (0x0310, words(0x0414, 0xF100), words(0x2684, 0x6000)),
    (0x0320, words(0x2354), words(0x2652)),
    (0x0330, words(0x237A), words(0x25F4)),
    (0x03CC, words(0x040E, 0xFC00), words(0x24E8, 0x6F00)),
    (0x03D8, words(0x040E, 0xFC00), words(0x24E8, 0x6F00)),
)


# New code occupies bytes beyond the manual's 0452 end-of-program marker and
# above the game's highest referenced data byte (04A8), but below VIP work RAM.
ROUTINES = (
    (0x04B0, words(
        0x6000,             # V0 = zero value
        0x6100,             # V1 = table index
        0xA454,             # clear_loop: I = called-number table base
        0xF11E,             # I += V1
        0xF055,             # [I] = V0; post-increment is deliberately ignored
        0x7101,             # V1++
        0x314F,             # done after 79 bytes (flags plus original scratch)
        0x14B4,             # loop
        0xA69D, 0xF055,     # older displayed number = 0
        0xA69E, 0xF055,     # most recent displayed number = 0
        0x00EE,
    )),
    (0x04D0, words(
        0xA454, 0xF71E,     # I = called-number table + candidate
        0xF065,             # V0 = flag
        0x3000, 0x1224,     # retry if already called
        0xA454, 0xF71E,     # recompute I regardless of Fx65 post-increment quirk
        0x6001, 0xF055,     # mark called; resulting I is not consumed
        0x1248,
    )),
    (0x04E8, words(
        0x8900,             # preserve V0 in otherwise-dead V9
        0xF065,             # V0 = [I]
        0x8C00,             # VC = V0
        0x8090,             # restore V0
        0x00EE,
    )),
    (0x04F4, words(
        0x87E0, 0x81E0,     # V7 = first digit; V1 = first digit
        0x8114, 0x8114, 0x8114,  # V1 = digit * 8, without shift quirks
        0x8714, 0x87E4,     # V7 = digit * 10
        0x80E0, 0xA4A1,
        0xF055,             # save first digit
        0xA4A2,             # make Fx55 post-increment irrelevant
        0x12C2,
    )),
    (0x0510, words(
        0xA4A2, 0x80E0,
        0xF055,             # save second digit
        0xA4A2,             # make Fx55 post-increment explicit
        0x00EE,
    )),
    (0x051A, words(
        0x6001, 0xF015,     # portable one-tick visible phase
        0xF007, 0x3000,
        0x151E, 0x00EE,
    )),
    (0x0528, words(
        0x00E0,
        0xA69D, 0xF065, 0x8700, 0x6101, 0x3700, 0x2570,
        0xA69E, 0xF065, 0x8700, 0x610D, 0x3700, 0x2570,
        0x00EE,
    )),
    (0x0550, words(
        0xA69E, 0xF065,     # V0 = previous most recent number
        0xA69D, 0xF055,     # move it to older slot
        0x8070,             # V0 = current V7
        0xA69E, 0xF055,     # save as most recent
        0x239C,             # original category-letter/BCD routine
        0x00EE,
    )),
    (0x0570, words(
        0x623C, 0x8275, 0x4F00, 0x159A,
        0x622D, 0x8275, 0x4F00, 0x159E,
        0x621E, 0x8275, 0x4F00, 0x15A2,
        0x620F, 0x8275, 0x4F00, 0x15A6,
        0xA44C, 0x15AA,
        0x7000, 0x7000, 0x7000,
        0xA448, 0x15AA,
        0xA444, 0x15AA,
        0xA43F, 0x15AA,
        0xA43A, 0x15AA,
        0x6010, 0xD015,     # category letter at caller-selected row
        0xA4A6, 0xF733,     # decimal conversion
        0xA4A7, 0xF065, 0xF029, 0x6019, 0xD015,
        0xA4A8, 0xF065, 0xF029, 0x601F, 0xD015,
        0x00EE,
    )),
    (0x05D0, words(
        0x2392,             # original tone/key-release helper
        0x6000,
        0xA69D, 0xF055,
        0xA69E, 0xF055,
        0xA68F, 0xF055,     # verified-row count = 0
        0x00EE,
    )),
    (0x05E8, words(
        0x8900,             # preserve V0 in otherwise-dead V9
        0xF065,             # V0 = [I]
        0x8100,             # V1 = V0
        0x8090,             # restore V0
        0x00EE,
    )),
    (0x05F4, words(
        0x00E0,
        0xA68F, 0xF065, 0x8600,  # V6 = verified-row count
        0x3600, 0x1604, 0x00EE, 0x7000,
        0x3605, 0x1610,     # five rows: discard the oldest after scrolling
        0x6301, 0x6101, 0x6604, 0x1620,
        0x6300, 0x6119, 0x8260,
        0x4200, 0x1620, 0x71FA, 0x72FF, 0x1616,
        0xA690, 0xF31E, 0xF065, 0x8700, 0x2570,
        0xA698, 0xF31E, 0xF065,
        0x3000, 0x1638, 0xA426, 0x163A, 0xA41C,
        0x6020, 0xD015, 0x7008, 0x6B05, 0xFB1E, 0xD015,
        0x7106, 0x7301, 0x76FF, 0x3600, 0x1620, 0x00EE,
    )),
    (0x0652, words(
        0xA68F, 0xF065, 0x8A00,  # VA = append index
        0x6B00, 0x3100, 0x6B01,  # VB = current OK flag
        0xA690, 0xFA1E, 0x8070, 0xF055,
        0xA698, 0xFA1E, 0x80B0, 0xF055,
        0x7A01, 0x80A0, 0xA68F, 0xF055,
        0x3B00, 0x167E, 0xA426, 0x1680, 0xA41C,
        0x2354, 0x00EE,
    )),
    (0x0684, words(
        0x8900,             # preserve V0 in otherwise-dead V9
        0x8010, 0xF055,     # [I] = V1
        0x8090, 0x00EE,     # restore V0
    )),
)


def apply_patch(original: bytes) -> bytes:
    digest = hashlib.sha256(original).hexdigest()
    if digest != ORIGINAL_SHA256:
        raise ValueError(f"unexpected input SHA-256: {digest}")
    if len(original) != 1536:
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

    for address, replacement in ROUTINES:
        offset = address - 0x0200
        if address < 0x04B0 or address + len(replacement) > 0x069D:
            raise AssertionError(f"new routine outside reclaimed user space at {address:04X}")
        fixed[offset : offset + len(replacement)] = replacement

    return bytes(fixed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="verify an existing output instead of writing it")
    args = parser.parse_args()

    fixed = apply_patch(args.input.read_bytes())
    if args.check:
        if args.output.read_bytes() != fixed:
            raise SystemExit(f"{args.output} is stale or differs from the reproducible build")
    else:
        args.output.write_bytes(fixed)

    print(f"input  sha256 {ORIGINAL_SHA256}")
    print(f"output sha256 {hashlib.sha256(fixed).hexdigest()}")
    print(f"output bytes  {len(fixed)}")


if __name__ == "__main__":
    main()
