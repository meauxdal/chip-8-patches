#!/usr/bin/env python3
"""Reproducibility, control-flow, quirk, and OpenStudio2 checks for Videodraw."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

from build import (
    DEFAULT_INPUT,
    DEFAULT_OUTPUT,
    FIXED_SHA256,
    ORIGINAL_LENGTH,
    ORIGINAL_SHA256,
    apply_patch,
)


WORKSPACE = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Quirks:
    name: str
    wrap: bool
    increment_i: bool


QUIRKS = (
    Quirks("VIP", True, True),
    Quirks("wrapping/no-I-increment", True, False),
    Quirks("clipping/I-increment", False, True),
    Quirks("clipping/no-I-increment", False, False),
)


class Chip8:
    def __init__(self, image: bytes, quirks: Quirks, allow_native: bool = False):
        self.mem = bytearray(4096)
        self.mem[0x200 : 0x200 + len(image)] = image
        self.v = [0] * 16
        self.i = 0
        self.pc = 0x200
        self.delay = 0
        self.keys: set[int] = set()
        self.screen = bytearray(256)
        self.quirks = quirks
        self.allow_native = allow_native
        self.native_entries: list[tuple[int, int]] = []

    def draw(self, x: int, y: int, height: int) -> None:
        self.v[0xF] = 0
        for row in range(height):
            yy = y + row
            if self.quirks.wrap:
                yy &= 31
            elif yy >= 32:
                continue
            for bit in range(8):
                if not self.mem[self.i + row] & (0x80 >> bit):
                    continue
                xx = x + bit
                if self.quirks.wrap:
                    xx &= 63
                elif xx >= 64:
                    continue
                offset, mask = yy * 8 + xx // 8, 0x80 >> (xx & 7)
                self.v[0xF] |= int(bool(self.screen[offset] & mask))
                self.screen[offset] ^= mask

    def step(self) -> int:
        at = self.pc
        op = int.from_bytes(self.mem[at : at + 2], "big")
        self.pc += 2
        top, nnn = op >> 12, op & 0xFFF
        x, y, n, kk = (op >> 8) & 0xF, (op >> 4) & 0xF, op & 0xF, op & 0xFF

        if op == 0x00E0:
            self.screen[:] = bytes(256)
        elif top == 0:
            if not self.allow_native or nnn != 0x236:
                raise AssertionError(f"unexpected native call {op:04X} at {at:04X}")
            self.native_entries.append((at, nnn))
        elif top == 1:
            self.pc = nnn
        elif top in (3, 4):
            if (self.v[x] == kk) == (top == 3):
                self.pc += 2
        elif top == 6:
            self.v[x] = kk
        elif top == 7:
            self.v[x] = (self.v[x] + kk) & 0xFF
        elif top == 8 and n == 0:
            self.v[x] = self.v[y]
        elif top == 8 and n == 2:
            self.v[x] &= self.v[y]
        elif top == 0xA:
            self.i = nnn
        elif top == 0xD:
            self.draw(self.v[x], self.v[y], n)
        elif top == 0xE and kk == 0xA1:
            if self.v[x] not in self.keys:
                self.pc += 2
        elif top == 0xF and kk == 0x07:
            self.v[x] = self.delay
        elif top == 0xF and kk == 0x15:
            self.delay = self.v[x]
        elif top == 0xF and kk == 0x65:
            for register in range(x + 1):
                self.v[register] = self.mem[self.i + register]
            if self.quirks.increment_i:
                self.i = (self.i + x + 1) & 0xFFF
        else:
            raise AssertionError(f"unsupported {op:04X} at {at:04X}")
        return at


def boot(image: bytes, quirks: Quirks, allow_native: bool = False) -> Chip8:
    cpu = Chip8(image, quirks, allow_native)
    for _ in range(100):
        if cpu.pc == 0x20A:
            return cpu
        cpu.step()
    raise AssertionError("Videodraw did not reach its cursor loop")


def iterate(cpu: Chip8, key: int | None) -> tuple[int, int, int, bytes]:
    assert cpu.pc == 0x20A
    cpu.keys = set() if key is None else {key}
    left_loop_start = False
    for _ in range(100):
        at = cpu.step()
        if at == 0x20A:
            left_loop_start = True
        if cpu.pc == 0x20C:
            cpu.delay = 0
        if left_loop_start and cpu.pc == 0x20A:
            cpu.keys.clear()
            return cpu.v[0], cpu.v[1] & 63, cpu.v[2] & 31, bytes(cpu.screen)
    raise AssertionError("Videodraw cursor iteration did not complete")


def pixel(screen: bytes, x: int, y: int) -> bool:
    return bool(screen[y * 8 + x // 8] & (0x80 >> (x & 7)))


def run_scenario(
    image: bytes,
    quirks: Quirks,
    keys: tuple[int | None, ...],
    allow_native: bool = False,
) -> tuple[list[tuple[int, int, int, bytes]], Chip8]:
    cpu = boot(image, quirks, allow_native)
    return [iterate(cpu, key) for key in keys], cpu


def reachable_opcodes(image: bytes) -> dict[int, int]:
    todo, found, end = [0x200], {}, 0x200 + len(image)
    while todo:
        pc = todo.pop()
        if pc in found or not 0x200 <= pc + 1 < end:
            continue
        op = int.from_bytes(image[pc - 0x200 : pc - 0x1FE], "big")
        found[pc] = op
        top, nnn, kk = op >> 12, op & 0xFFF, op & 0xFF
        if top == 1:
            todo.append(nnn)
        elif top in (3, 4, 5, 9) or top == 0xE and kk in (0x9E, 0xA1):
            todo.extend((pc + 2, pc + 4))
        elif top == 0xB:
            raise AssertionError(f"reachable Bnnn at {pc:04X}")
        else:
            todo.append(pc + 2)
    return found


def check_cfg(original: bytes, fixed: bytes) -> int:
    assert original[0x36:0x3C] == bytes.fromhex("01F803BBE2D4")
    original_found = reachable_opcodes(original)
    assert original_found[0x206] == 0x0236
    assert 0x236 not in original_found

    found = reachable_opcodes(fixed)
    assert found[0x206] == 0x6000
    assert found[0x234] == 0x1250
    assert set(range(0x250, 0x25A, 2)) <= found.keys()
    assert not set(range(0x236, 0x23C, 2)) & found.keys()
    for pc, op in found.items():
        top, n = op >> 12, op & 0xF
        if top == 0 and op not in (0x00E0, 0x00EE):
            raise AssertionError(f"reachable native 0NNN at {pc:04X}: {op:04X}")
        if top == 8 and n in (6, 0xE):
            raise AssertionError(f"reachable ambiguous shift at {pc:04X}: {op:04X}")
    return len(found)


def check_behavior(original: bytes, fixed: bytes) -> int:
    keys = (None, 5, None, 6, None, 8, None, 0, None, 5, 4, None, 2, None)
    reference, original_cpu = run_scenario(original, QUIRKS[0], keys, True)
    assert original_cpu.native_entries == [(0x206, 0x236)]

    for quirks in QUIRKS:
        actual, fixed_cpu = run_scenario(fixed, quirks, keys)
        assert actual == reference
        assert not fixed_cpu.native_entries

    assert reference[1][0] == 5 and pixel(reference[1][3], 0, 0)
    assert reference[4][1:3] == (1, 0) and pixel(reference[4][3], 1, 0)
    assert reference[6][1:3] == (1, 1) and pixel(reference[6][3], 1, 1)
    assert reference[7][0] == 0 and not pixel(reference[7][3], 1, 1)
    assert reference[11][1] == 0
    assert reference[13][2] == 0
    return len(keys) * len(QUIRKS)


def validate_openstudio2(image: bytes, os2: Path) -> str:
    test_file, asm_file = os2 / "test_firmware.py", os2 / "openstudio2.asm"
    if not test_file.is_file() or not asm_file.is_file():
        return f"skipped (not found at {os2})"

    sys.path.insert(0, str(os2))
    sys.modules.pop("build", None)
    spec = importlib.util.spec_from_file_location("os2_videodraw_validation", test_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cpu = module.chip8_cpu({0x0200: image})
    symbols = module.define_symbols(asm_file.read_text(encoding="utf-8").splitlines())

    def boundary() -> bool:
        return cpu.r[cpu.p] == symbols["interpreter"] and cpu.r[5] == 0x120A

    def step_checked() -> None:
        if cpu.r[cpu.p] == symbols["unsupported"]:
            raise AssertionError(f"OpenStudio2 unsupported trap with R5={cpu.r[5]:04X}")
        cpu.step()
        cpu.memory[0x08B2] = 0

    for boot_steps in range(100_000):
        if boundary():
            break
        step_checked()
    else:
        raise AssertionError("OpenStudio2 did not reach the Videodraw cursor loop")

    def one_loop(key: int | None) -> None:
        cpu.keypad_a = set() if key is None else {key}
        left = False
        for _ in range(100_000):
            step_checked()
            if not boundary():
                left = True
            if left and boundary():
                cpu.keypad_a.clear()
                return
        raise AssertionError("OpenStudio2 Videodraw loop did not complete")

    one_loop(None)
    assert not any(cpu.memory[0x0900:0x0A00])
    one_loop(5)
    assert cpu.memory[0x08A0] == 5 and cpu.memory[0x0900] == 0x80
    one_loop(6)
    assert cpu.memory[0x08A1] == 1
    one_loop(None)
    assert cpu.memory[0x0900] == 0xC0
    one_loop(8)
    assert cpu.memory[0x08A2] == 1
    one_loop(None)
    assert cpu.memory[0x0908] == 0x40
    one_loop(0)
    assert cpu.memory[0x08A0] == 0 and cpu.memory[0x0908] == 0

    cpu.memory[0x08A0:0x08A3] = bytes((5, 0, 0))
    cpu.memory[0x0900:0x0A00] = bytes(256)
    one_loop(4)
    assert cpu.memory[0x08A1] == 63
    one_loop(None)
    assert cpu.memory[0x0900] == 0x80 and cpu.memory[0x0907] == 0x01
    one_loop(2)
    assert cpu.memory[0x08A2] == 31
    one_loop(None)
    assert cpu.memory[0x09FF] == 0x01
    return f"passed ({boot_steps + 1} CDP1802 instructions to cursor loop; draw/erase/move/wrap)"


def crc16_ccitt(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            if value & 0x8000:
                value = ((value << 1) ^ 0x1021) & 0xFFFF
            else:
                value = value << 1 & 0xFFFF
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openstudio2", type=Path, default=WORKSPACE / "OpenStudio2")
    args = parser.parse_args()

    original = DEFAULT_INPUT.read_bytes()
    assert len(original) == ORIGINAL_LENGTH
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256

    fixed = DEFAULT_OUTPUT.read_bytes()
    assert fixed == apply_patch(original)
    assert hashlib.sha256(fixed).hexdigest() == FIXED_SHA256

    cfg_count = check_cfg(original, fixed)
    scenario_count = check_behavior(original, fixed)
    print(f"reproducible image: passed ({FIXED_SHA256}; {len(fixed)} bytes)")
    print("source identity: passed (local guarded original)")
    print(f"static CFG: passed ({cfg_count} reachable instructions; no native 0NNN/ambiguous shifts)")
    print(f"modeled behavior: passed ({scenario_count} scenario/profile combinations)")
    print(f"OpenStudio2 firmware simulation: {validate_openstudio2(fixed, args.openstudio2)}")
    print(f"fixed CRC32: {zlib.crc32(fixed):08X}")
    print(f"fixed CRC16-CCITT: {crc16_ccitt(fixed):04X}")


if __name__ == "__main__":
    main()
