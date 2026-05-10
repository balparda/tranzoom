<!-- SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Changelog

All notable changes to this project will be documented in this file.

- [Changelog](#changelog)
  - [V.V.V - YYYY-MM-DD - Placeholder](#vvv---yyyy-mm-dd---placeholder)
  - [1.0.0 - 2026-05-10](#100---2026-05-10)

This project follows a pragmatic versioning approach:

- **Patch**: bug fixes / docs / small improvements.
- **Minor**: new features or non-breaking changes.
- **Major**: breaking changes (command renames, incompatible output formats).

## V.V.V - YYYY-MM-DD - Placeholder

- Added
  - Placeholder for future changes.

- Changed
  - Placeholder for future changes.

- Fixed
  - Placeholder for future changes.

## 1.0.0 - 2026-05-10

Initial public release.

- `mandel gen` command: renders the Mandelbrot set to a PNG file given a center point and frame size
- Arbitrary-precision coordinate representation using `gmpy2.mpq` (exact rationals) — no floating-point error in coordinates at any zoom depth
- Automatic precision calculation: the `Frame.precision` property computes the minimum `mpfr` bits needed to distinguish adjacent pixels, based on zoom depth, up to 300,000 bits (~100k decimal digits)
- `gmpy2.mpfr` escape-time rendering with automatic context precision selection via `gmpy2.local_context()`
- Fast interior shortcuts: main cardioid and period-2 bulb algebraic tests skip the iterative escape test for known interior points
- Progress bar (via `tqdm`) during rendering, showing per-row speed
- Histogram-equalized exterior color palettes cycling 3 times across the escape-iteration range; interior points (never escaped) are rendered as pure black; four palettes ship out of the box (see `--palette` above)
- Output images saved as `<prefix>[-<YYYYMMDDhhmmss>][-<SHA256-20>].png`; prefix defaults to `'mandel'` (global `--prefix` flag); date via `--date/--no-date`; 20-char SHA256 hash via `--hash/--no-hash`; directory via `-o/--out` flag
- `Frame` class with `FromCoords()` and `FromCenter()` constructors, `area`, `precision`, `magnification`, and `iterations` properties, and a human-readable `__str__` representation showing center and half-width in exact rational form
- `mandel markdown` command: auto-generates CLI documentation in Markdown
- `GetBasicDataFromPNG()` utility for round-trip PNG integrity verification (dimensions + hash) after rendering
- Example renders at 7 zoom levels saved as committed test data in `tests/data/images/` via `scripts/make_examples.sh`; seahorse-tail image hash pinned in `cli/base.py` for regression testing
- Global CLI options: `--version`, `--verbose` (0–3), `--color/--no-color`, `--width/-w`, `--height/-h` (16–8192 pixels, default 1024), `-o/--out` (output directory), `--prefix` (filename prefix, default `'mandel'`), `--date/--no-date`, `--hash/--no-hash`, `--threads` (parallelism; default: all available CPU cores, capped at 16)
- Per-command options on `mandel gen`: `--iter/-i` (manual `max_iter` override; default: automatic adaptive search), `--palette` (color palette selection; default: `'blue-to-yellow-to-brown'`)
- Four built-in color palettes selectable via `--palette`: `'blue-to-yellow-to-brown'` (classic 16-stop gradient, default), `'lava'` (16-stop volcanic gradient), `'electric-ocean'` (32-stop abyss-to-magenta-to-lavender gradient), `'sunset'` (32-stop indigo-to-amber-to-wine gradient)
- Multi-process rendering using `concurrent.futures.ProcessPoolExecutor`: each CPU core renders an interleaved subset of rows, results are merged into the final image; single-process fallback when `--threads 1`
- Adaptive iteration pre-pass: when `--iter` is not set, a small 16×16 test render is performed first to estimate the optimal `max_iter` for the given frame (with a 1.5× safety margin), avoiding wasteful over-iteration
- `zoom` CLI stub registered as a console script (`poetry run zoom`) — placeholder for future AI-guided zoom features; not yet functional
- `transai` dependency included as the foundation for future AI/LLM-guided zoom features
