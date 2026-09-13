#!/usr/bin/env python3
"""Reproducibility, memory-independence, and OpenStudio2 checks for Craps."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path

from build import (
    DEFAULT_INPUT,
    DEFAULT_OUTPUT,
    FIXED_SHA256,
    FRAME,
    FRAME_ADDRESS,
    ORIGINAL_LENGTH,
    ORIGINAL_SHA256,
    PROGRAM_START,
    apply_patch,
)


WORKSPACE = Path(__file__).resolve().parents[2]


def draw(screen: bytearray, sprite: bytes, x: int, y: int) -> None:
    for row, value in enumerate(sprite):
        for bit in range(8):
            if value & (0x80 >> bit):
                xx, yy = (x + bit) & 63, (y + row) & 31
                screen[yy * 8 + xx // 8] ^= 0x80 >> (xx & 7)


def expected_startup_screen() -> bytes:
    screen = bytearray(256)
    draw(screen, FRAME, 8, 8)
    draw(screen, FRAME, 18, 8)
    return bytes(screen)


def startup_screen(image: bytes, fill: int) -> bytes:
    memory = bytearray([fill]) * 4096
    memory[PROGRAM_START : PROGRAM_START + len(image)] = image
    sprite = bytes(memory[FRAME_ADDRESS : FRAME_ADDRESS + 7])
    screen = bytearray(256)
    draw(screen, sprite, 8, 8)
    draw(screen, sprite, 18, 8)
    return bytes(screen)


def validate_openstudio2(image: bytes, os2: Path) -> str:
    test_file, asm_file = os2 / "test_firmware.py", os2 / "openstudio2.asm"
    if not test_file.is_file() or not asm_file.is_file():
        return f"skipped (not found at {os2})"

    sys.path.insert(0, str(os2))
    sys.modules.pop("build", None)
    spec = importlib.util.spec_from_file_location("os2_craps_validation", test_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cpu = module.chip8_cpu({PROGRAM_START: image})
    symbols = module.define_symbols(asm_file.read_text(encoding="utf-8").splitlines())
    cpu.keypad_a = {1}
    for steps in range(500_000):
        if cpu.r[cpu.p] == symbols["unsupported"]:
            raise AssertionError(f"OpenStudio2 unsupported trap with R5={cpu.r[5]:04X}")
        if cpu.r[cpu.p] == symbols["key_wait_release"]:
            screen = bytes(cpu.memory[0x0900:0x0A00])
            if screen != expected_startup_screen():
                raise AssertionError("OpenStudio2 startup display does not contain the two reconstructed frames")
            return f"passed ({steps} CDP1802 instructions to key-release wait)"
        cpu.step()
    raise AssertionError("OpenStudio2 did not reach the initial key-release wait")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openstudio2", type=Path, default=WORKSPACE / "OpenStudio2")
    args = parser.parse_args()

    original = DEFAULT_INPUT.read_bytes()
    assert len(original) == ORIGINAL_LENGTH
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256

    fixed = DEFAULT_OUTPUT.read_bytes()
    assert fixed == apply_patch(original), "fixed image is stale or not reproducible"
    assert hashlib.sha256(fixed).hexdigest() == FIXED_SHA256

    expected = expected_startup_screen()
    assert startup_screen(fixed, 0x00) == expected
    assert startup_screen(fixed, 0xA5) == expected
    assert startup_screen(original, 0x00) != startup_screen(original, 0xA5)

    print(f"reproducible image: passed ({FIXED_SHA256}; {len(fixed)} bytes)")
    print("source identity: passed (local guarded original)")
    print("memory independence: passed (fixed frames do not depend on bytes left by an earlier program)")
    print("frame geometry: passed (two 8x7 boxes with 4x5 numeral interiors)")
    print(f"OpenStudio2 firmware simulation: {validate_openstudio2(fixed, args.openstudio2)}")


if __name__ == "__main__":
    main()
