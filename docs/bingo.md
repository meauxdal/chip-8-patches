# Bingo portable fix

The 1,536-byte source (`0200-07FF`) is identified in the CHIP-8 database by
SHA-1 `08f70fe1c228d15a7a5f456840b5e0e56a51fd99`.
The fixed image has SHA-256
`d7e5cd2d5c070eb4d8476bd5a0e6fa3f255d84944fb39db461998bb1d7ab69d9`.

## Patch

The original uses thirteen calls to six CDP1802 services. Those services scroll
VIP display RAM, turn an offset into a physical display address, load or store a
selected V register through `I`, adjust `I`, and consume inline operand bytes.

Portable CHIP-8 cannot read or scroll the framebuffer. The patch instead records
called numbers and verification results in `068F-069E`, clears the display when a
scroll is required, and redraws the surviving game objects. New routines occupy
`04B0-068D` and provide initialization, called-number flags, indexed loads/stores,
decimal conversion, timer pacing, display reconstruction, and verification-row
history. All native call sites are replaced or made unreachable.

Every `Fx55`/`Fx65` use reloads `I` when its post-increment value could matter.
Ambiguous shifts are replaced by addition, coordinates remain in bounds, and the
CPU-speed delay loop is replaced by the delay timer. The fixed reachable program
contains no native `0NNN`, ambiguous shift, `Bnnn`, or `Fx0A` instruction.

The inline operands following the original native calls at `02F6` and `0310`
are executable after those calls return from portable helpers. They are replaced
with `7000` no-ops so Verify mode preserves its three-pass loop counter.
