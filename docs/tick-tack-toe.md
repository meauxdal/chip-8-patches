# VIP Tick-Tack-Toe portable fix

The included original is the 470-byte manual-sized image with SHA-256
`40474f473154e467ac9ece7e01656764cdbb16fe6884c6ecc4092ef5a7a7dec9`, and
the builder also accepts a known 512-byte capture with SHA-256
`22d6c108415ff9ed86c7c7fcdcf29563e923f954e06ac938a171d593964072d6`.
Their first 470 bytes match. Both produce the same 490-byte fixed image, SHA-256
`b54cd3243b58499ad747f7b1e46e377d38d3f9470e1a50c74c18034dcfb3fcad`.

## Patch

At startup, `0200: 02E4` calls CDP1802 code that clears the sixteen board bytes at
`03F0-03FF`. The patch replaces it with `13D6`, a jump to a twenty-byte CHIP-8
routine appended at `03D6-03E9`. The routine stores two zero bytes per pass,
reloads `I` so `Fx55` post-increment behavior is irrelevant, then jumps to the
original continuation at `0202`. A jump is used because the native service did
not consume a CHIP-8 stack entry.