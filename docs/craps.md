# Craps portable fix

The 192-byte source is identified in the CHIP-8 database by SHA-1
`35158696bd94ea22ef34e899fff1f15f7154d4fd`.
The fixed 247-byte image has SHA-256
`2dee82081ef51e77187ff83d931288f2ec3c732b382f7c43ed068b4809ae735a`.

The widely circulated filename misspells the author as Camerlo Cortez. Other
catalogues credit Carmelo Cortez, which is the spelling used for the fixed image.

## Defect

The routine at `0258` sets `I` to `02F0` and draws seven bytes at `(V1, 8)`.
The source image ends at `02BF`, so those bytes are absent. Their contents depend
on how an interpreter initializes memory or what a previously loaded program left
behind. The program consequently shows blank or arbitrary backgrounds behind the
two correctly drawn numeral sprites.

## Patch

The builder pads `02C0-02EF` with zeroes and adds this sprite at `02F0-02F6`:

```text
FF 81 81 81 81 81 FF
```

This is a reconstructed 8-by-7 rectangular frame, not a recovered primary-source
byte sequence. Its geometry follows directly from the program: the frame routine
draws seven rows at `(8, 8)` and `(18, 8)`, while the roll routine draws each 4-by-5
hex-font numeral one pixel inside at `(9, 9)` and `(19, 9)`. The patch changes no
instructions or game logic; it only makes the referenced graphics data explicit
and independent of interpreter memory state.
