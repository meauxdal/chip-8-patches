# Videodraw Chip 8 portable fix

The accepted 256-byte payload has SHA-256
`c3d5e465fdba6c275ab02fbef114fa4f69f9cac26edddc10d05326e195d8a9be`.
It is also verified as the payload following the 512-byte interpreter in the
768-byte archival object. The fixed image has SHA-256
`2e2f85723f85786b668f37e7989b743f4f7f75dae89e098b714c9f8ba51ba1be`.

## Patch

The only reachable native call, `0206: 0236`, selects VIP framebuffer page `03`
and restores the CDP1802 X register. A portable interpreter owns its framebuffer,
so the call is replaced by `6000`, preserving the program-visible V0 value.

The original relies on sprite wrapping when coordinates cross a screen edge.
`0234: 120A` becomes `1250`, routing each loop through ten bytes placed in
unreachable capture residue at `0250-0259`. They mask V1 to 0-63 and V2 to 0-31,
then return to `020A`, making wrapping and clipping interpreters agree. VB is
scratch; any logic-op effect on VF is overwritten by the following draw.

## Evidence

The validator checks the guarded local payload, reproduction, reachable control
flow, drawing, erasing, four directions, four edge crossings, 56 quirk/profile
scenarios, and the current OpenStudio2 firmware path. Controls are 0 erase, 5 draw,
and 2/4/6/8 move up/left/right/down.
