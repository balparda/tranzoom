<!-- SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Changelog

All notable changes to this project will be documented in this file.

- [Changelog](#changelog)
  - [V.V.V - YYYY-MM-DD - Placeholder](#vvv---yyyy-mm-dd---placeholder)
  - [1.0.0 - 2026-05-08](#100---2026-05-08)

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

## 1.0.0 - 2026-05-08

Initial public release.

- `mandel gen` command: renders the Mandelbrot set to a PNG file given a center point and frame size
- Arbitrary-precision coordinate representation using `gmpy2.mpq` (exact rationals) — no floating-point error in coordinates at any zoom depth
- Automatic precision calculation: the `Frame.precision` property computes the minimum `mpfr` bits needed to distinguish adjacent pixels, based on zoom depth, up to 300,000 bits (~100k decimal digits)
- `gmpy2.mpfr` escape-time rendering with automatic context precision selection via `gmpy2.local_context()`
- Fast interior shortcuts: main cardioid and period-2 bulb algebraic tests skip the iterative escape test for known interior points
- Logarithmic auto-scaling of `max_iter` with magnification level (deeper zooms get more iterations)
- Progress bar (via `tqdm`) during rendering, showing per-row speed
- Smooth 16-color histogram-equalized exterior color palette (blue-to-yellow-to-brown cycling gradient); interior points (never escaped) are rendered as pure black
- Output images saved as `<prefix>[-<YYYYMMDDhhmmss>][-<SHA256-20>].png`; prefix defaults to `'mandel'` (global `--prefix` flag); date via `--date/--no-date`; 20-char SHA256 hash via `--hash/--no-hash`; directory via `-o/--out` flag
- `Frame` class with `FromCoords()` and `FromCenter()` constructors, `area`, `precision`, `magnification`, and `iterations` properties, and a human-readable `__str__` representation showing center and half-width in exact rational form
- `mandel markdown` command: auto-generates CLI documentation in Markdown
- `GetBasicDataFromPNG()` utility for round-trip PNG integrity verification (dimensions + hash) after rendering
- Example renders at 7 zoom levels saved as committed test data in `tests/data/images/` via `scripts/make_examples.sh`; seahorse-tail image hash pinned in `cli/base.py` for regression testing
- Global CLI options: `--version`, `--verbose` (0–3), `--color/--no-color`, `--width/-w`, `--height/-h` (4–8192 pixels, default 1024), `-o/--out` (output directory), `--prefix` (filename prefix, default `'mandel'`), `--date/--no-date`, `--hash/--no-hash`
- `transai` dependency included as the foundation for future AI/LLM-guided zoom features
