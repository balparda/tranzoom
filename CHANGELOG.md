<!-- SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Changelog

All notable changes to this project will be documented in this file.

- [Changelog](#changelog)
  - [V.V.V - YYYY-MM-DD - Placeholder](#vvv---yyyy-mm-dd---placeholder)
  - [1.1.0 - 2026-05-14](#110---2026-05-14)
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

## 1.1.0 - 2026-05-14

- Added
  - **File-path frame input**: `mandel gen`, `zoom ai`, and `zoom manual` now accept an existing tranZoom PNG file path as the `CENTER_RE` positional argument. When a path is given, the frame coordinates are read from the image's embedded metadata (`tranzoom:frame:*` PNG text chunks), and the other frame arguments (`CENTER_IM`, `F_WIDTH`, `F_HEIGHT`) are ignored. This makes it easy to resume or re-render from any previously saved image.
  - `zoom ai` command: AI-guided Mandelbrot zoom search using a local LLM vision model (via LMStudio). Renders each frame, divides it into 9 sectors using a thirds grid overlay, sends the image to the model for scoring, and navigates toward the most interesting sector. Runs in an infinite loop until Ctrl+C or `--max-steps` is reached.
  - `zoom manual` command: Manually-guided Mandelbrot zoom search. Same iterative loop and frame navigation as `zoom ai`, but the user enters the direction (1–9, numpad layout) at each step instead of an LLM.
  - `zoom ai --query` / `-q` flag: optional natural-language targeted search query sent to the LLM alongside the default fractal-quality scoring prompt, enabling targeted search for specific visual features.
  - `zoom ai --reason/--no-reason` flag: when enabled, the LLM includes a short textual explanation for each sector's score (useful for debugging); disabled by default for speed.
  - `zoom ai --memory` flag: number of previous AI steps the LLM retains in its chat history; `0` means stateless (each call is independent); default is `5`; max is `30`.
  - `-n/--max-steps` flag on both `zoom ai` and `zoom manual`: maximum number of zoom steps to run; `0` means unlimited (run until Ctrl+C); default is `0`.
  - `--iterm/--no-iterm` flag on `zoom ai`, `zoom manual`, and `mandel gen` / `mandel read`: when enabled on macOS + iTerm2, prints the rendered image inline in the terminal using the iTerm2 inline image protocol.
  - Full set of AI model flags on the `zoom` global callback (imported from `transai`): `--model` / `-m`, `--spec-tokens`, `--seed`, `--context` / `-c`, `--temperature` / `-x`, `--gpu`, `--gpu-layers`, `--fp16`, `--use-mmap`, `--flash`, `--kv-cache`, `--timeout`.
  - `mandel read` command: reads an existing tranZoom PNG and pretty-prints its embedded metadata (frame coordinates, magnification, palette, precision, LLM evaluation data, etc.). Optionally displays the image inline with `--iterm`.
  - `Fractal` enum (`core/frame.py`): all `Frame` objects now carry their fractal type; `Frame.FromCoords()` and `Frame.FromCenter()` require a `Fractal` argument as the first parameter.
  - Image SHA256 hash now embedded in PNG metadata under key `tranzoom:image:hash`.
  - Fractal type now embedded in PNG metadata under key `tranzoom:frame:fractal`.
  - Full LLM evaluation metadata embedded in AI-evaluated images: model name, temperature, seed, memory setting, reasoning flag, setup and image prompts, extra query, zoom step count, and full JSON evaluation result — all under `tranzoom:llm:*` keys.
  - `MakeImagePath()` utility in `core/image.py`: centralizes image file path construction with optional serial-number suffix for uniqueness in zoom sessions.
  - `DrawThirdsInfoOverlay()` in `core/image.py`: draws the 3×3 sector grid with green sector number labels on top of a rendered image (used as AI input).
  - `DrawCardinalInfoOverlay()` in `core/image.py`: draws white grid lines and green directional circles/labels (N, NE, E, …) for the 8 cardinal and ordinal directions (used to visualize movement choices).
  - `AddEvaluationMetaToImage()` in `core/image.py`: injects LLM or human evaluation data into a PNG's metadata without re-rendering.
  - `PrintITerm2()` in `core/image.py`: emits an image to the terminal using the iTerm2 inline image protocol.
  - `PixelPalette()` in `core/image.py`: extracted public helper that maps a `[0.0, 1.0]` position to an `(R, G, B)` tuple for a given palette.
  - `core/queries.py` module (new): AI prompt templates (`AI_SETUP_THIRDS_SCORING_PROMPT`, `AI_IMAGE_THIRDS_SCORING_PROMPT`, targeted search blocks) and Pydantic models for structured LLM responses (`SectorEvaluation`, `SectorCompleteEvaluation`, `ZoomSectorScoring`, `ZoomSectorCompleteScoring`). Includes `FinalScore()` with configurable `target_weight` for blending fractal quality and targeted-search scores.
  - `core/ai.py` module (new): implements `ZoomLoop()` and `ManualLoop()` — the main iterative zoom session logic with frame navigation, image rendering, AI calls, metadata saving, and Ctrl+C handling.
  - `cli/aicommand.py` module (new): registers the `zoom ai` and `zoom manual` commands with the `zoom` Typer app.
  - `pydantic` added as a production dependency (used by `core/queries.py` for structured AI output parsing).
  - `ExactInputType` type alias (`str | float | gmpy2.mpq`) in `core/frame.py`: documents the accepted input types for `Frame` coordinate arguments.
  - Zoom navigation constants in `core/frame.py`: `DEFAULT_MPQ_ZOOM` (zoom factor per step), `DEFAULT_MPQ_STEP_DIRECT`, `DEFAULT_MPQ_STEP_DIAGONAL` (frame-center shift magnitudes for cardinal and diagonal moves).
  - `DEFAULT_MANDELBROT_FRAME` and `DEFAULT_FRAMES` dict in `core/frame.py` replace the old `DEFAULT_FRAME` constant; `DEFAULT_FRAMES[Fractal.MANDELBROT]` gives the standard whole-set frame.

- Changed
  - `zoom` app image size is now fixed at 512×512 (the `--width`/`--height` global flags were removed from the `zoom` CLI; they remain on `mandel`). AI and manual zoom sessions always produce square 512×512 images.
  - `Frame.FromCoords()` and `Frame.FromCenter()` now require a `Fractal` argument as the first positional parameter.
  - `DEFAULT_FRAME` in `core/frame.py` renamed to `DEFAULT_MANDELBROT_FRAME`; a new `DEFAULT_FRAMES` dict indexed by `Fractal` enum is provided.
  - `MAX_IMAGE_SIZE` in `core/frame.py` increased from 8192 to 16384 (`16 × 1024`).
  - Image path generation logic extracted from `cli/gencommand.py` into `core/image.py` (`MakeImagePath()`); supports an optional serial-number suffix for uniqueness within a session.
  - CLI argument constants in `cli/base.py` renamed from `*_OPTION` to `*_ARGUMENT` (`FRAME_CENTER_RE_ARGUMENT`, `FRAME_CENTER_IM_ARGUMENT`, `FRAME_WIDTH_ARGUMENT`, `FRAME_HEIGHT_ARGUMENT`) to reflect that they are positional Typer arguments, not options.
  - `zoom` app help text updated to reflect real AI-guided zoom functionality.
  - `TranZoomAIConfig` dataclass (in `zoom.py`) extends `TranZoomConfig` with all AI model configuration fields; `zoom` callback now creates a `TranZoomAIConfig` context object.
  - `_MPQ_TWO` and `_MPQ_MAX_IMAGE_SIZE` constants in `core/frame.py` now use `gmpy2.mpq('…')` string construction for improved clarity.

- Fixed
  - `mandel gen` image path construction now validates the prefix against path traversal (directory separators) through the shared `MakeImagePath()` utility.

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
