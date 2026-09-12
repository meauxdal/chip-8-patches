# Portable CHIP-8 patches

Archival builders and validation notes for four interpreter-specific CHIP-8
programs. Each builder accepts only the documented source hash, checks every
replaced byte, and writes the portable image without modifying the original.

| Title | Original and fixed images | Technical note |
| --- | --- | --- |
| Bingo | `bingo/` | [docs/bingo.md](docs/bingo.md) |
| Clock Program | `clock-program/` | [docs/clock-program.md](docs/clock-program.md) |
| VIP Tick-Tack-Toe | `tick-tack-toe/` | [docs/tick-tack-toe.md](docs/tick-tack-toe.md) |
| Videodraw Chip 8 | `videodraw/` | [docs/videodraw.md](docs/videodraw.md) |

The abandoned Pinball investigation is summarized in
[docs/pinball.md](docs/pinball.md); no patch or fixed image was produced.

Each title directory contains the canonical original copied from the RCA Studio II
full set, the fixed image, and the scripts needed to reproduce and validate it.
Alternate input paths may still be passed on the command line.

Rebuild and check a title from the repository root:

```text
python bingo/build.py
python bingo/build.py --check
python bingo/validate.py
```

The other title directories use the same commands.
