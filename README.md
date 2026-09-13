# Portable CHIP-8 patches

Archival builders and validation notes for CHIP-8 fixes. Each builder discovers
the documented source ROM by its CHIP-8 database SHA-1, checks every
replaced byte, and writes the portable image without modifying the original.

| Title | Original and fixed images | Technical note |
| --- | --- | --- |
| Bingo | `bingo/` | [docs/bingo.md](docs/bingo.md) |
| Clock Program | `clock-program/` | [docs/clock-program.md](docs/clock-program.md) |
| Craps | `craps/` | [docs/craps.md](docs/craps.md) |
| Keypad Test | `keypad-test/` | [docs/keypad-test.md](docs/keypad-test.md) |
| Tick-Tack-Toe | `tick-tack-toe/` | [docs/tick-tack-toe.md](docs/tick-tack-toe.md) |
| Videodraw | `videodraw/` | [docs/videodraw.md](docs/videodraw.md) |
| Wipe Off | `wipe-off/` | [docs/wipe-off.md](docs/wipe-off.md) |

Pinball is a VIP-exclusive CHIP-8 title, but fixing it is beyond the
scope of this project. See [docs/pinball.md](docs/pinball.md).

Each title directory contains the original, the fixed image, and the scripts 
needed to reproduce and validate it.

Rebuild and check a title from the repository root:

```text
python bingo/build.py
python bingo/build.py --check
python bingo/validate.py
```

The other title directories use the same commands.
