# Bingo portable fix

The 1,536-byte source (`0200-07FF`) is accepted only with SHA-256
`702676f43590720f95e5fc3c334a00a58478b0fca5c082f25c772f54abcaa65a`.
The fixed image has SHA-256
`d261441ae0e9241cf43cf33f6947e55ec7e9c9c038eb46ebff0668aa0433f5fb`.

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

## Evidence

The validator checks guarded reproduction, reachable control flow, and three
manual-call display sequences under VIP, CHIP-48-like, and mixed quirk profiles.
It also completes a manual call through the current OpenStudio2 firmware model.
An earlier intermediate was played successfully on physical OpenStudio2; the
final image adds the indexed store at `0310`/`0684` and was not separately recorded
on hardware.
