#!/usr/bin/env python3
"""Validate Keypad Test's portable shifts with the OpenStudio2 firmware."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from build import DEFAULT_INPUT, DEFAULT_OUTPUT, apply_patch


WORKSPACE = Path(__file__).resolve().parents[2]
FONT = bytes.fromhex(
    "F0909090F0 2060202070 F010F080F0 F010F010F0 "
    "9090F01010 F080F010F0 F080F090F0 F010204040 "
    "F090F090F0 F090F010F0 F090F09090 E090E090E0 "
    "F0808080F0 E0909090E0 F080F080F0 F080F08080"
)
COORDS = (
    (8, 25), (1, 1), (8, 1), (15, 1),
    (1, 9), (8, 9), (15, 9), (1, 17),
    (8, 17), (15, 17), (1, 25), (15, 25),
    (22, 1), (22, 9), (22, 17), (22, 25),
)


def expected_screen() -> bytes:
    screen = bytearray(256)
    for digit, (x, y) in enumerate(COORDS):
        for row, sprite in enumerate(FONT[digit * 5 : digit * 5 + 5]):
            for bit in range(8):
                if sprite & (0x80 >> bit):
                    xx, yy = (x + bit) & 63, (y + row) & 31
                    screen[yy * 8 + xx // 8] ^= 0x80 >> (xx & 7)
    return bytes(screen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openstudio2", type=Path, default=WORKSPACE / "OpenStudio2")
    args = parser.parse_args()

    original = DEFAULT_INPUT.read_bytes()
    fixed = DEFAULT_OUTPUT.read_bytes()
    assert fixed == apply_patch(original)

    sys.path.insert(0, str(args.openstudio2))
    sys.modules.pop("build", None)
    test_file = args.openstudio2 / "test_firmware.py"
    spec = importlib.util.spec_from_file_location("os2_keypad_validation", test_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cpu = module.chip8_cpu({0x0200: fixed})
    symbols = module.define_symbols((args.openstudio2 / "openstudio2.asm").read_text().splitlines())

    def run_until(predicate, limit: int = 500_000, tick_timer: bool = False) -> int:
        for steps in range(limit):
            if cpu.r[cpu.p] == symbols["unsupported"]:
                raise AssertionError(f"OpenStudio2 unsupported trap with R5={cpu.r[5]:04X}")
            if predicate():
                return steps
            cpu.step()
            if tick_timer and steps % 200 == 199 and cpu.memory[0x08B2]:
                cpu.memory[0x08B2] -= 1
        raise AssertionError("OpenStudio2 scenario timed out")

    at_wait = lambda: cpu.r[cpu.p] == symbols["op_wait_key"]
    run_until(at_wait)
    clean_screen = bytes(cpu.memory[0x0900:0x0A00])
    assert clean_screen == expected_screen()

    for key in range(16):
        if key < 10:
            cpu.keypad_a = {key}
        else:
            cpu.keypad_b = {key - 9}
        run_until(lambda: cpu.r[cpu.p] == symbols["key_wait_release"])
        cpu.keypad_a.clear()
        cpu.keypad_b.clear()
        cpu.step()
        run_until(at_wait, tick_timer=True)
        assert bytes(cpu.memory[0x0900:0x0A00]) == clean_screen

    print("reproducible image: passed")
    print("clean 4x4 keypad layout: passed")
    print("all 16 key highlights restore the display: passed")


if __name__ == "__main__":
    main()
