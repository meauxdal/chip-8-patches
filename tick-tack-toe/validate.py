#!/usr/bin/env python3
"""Reproducible behavior and portability checks for VIP Tick-Tack-Toe."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path

from build import DEFAULT_INPUT, DEFAULT_OUTPUT, FIXED_SHA256, SOURCES, apply_patch


WORKSPACE = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Quirks:
    name: str
    shift_vy: bool
    increment_i: bool
    wrap: bool
    logic_vf_zero: bool


QUIRKS = (
    Quirks("VIP", True, True, True, False),
    Quirks("CHIP-48-like", False, False, False, True),
    Quirks("mixed", True, False, False, False),
)


class Chip8:
    def __init__(self, image: bytes, quirks: Quirks = QUIRKS[0], seed_board: int | None = None):
        self.mem = bytearray(4096)
        self.mem[0x200 : 0x200 + len(image)] = image
        if seed_board is not None:
            self.mem[0x3F0:0x400] = bytes([seed_board]) * 16
        self.v = [0] * 16
        self.i = 0
        self.pc = 0x200
        self.stack: list[int] = []
        self.delay = self.sound = 0
        self.keys: set[int] = set()
        self.screen = bytearray(256)
        self.randoms = cycle((1, 2, 3, 4, 5, 6, 7, 0xA5))
        self.native_entries: list[tuple[int, int]] = []
        self.quirks = quirks

    def native(self, target: int) -> None:
        self.native_entries.append((self.pc - 2, target))
        if target != 0x02E4:
            raise AssertionError(f"unknown native call {target:03X}")
        self.mem[0x3F0:0x400] = bytes(16)

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
        op = int.from_bytes(self.mem[self.pc : self.pc + 2], "big")
        self.pc += 2
        nnn, x, y, n, kk = op & 0xFFF, (op >> 8) & 0xF, (op >> 4) & 0xF, op & 0xF, op & 0xFF
        top = op >> 12
        if op == 0x00E0:
            self.screen[:] = bytes(256)
        elif op == 0x00EE:
            self.pc = self.stack.pop()
        elif top == 0:
            self.native(nnn)
        elif top == 1:
            self.pc = nnn
        elif top == 2:
            self.stack.append(self.pc)
            self.pc = nnn
        elif top in (3, 4):
            equal = self.v[x] == kk
            if equal == (top == 3):
                self.pc += 2
        elif top in (5, 9):
            equal = self.v[x] == self.v[y]
            if equal == (top == 5):
                self.pc += 2
        elif top == 6:
            self.v[x] = kk
        elif top == 7:
            self.v[x] = (self.v[x] + kk) & 0xFF
        elif top == 8:
            if n == 0:
                self.v[x] = self.v[y]
            elif n in (1, 2, 3):
                self.v[x] = (self.v[x] | self.v[y], self.v[x] & self.v[y], self.v[x] ^ self.v[y])[n - 1]
                if self.quirks.logic_vf_zero:
                    self.v[0xF] = 0
            elif n == 4:
                total = self.v[x] + self.v[y]
                self.v[x], self.v[0xF] = total & 0xFF, int(total > 0xFF)
            elif n in (5, 7):
                a, b = (self.v[x], self.v[y]) if n == 5 else (self.v[y], self.v[x])
                self.v[x], self.v[0xF] = (a - b) & 0xFF, int(a >= b)
            elif n in (6, 0xE):
                value = self.v[y] if self.quirks.shift_vy else self.v[x]
                if n == 6:
                    self.v[x], self.v[0xF] = value >> 1, value & 1
                else:
                    self.v[x], self.v[0xF] = (value << 1) & 0xFF, value >> 7
            else:
                raise AssertionError(f"unsupported {op:04X} at {at:04X}")
        elif top == 0xA:
            self.i = nnn
        elif top == 0xB:
            self.pc = nnn + self.v[0]
        elif top == 0xC:
            self.v[x] = next(self.randoms) & kk
        elif top == 0xD:
            self.draw(self.v[x], self.v[y], n)
        elif top == 0xE:
            pressed = self.v[x] in self.keys
            if kk == 0x9E and pressed or kk == 0xA1 and not pressed:
                self.pc += 2
        elif top == 0xF:
            if kk == 0x07:
                self.v[x] = self.delay
            elif kk == 0x0A:
                if self.keys:
                    self.v[x] = min(self.keys)
                else:
                    self.pc = at
            elif kk == 0x15:
                self.delay = self.v[x]
            elif kk == 0x18:
                self.sound = self.v[x]
            elif kk == 0x1E:
                self.i = (self.i + self.v[x]) & 0xFFF
            elif kk == 0x29:
                self.i = self.v[x] * 5
            elif kk == 0x33:
                value = self.v[x]
                self.mem[self.i : self.i + 3] = bytes((value // 100, value // 10 % 10, value % 10))
            elif kk in (0x55, 0x65):
                if kk == 0x55:
                    self.mem[self.i : self.i + x + 1] = bytes(self.v[: x + 1])
                else:
                    self.v[: x + 1] = self.mem[self.i : self.i + x + 1]
                if self.quirks.increment_i:
                    self.i += x + 1
            else:
                raise AssertionError(f"unsupported {op:04X} at {at:04X}")
        else:
            raise AssertionError(f"unsupported {op:04X} at {at:04X}")
        return at


def tick(cpu: Chip8, count: int) -> None:
    if count % 20 == 0:
        cpu.delay = max(0, cpu.delay - 1)
        cpu.sound = max(0, cpu.sound - 1)


def run_startup(image: bytes, quirks: Quirks, seed: int) -> Chip8:
    cpu = Chip8(image, quirks, seed)
    for count in range(20_000):
        if cpu.pc == 0x0204 and count:
            assert cpu.mem[0x3F0:0x400] == bytes(16)
            return cpu
        cpu.step()
        tick(cpu, count)
    raise AssertionError("startup did not reach the first key wait")


def run_game(image: bytes, quirks: Quirks) -> tuple[int, bytes, bytes, int]:
    cpu = Chip8(image, quirks, 0xA5)
    moves = cycle((0, 0xA, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9))
    key_waits = 0
    for count in range(1_000_000):
        if cpu.pc == 0x0204:
            cpu.keys = {next(moves)}
            key_waits += 1
        else:
            cpu.keys.clear()
        cpu.step()
        tick(cpu, count)
        if cpu.pc in (0x0354, 0x0358):
            return cpu.pc, bytes(cpu.mem[0x3F0:0x3FA]), bytes(cpu.screen), key_waits
    raise AssertionError("game scenario did not reach a terminal display")


def reachable_opcodes(image: bytes) -> dict[int, int]:
    todo, found, end = [0x200], {}, 0x200 + len(image)
    while todo:
        pc = todo.pop()
        if pc in found or not 0x200 <= pc + 1 < end:
            continue
        op = int.from_bytes(image[pc - 0x200 : pc - 0x1FE], "big")
        found[pc] = op
        top, nnn, kk = op >> 12, op & 0xFFF, op & 0xFF
        if op == 0x00EE:
            continue
        if top == 1:
            todo.append(nnn)
        elif top == 2:
            todo.extend((nnn, pc + 2))
        elif top in (3, 4, 5, 9) or top == 0xE and kk in (0x9E, 0xA1):
            todo.extend((pc + 2, pc + 4))
        elif top == 0xB:
            raise AssertionError(f"reachable Bnnn at {pc:04X}")
        else:
            todo.append(pc + 2)
    return found


def check_cfg(image: bytes) -> int:
    found = reachable_opcodes(image)
    for pc, op in found.items():
        top, n = op >> 12, op & 0xF
        if top == 0 and op not in (0x00E0, 0x00EE):
            raise AssertionError(f"reachable native 0NNN at {pc:04X}: {op:04X}")
        if top == 8 and n in (6, 0xE):
            raise AssertionError(f"reachable ambiguous shift at {pc:04X}: {op:04X}")
    return len(found)


def validate_openstudio2(image: bytes, os2: Path) -> str:
    test_file, asm_file = os2 / "test_firmware.py", os2 / "openstudio2.asm"
    if not test_file.is_file() or not asm_file.is_file():
        return f"skipped (not found at {os2})"
    sys.path.insert(0, str(os2))
    sys.modules.pop("build", None)
    spec = importlib.util.spec_from_file_location("os2_tictactoe_validation", test_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cpu = module.chip8_cpu({0x0200: image})
    symbols = module.define_symbols(asm_file.read_text(encoding="utf-8").splitlines())
    cpu.memory[0x13F0:0x1400] = bytes([0xA5]) * 16
    for steps in range(500_000):
        if cpu.r[cpu.p] == symbols["unsupported"]:
            raise AssertionError(f"OpenStudio2 unsupported trap with R5={cpu.r[5]:04X}")
        cpu.step()
        if cpu.r[5] == 0x1204 and any(cpu.memory[0x0900:0x0A00]):
            assert cpu.memory[0x13F0:0x1400] == bytes(16)
            return f"passed ({steps + 1} CDP1802 instructions to first key wait)"
    raise AssertionError("OpenStudio2 did not reach the first key wait")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openstudio2", type=Path, default=WORKSPACE / "OpenStudio2")
    args = parser.parse_args()

    original = DEFAULT_INPUT.read_bytes()
    assert SOURCES[hashlib.sha256(original).hexdigest()] == len(original)
    fixed = DEFAULT_OUTPUT.read_bytes()
    assert fixed == apply_patch(original)
    assert hashlib.sha256(fixed).hexdigest() == FIXED_SHA256

    cfg_count = check_cfg(fixed)
    print(f"reproducible image: passed ({hashlib.sha256(fixed).hexdigest()}; {len(fixed)} bytes)")
    print("source identity: passed (local guarded original)")
    print(f"static CFG: passed ({cfg_count} reachable instructions; no 0NNN/shift/Bnnn)")

    reference_start = run_startup(original, QUIRKS[0], 0xA5)
    assert reference_start.native_entries == [(0x0200, 0x02E4)]
    reference_game = run_game(original, QUIRKS[0])
    for quirks in QUIRKS:
        fixed_start = run_startup(fixed, quirks, 0xA5)
        assert not fixed_start.native_entries
        assert bytes(fixed_start.screen) == bytes(reference_start.screen)
        assert fixed_start.v == reference_start.v
        assert fixed_start.i == reference_start.i
        game = run_game(fixed, quirks)
        assert game == reference_game
        pixels = sum(value.bit_count() for value in game[2])
        print(f"{quirks.name}: passed (terminal {game[0]:04X}; {pixels} pixels; {game[3]} key waits)")

    print(f"OpenStudio2 firmware simulation: {validate_openstudio2(fixed, args.openstudio2)}")


if __name__ == "__main__":
    main()
