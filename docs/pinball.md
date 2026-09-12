# VIP Pinball investigation

No portable patch was produced. This note preserves the completed reverse
engineering in case the work is revisited.

The two examined 1,536-byte images are byte-identical, load at `0200-07FF`, and
have SHA-256
`b69111849cf95731d18dfc0b56cb9543ea835105516bb7e348afa1910d0e6af1`.
The program matches Andrew Modla's Pinball listing in the RCA COSMAC VIP Game
Manual.

## Native interface

Reachable control flow contains 433 CHIP-8 instructions and 65 calls to nine
CDP1802 services. Thirty-seven calls carry inline parameters; 74 parameter bytes
must be treated as data rather than CHIP-8 opcodes.

| Entry | Derived service |
| --- | --- |
| `05E3` | Move the ball's framebuffer byte offset and bit mask in one of eight directions. |
| `0603` | XOR the selected framebuffer bit and skip the next CHIP-8 instruction when it was already set. |
| `0608` | Test the selected framebuffer bit without changing it and perform the same conditional skip. |
| `0625` | Replace `I`'s high byte with the VIP display page. |
| `0628` | Store an inline byte at `M[I]`, then add a second inline byte to `I`. |
| `0634` | Load an inline-selected V register from `M[I]`, then advance `I`. |
| `063A` | Store an inline-selected V register at `M[I]`, then advance `I`. |
| `0640` | Decrement `I`. |
| `0642` | Clear twenty bytes beginning at `I`, then advance past them. |

An instruction-level CDP1802 model passed 37,644 focused cases covering every
ball position and bit, movement modes, pixel tests and toggles, indexed memory
access, pointer boundaries, inline-operand advancement, and conditional return
PCs. This did not test a complete VIP interpreter, DMA or interrupt timing, full
gameplay, or hardware.

## Why work stopped

The indexed services are straightforward to translate, but the display services
are not. Standard CHIP-8 drawing is XOR-only, while Pinball directly overwrites
flipper bytes that may overlap the ball. The collision services also change
control flow by conditionally skipping the caller's next instruction. Preserving
both effects likely requires a shadow framebuffer or a broader game rewrite,
possibly exceeding a 2 KiB VIP memory target. The remaining effort was judged
disproportionate to this archive.
