# VIP Tick-Tack-Toe portable fix

The included original is the 470-byte manual-sized image with CHIP-8 database
SHA-1 `8c404dc15f854456cafe9b22fcdbaf16830ffde5`. The builder also accepts a
known 512-byte capture by its existing SHA-256 source guard when supplied
explicitly.
Their first 470 bytes match. Both produce the same 490-byte fixed image, SHA-256
`b54cd3243b58499ad747f7b1e46e377d38d3f9470e1a50c74c18034dcfb3fcad`.

The manual-sized program ends at `03D5`. In the 512-byte Hagley capture the
remaining 42 bytes are retained capture tail rather than part of that
manual-sized image; in particular, `03F0-03FF` is the sixteen-byte mutable
board/work area cleared by the startup native service.

## Patch

At startup, `0200: 02E4` calls CDP1802 code that clears the sixteen board bytes at
`03F0-03FF`. The patch replaces it with `13D6`, a jump to a twenty-byte CHIP-8
routine appended at `03D6-03E9`. The routine stores two zero bytes per pass,
reloads `I` so `Fx55` post-increment behavior is irrelevant, then jumps to the
original continuation at `0202`. A jump is used because the native service did
not consume a CHIP-8 stack entry.