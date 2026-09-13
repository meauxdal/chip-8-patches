# Keypad Test portable fix

The 114-byte source is identified in the CHIP-8 database by SHA-1
`0ebc4b92c6059d6193565644fb00108161d03d23`.
The fixed image has SHA-256
`4132032f1d3874c8b6ad7728b1e402ba1b6330db1f775a5e858ae3f9599a6a23`.

## Patch

The coordinate-table helpers use `820E` and `8206` to double and restore V2.
Those encodings shift V2 only on interpreters that ignore the Y nibble. Under
original COSMAC VIP semantics they shift V0 into V2, corrupting the table index
on the first pass.

The four instructions at `022C`, `0230`, `0238`, and `023C` are changed to
`822E`, `8226`, `822E`, and `8226`. Explicitly naming V2 as both operands
preserves the program's behavior under both shift conventions. No other bytes
change, including the program's deliberate self-modifying reset effect.
