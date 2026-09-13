#!/usr/bin/env python3
"""Check the reproducible Wipe Off image and its two preserved code regions."""

from build import DEFAULT_INPUT, DEFAULT_OUTPUT, apply_patch


original = DEFAULT_INPUT.read_bytes()
fixed = DEFAULT_OUTPUT.read_bytes()
assert fixed == apply_patch(original)
assert fixed[0x1E:0x20] == bytes.fromhex("67 14")
assert fixed[0xBA:0xCA] == bytes.fromhex("D3 45 73 05 F1 29 D3 45 73 05 F2 29 D3 45 12 C8")
print("reproducible one-byte patch: passed")
print("20-ball counter and final-score routine: passed")
