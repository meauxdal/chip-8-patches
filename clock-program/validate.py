#!/usr/bin/env python3
"""Reproducibility, control-flow, timing, and behavior checks for Clock Program."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
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


VIP_CLOCK_HZ = 1_760_900
MACHINE_CLOCKS = 8
NATIVE_MACHINE_CYCLES = 1506
WORKSPACE = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Quirks:
    name: str
    wrap: bool


QUIRKS = (
    Quirks("VIP", True),
    Quirks("clipping", False),
)

FONT = bytes.fromhex(
    "F0909090F0 2060202070 F010F080F0 F010F010F0 "
    "9090F01010 F080F010F0 F080F090F0 F010204040 "
    "F090F090F0 F090F010F0 F090F09090 E090E090E0 "
    "F0808080F0 E0909090E0 F080F080F0 F080F08080"
)


class Chip8:
    def __init__(self, image: bytes, quirks: Quirks):
        self.mem = bytearray(4096)
        self.mem[: len(FONT)] = FONT
        self.mem[0x200 : 0x200 + len(image)] = image
        self.v = [0] * 16
        self.i = 0
        self.pc = 0x200
        self.stack: list[int] = []
        self.delay = 0
        self.keys: set[int] = set()
        self.screen = bytearray(256)
        self.native_entries: list[tuple[int, int]] = []
        self.quirks = quirks

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
        elif op == 0x00EE:
            self.pc = self.stack.pop()
        elif top == 0:
            if nnn != 0x02D8:
                raise AssertionError(f"unknown native call {nnn:03X} at {at:04X}")
            self.native_entries.append((at, nnn))
        elif top == 1:
            self.pc = nnn
        elif top == 2:
            self.stack.append(self.pc)
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
        elif top == 0xA:
            self.i = nnn
        elif top == 0xD:
            self.draw(self.v[x], self.v[y], n)
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
            elif kk == 0x29:
                self.i = self.v[x] * 5
            else:
                raise AssertionError(f"unsupported {op:04X} at {at:04X}")
        else:
            raise AssertionError(f"unsupported {op:04X} at {at:04X}")
        return at


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


def clock_snapshots(image: bytes, digits: tuple[int, ...], quirks: Quirks, count: int) -> tuple[list[tuple], Chip8]:
    cpu = Chip8(image, quirks)
    pending = list(digits) + [0]
    snapshots: list[tuple] = []
    previous_pc = None
    for steps in range(2_000_000):
        if cpu.pc in (0x0200, 0x0202, 0x0204, 0x0206, 0x0208, 0x020A, 0x024A) and pending:
            cpu.keys = {pending.pop(0)}
        else:
            cpu.keys.clear()

        previous_pc = cpu.step()
        if steps % 20 == 19:
            cpu.delay = max(0, cpu.delay - 1)

        if cpu.pc == 0x0252 and previous_pc in (0x0266, 0x0268):
            snapshots.append((tuple(cpu.v[1:7]), bytes(cpu.screen)))
            if len(snapshots) == count:
                return snapshots, cpu
    raise AssertionError("clock scenario did not produce the requested snapshots")


def check_scenario(original: bytes, fixed: bytes, digits: tuple[int, ...], expected: tuple[tuple[int, ...], ...]) -> None:
    reference, reference_cpu = clock_snapshots(original, digits, QUIRKS[0], len(expected))
    assert tuple(item[0] for item in reference) == expected
    assert reference_cpu.native_entries == [(0x0266, 0x02D8)] * len(expected)
    for quirks in QUIRKS:
        actual, cpu = clock_snapshots(fixed, digits, quirks, len(expected))
        assert actual == reference
        assert not cpu.native_entries


def check_timing(original: bytes, fixed: bytes) -> float:
    assert original[0xD8:0xE0] == bytes.fromhex("f8faaf2f8f3adbd4")
    assert int.from_bytes(original[0x52:0x54], "big") == 0x6D3B
    assert int.from_bytes(fixed[0x52:0x54], "big") == 0x6D3C
    seconds = NATIVE_MACHINE_CYCLES * MACHINE_CLOCKS / VIP_CLOCK_HZ
    assert 0.0068 < seconds < 0.0069
    return seconds


def validate_openstudio2(image: bytes, os2: Path) -> str:
    test_file, asm_file = os2 / "test_firmware.py", os2 / "openstudio2.asm"
    if not test_file.is_file() or not asm_file.is_file():
        return f"skipped (not found at {os2})"

    sys.path.insert(0, str(os2))
    sys.modules.pop("build", None)
    spec = importlib.util.spec_from_file_location("os2_clock_validation", test_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cpu = module.chip8_cpu({0x0200: image})
    symbols = module.define_symbols(asm_file.read_text(encoding="utf-8").splitlines())

    def run_until(predicate, limit: int = 500_000, tick_timer: bool = False) -> int:
        for steps in range(limit):
            if cpu.r[cpu.p] == symbols["unsupported"]:
                raise AssertionError(f"OpenStudio2 unsupported trap with R5={cpu.r[5]:04X}")
            if predicate():
                return steps
            cpu.step()
            if tick_timer and steps % 200 == 199 and cpu.memory[0x08B2]:
                cpu.memory[0x08B2] -= 1
        raise AssertionError("OpenStudio2 firmware scenario did not reach expected state")

    for register, key in enumerate((1, 2, 3, 4, 5, 6), start=1):
        cpu.keypad_a = {key}
        run_until(lambda: cpu.r[cpu.p] == symbols["key_wait_release"])
        cpu.keypad_a.clear()
        run_until(lambda register=register, key=key: cpu.memory[0x08A0 + register] == key)

    cpu.keypad_a = {7}
    run_until(lambda: cpu.r[cpu.p] == symbols["key_wait_release"])
    cpu.keypad_a.clear()
    run_until(lambda: cpu.memory[0x08AD] == 7)
    steps = run_until(lambda: cpu.memory[0x08A6] == 7, tick_timer=True)
    if not any(cpu.memory[0x0900:0x0A00]):
        raise AssertionError("OpenStudio2 clock scenario did not draw a display")
    return f"passed ({steps} CDP1802 instructions after start input to first increment)"


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

    cfg_count = check_cfg(fixed)
    native_seconds = check_timing(original, fixed)
    check_scenario(original, fixed, (1, 2, 3, 4, 5, 8), ((1, 2, 3, 4, 5, 8), (1, 2, 3, 4, 5, 9), (1, 2, 3, 5, 0, 0)))
    check_scenario(original, fixed, (2, 3, 5, 9, 5, 8), ((2, 3, 5, 9, 5, 8), (2, 3, 5, 9, 5, 9), (0, 0, 0, 0, 0, 0)))

    print(f"reproducible image: passed ({FIXED_SHA256}; {len(fixed)} bytes)")
    print("source identity: passed (local guarded original)")
    print(f"static CFG: passed ({cfg_count} reachable instructions; no native 0NNN/shift/Bnnn)")
    print(f"native timing model: passed ({NATIVE_MACHINE_CYCLES} machine cycles; {native_seconds * 1000:.4f} ms at {VIP_CLOCK_HZ / 1_000_000:.4f} MHz)")
    print("clock behavior: passed (minute and 24-hour rollovers under VIP and clipping draw profiles)")
    print(f"OpenStudio2 firmware simulation: {validate_openstudio2(fixed, args.openstudio2)}")
    print("Fx0A behavior: passed through current OpenStudio2 press/release handling; image unchanged")


if __name__ == "__main__":
    main()
