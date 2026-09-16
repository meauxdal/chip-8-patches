# Videodraw Chip 8 portable fix

The accepted 256-byte payload is identified in the CHIP-8 database by SHA-1
`87939f2c59bf27d30fdc53dc53161b6c9ef8085c`.
It is also verified as the payload following the 512-byte interpreter in the
768-byte archival object. The fixed image has SHA-256
`2e2f85723f85786b668f37e7989b743f4f7f75dae89e098b714c9f8ba51ba1be`.

The first 80 bytes (`0200-024F`) also match the independently preserved
80-byte Video Display Drawing Game image, SHA-1
`12fccf60004f685c112fe3db3d3bcfba104cbcb1`. The remaining 176 bytes are
retained as part of the Hagley capture; no evidence supports a second program there.

## Patch

The only reachable native call, `0206: 0236`, selects VIP framebuffer page `03`
and restores the CDP1802 X register. A portable interpreter owns its framebuffer,
so the call is replaced by `6000`, preserving the program-visible V0 value.

The original relies on sprite wrapping when coordinates cross a screen edge.
`0234: 120A` becomes `1250`, routing each loop through ten bytes placed in
unreachable capture residue at `0250-0259`. They mask V1 to 0-63 and V2 to 0-31,
then return to `020A`, making wrapping and clipping interpreters agree. VB is
scratch; any logic-op effect on VF is overwritten by the following draw.

## Controls

- 5 draw
- 0 erase 
- 2/4/6/8 move up/left/right/down. 
- two non-opposites of the above keys for diagonal movement