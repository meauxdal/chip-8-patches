#!/usr/bin/env python3
"""Reproducible behavioral and portability checks for the Bingo fix."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from build import DEFAULT_INPUT, DEFAULT_OUTPUT, ORIGINAL_SHA256, apply_patch


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
    def __init__(self, image: bytes, quirks: Quirks = QUIRKS[0]):
        self.mem = bytearray(4096)
        self.mem[0x200 : 0x200 + len(image)] = image
        self.v = [0] * 16
        self.i = 0
        self.pc = 0x200
        self.stack: list[int] = []
        self.delay = self.sound = 0
        self.keys: set[int] = set()
        self.screen = bytearray(256)
        self.randoms = iter([0x00, 0x10, 0x20, 0x30])
        self.native_entries: list[tuple[int, int, int]] = []
        self.quirks = quirks

    def native(self, target: int) -> None:
        """Model the original VIP helpers by their observable effects."""
        self.native_entries.append((self.pc - 2, target, self.i))
        if target == 0x03FF:
            self.i = 0x0700 | (self.i & 0xFF)
        elif target == 0x03F3:
            assert 0x0700 <= self.i <= 0x07FF
            source = self.i - 0x0700
            count = 0x100 - (self.i & 0xFF)
            self.screen[:count] = self.screen[source : source + count]
            self.i = (self.i + count) & 0xFFFF
        elif target == 0x0402:
            value, increment = self.mem[self.pc : self.pc + 2]
            self.pc += 2
            if 0x0700 <= self.i <= 0x07FF:
                self.screen[self.i - 0x0700] = value
            else:
                self.mem[self.i] = value
            self.i = (self.i + increment) & 0xFFFF
        elif target in (0x040E, 0x0414):
            register = self.mem[self.pc] & 0x0F
            increment = self.mem[self.pc + 1]
            self.pc += 2
            if target == 0x040E:
                self.v[register] = self.mem[self.i]
            else:
                self.mem[self.i] = self.v[register]
            self.i = (self.i + increment) & 0xFFFF
        elif target == 0x041A:
            self.i = (self.i - 1) & 0xFFFF
        else:
            raise AssertionError(f"unknown native call {target:03X}")

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
            self.v[x] = next(self.randoms, 0x40) & kk
        elif top == 0xD:
            self.draw(self.v[x], self.v[y], n)
        elif top == 0xE:
            pressed = self.v[x] in self.keys
            if kk == 0x9E and pressed or kk == 0xA1 and not pressed:
                self.pc += 2
        elif top == 0xF:
            if kk == 0x07:
                self.v[x] = self.delay
            elif kk == 0x15:
                self.delay = self.v[x]
            elif kk == 0x18:
                self.sound = self.v[x]
            elif kk == 0x1E:
                self.i = (self.i + self.v[x]) & 0xFFF
            elif kk == 0x29:
                self.i = self.v[x] * 5
                font = bytes.fromhex(
                    "F0909090F02060202070F010F080F0F010F010F09090F01010F080F010F0F080F090F0"
                    "F010204040F090F090F0F090F010F0F090F09090E090E090E0F0808080F0E0909090E0"
                    "F080F080F0F080F08080"
                )
                self.mem[: len(font)] = font
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


def run_calls(image: bytes, quirks: Quirks) -> tuple[Chip8, list[bytes]]:
    cpu, screens = Chip8(image, quirks), []
    cpu.keys = {0xA}
    released = False
    for count in range(2_000_000):
        at = cpu.step()
        if not released and at == 0x0396:
            cpu.keys.clear()
            released = True
        tick(cpu, count)
        if released and cpu.pc == 0x0208 and count > 1000:
            screens.append(bytes(cpu.screen))
            if len(screens) == 3:
                return cpu, screens
            cpu.keys, released = {0xA}, False
    raise AssertionError("manual-call scenario did not finish")


def run_verify(image: bytes, quirks: Quirks) -> Chip8:
    cpu = Chip8(image, quirks)
    cpu.pc = 0x02DE
    cpu.v[7] = 42
    cpu.mem[0x0454 + cpu.v[7]] = 1
    iterations = 0
    for _ in range(2_000):
        if cpu.pc == 0x031E:
            assert iterations == 3, f"Verify completed after {iterations} iterations"
            return cpu
        iterations += cpu.pc == 0x02F2
        cpu.step()
    raise AssertionError(f"Verify did not finish after {iterations} iterations")


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
        top, n, kk = op >> 12, op & 0xF, op & 0xFF
        if top == 0 and op not in (0x00E0, 0x00EE):
            raise AssertionError(f"reachable native 0NNN at {pc:04X}: {op:04X}")
        if top == 8 and n in (6, 0xE):
            raise AssertionError(f"reachable ambiguous shift at {pc:04X}: {op:04X}")
        if top == 0xF and kk == 0x0A:
            raise AssertionError(f"reachable Fx0A at {pc:04X}: {op:04X}")
    return len(found)


def validate_openstudio2(image: bytes, os2: Path) -> str:
    test_file, asm_file = os2 / "test_firmware.py", os2 / "openstudio2.asm"
    if not test_file.is_file() or not asm_file.is_file():
        return f"skipped (not found at {os2})"
    sys.path.insert(0, str(os2))
    sys.modules.pop("build", None)
    spec = importlib.util.spec_from_file_location("os2_bingo_validation", test_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cpu = module.chip8_cpu({0x0200: image})
    symbols = module.define_symbols(asm_file.read_text(encoding="utf-8").splitlines())
    cpu.keypad_b.add(1)  # CHIP-8 key A
    released = seen_program = False
    for steps in range(5_000_000):
        if cpu.r[cpu.p] == symbols["unsupported"]:
            raise AssertionError(f"OpenStudio2 unsupported trap with R5={cpu.r[5]:04X}")
        seen_program |= cpu.r[5] >= 0x1200
        if not released and cpu.r[5] == 0x1398:
            cpu.keypad_b.clear()
            released = True
        cpu.step()
        if steps % 100 == 0:
            cpu.memory[0x08B2] = max(0, cpu.memory[0x08B2] - 1)
            cpu.memory[0x08B3] = max(0, cpu.memory[0x08B3] - 1)
        if released and seen_program and cpu.r[5] == 0x1208 and steps > 10_000:
            number = cpu.memory[0x08A7]
            assert 1 <= number <= 75
            assert cpu.memory[0x1000 + 0x454 + number] == 1
            assert any(cpu.memory[0x0900:0x0A00])
            return f"passed ({steps + 1} CDP1802 instructions, called {number})"
    raise AssertionError("OpenStudio2 did not complete one manual call")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openstudio2", type=Path, default=WORKSPACE / "OpenStudio2")
    args = parser.parse_args()
    original, fixed = DEFAULT_INPUT.read_bytes(), DEFAULT_OUTPUT.read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256
    assert fixed == apply_patch(original), "fixed image is stale or not reproducible"

    cfg_count = check_cfg(fixed)
    reference_cpu, reference_calls = run_calls(original, QUIRKS[0])
    assert reference_cpu.native_entries, "reference scenario did not exercise native services"
    reference_verify = run_verify(original, QUIRKS[0])
    assert reference_verify.native_entries, "reference Verify scenario did not exercise native services"

    print(f"reproducible image: passed ({hashlib.sha256(fixed).hexdigest()})")
    print(f"static CFG: passed ({cfg_count} reachable instructions; no 0NNN/shift/Bnnn/Fx0A)")
    for quirks in QUIRKS:
        fixed_cpu, fixed_calls = run_calls(fixed, quirks)
        assert not fixed_cpu.native_entries
        assert fixed_calls == reference_calls
        fixed_verify = run_verify(fixed, quirks)
        assert not fixed_verify.native_entries
        counts = ", ".join(str(sum(value.bit_count() for value in screen)) for screen in fixed_calls)
        print(f"{quirks.name}: passed (manual-call pixels {counts}; Verify completed three iterations)")
    print(f"OpenStudio2 firmware simulation: {validate_openstudio2(fixed, args.openstudio2)}")


if __name__ == "__main__":
    main()
