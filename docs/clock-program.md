# Clock Program portable fix

The 280-byte source is identified in the CHIP-8 database by SHA-1
`016345d75eef34448840845a9590d41e6bfdf46a`.
The fixed image has SHA-256
`bf2d6d3bdcaefa4997ac81d40790adccb58be5c264b917b8f6a3c355123d98a7`.

## Patch

The original minute interval waits for 59 delay-timer ticks and then calls a
CDP1802 countdown at `02D8`. That routine costs 1,506 CDP1802 machine cycles, or
about 6.842 ms at the documented 1.7609 MHz VIP clock.

The patch changes `0252: 6D3B` to `6D3C`, waiting for 60 timer ticks, and changes
`0266: 02D8` to `1252`, bypassing the machine-code delay and starting the next
interval. The native bytes remain as unreachable archival data. The seven `Fx0A`
instructions are unchanged; press/release handling belongs to the interpreter.