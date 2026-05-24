<!-- SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Changelog

All notable changes to this project will be documented in this file.

- [Changelog](#changelog)
  - [V.V.V - 2026-05-DD - Placeholder](#vvv---2026-05-dd---placeholder)
  - [1.5.0 - 2026-05-TBD](#150---2026-05-tbd)
  - [1.4.1 - 2026-05-21](#141---2026-05-21)
  - [1.4.0 - 2026-05-20](#140---2026-05-20)
  - [1.3.0 - 2026-05-16](#130---2026-05-16)
  - [1.2.0 - 2026-05-15](#120---2026-05-15)
  - [1.1.0 - 2026-05-14](#110---2026-05-14)
  - [1.0.0 - 2026-05-10](#100---2026-05-10)

This project follows a pragmatic versioning approach:

- **Patch**: bug fixes / docs / small improvements.
- **Minor**: new features or non-breaking changes.
- **Major**: breaking changes (command renames, incompatible output formats).

## V.V.V - 2026-05-DD - Placeholder

- Added
  - Placeholder for future changes.

- Changed
  - Placeholder for future changes.

- Fixed
  - Placeholder for future changes.

## 1.5.0 - 2026-05-24

- Added
  - **`SerializingFractalObject` base class** (`frame.py`): new abstract base for fractal objects that serialize to a canonical JSON form with a stable SHA-256 hash (`.json`, `.binary`, `.sha` properties + `FromJson()` static method). `Frame` and `ComputationParameters` now extend it, gaining `.sha` and `.binary`.
  - **`Frame.FromJson()` and `ComputationParameters.FromJson()`** static deserializers for round-trip JSON ↔ object conversion with optional hash verification.
  - **`RenderParameters` class** (`image.py`): new `SerializingFractalObject` that encapsulates all rendering parameters — file type, exterior palette, interior (Set) palette, mark coordinates/color/width, and overlay type. Replaces scattered individual arguments in the rendering API.
  - **`ZoomParameters` class** (`image.py`): new `SerializingFractalObject` for animation planning, encapsulating animation type, computation parameters, render parameters, magnification, frame count, duration, and loop count.
  - **`ImageOutputConfig` dataclass** (`image.py`): groups output naming and save parameters (path, date flag, hash flag, prefix) into a single runtime-only config object (not part of the DB schema, not hashed).
  - **`OverlayType` enum** (`image.py`): `GRID` and `CARDINAL` overlay types.
  - **Fractal database fully implemented** (`frdb.py`): the `FractalDatabase` now stores frames, computation parameters, render parameters, and video/GIF entries, plus path and data-hash indexes for fast lookup. New typed dictionaries: `FrameData`, `ComputationData`, `ImageCoreKey`, `ImageData`, `ZoomData`.
  - **`CoreComputeImage()` function** (`frdb.py`): new unified rendering primitive that integrates DB lookup/store, fractal computation, image rendering, overlay, and output into a single call.
  - **Mark options on `tranz zoom`**: `--mark`, `--mark-color`, `--mark-width` moved from `tranz zoom auto` to the shared `tranz zoom` subgroup callback — they now apply to `tranz zoom ai`, `tranz zoom manual`, and `tranz zoom auto`.
  - New PNG metadata keys for render parameters: `tranzoom:render:mark_re`, `tranzoom:render:mark_im`, `tranzoom:render:mark_color`, `tranzoom:render:mark_width`.
  - Grid overlay is now always drawn during `tranz zoom ai` and `tranz zoom manual` sessions (no separate flag needed).

- Changed
  - **Breaking**: Palette `blue-to-yellow-to-brown` renamed to `sahara`; default exterior palette changed to `sahara`.
  - **Breaking**: Palette `electric-ocean` renamed to `electric`.
  - **Breaking**: PNG metadata keys renamed: `tranzoom:image:palette` → `tranzoom:render:palette`; `tranzoom:image:set_palette` → `tranzoom:render:set_palette`; `tranzoom:image:overlay` (bool `"true"`/`"false"`) → `tranzoom:render:overlay` (`OverlayType` value or `"none"`). Images written by older versions will have stale metadata keys when read back by this version.
  - `MakeImageMeta()` now takes a `RenderParameters` object instead of individual palette/mark/overlay arguments.
  - Mandelbrot `Frame` objects now reject non-zero `point_re`/`point_im` values; that field is only meaningful for Julia Sets.
  - All image-generating commands (`tranz image mandel`, `tranz image julia`, `tranz zoom ai`, `tranz zoom manual`, `tranz zoom auto`) now route rendering through `CoreComputeImage()` and the open `FractalDatabase` instance.

- Fixed
  - Mark options (`--mark`, `--mark-color`, `--mark-width`) were only available for `tranz zoom auto`; they are now correctly exposed for all `tranz zoom` subcommands via the shared subgroup callback.

## 1.4.1 - 2026-05-21

- Added
  - Image stats (`max_lo`/`max_hi`, `min_lo`/`min_hi`, `ang_lo`/`ang_hi`, `imag_lo`/`imag_hi`) are now saved to PNG metadata under `tranzoom:image:stats:*` keys after rendering.

- Changed
  - Render log magnification display now uses `10^X magnitude` format instead of the old humanized decimal string (e.g., `10^3.53 magnitude` instead of `3.387 k magnification`).

- Fixed
  - **Multi-process interior coloring bug**: `FractalStats` from worker tasks was not being combined back into the final image in parallel renders, causing incorrect interior coloring (`--set` mode) when rendering with more than one CPU core (the default). Fixed in both `Mandelbrot()` and `Julia()`.
  - **`tranz zoom auto --col` option**: invalid color strings now raise a clear `ClickException` with a list of valid colors, instead of an opaque `KeyError`.

## 1.4.0 - 2026-05-20

- Added
  - **Grayscale palettes** (`grayscale`, `rgrayscale`): two new 8-stop grayscale gradient palettes designed for coloring interior Set points; `rgrayscale` (white-to-black, where white=deep interior, black=near boundary) is now the default `--set-palette`; `grayscale` is the reverse (black-to-white).
  - **Interior (Set) point coloring**: new `--set ALGORITHM` global flag enables smooth coloring of interior (Set) points using a separate `--set-palette` (default `rgrayscale`); supported algorithms: `min` (minimum `|z|` at max depth), `max` (maximum `|z|`), `angle` (angle of `z`), `imaginary` (imaginary-weighted average of `z`); the same histogram-equalization approach used for exterior points is applied, cycling the set-palette once across the Set interior; defaults to off (all-black interior).
  - New `SetHighlightAlgorithm` enum in `core/frame.py` with values `min`, `max`, `angle`, `imaginary`.
  - New PNG metadata keys `tranzoom:image:set_palette` and `tranzoom:image:color_set`: embedded in all images to record the interior palette used and whether interior coloring was enabled.
  - **`tranz zoom auto`** — new command that renders a GIF or MP4 zoom animation along a straight zoom-in path toward a given starting frame; specify the destination magnification exponent (`10^N` zoom) and pick any two of `--frames`, `--fps`, `--duration` to constrain the third; output format controlled by `--anim` (`gif` or `mp4`, default `gif`); GIF loop count via `--loop` (0 = infinite); optional intermediate frame saving via `--save-frames/--no-save-frames`.
  - **GIF animation support**: `WriteAnimatedGIF()` function in `core/image.py` saves a sequence of rendered PNG frames as an animated GIF via `PIL.Image.save(...)`; frame timing and loop count are configurable.
  - **MP4 video support**: `WriteVideoMP4()` function in `core/image.py` saves a sequence of rendered PNG frames as an H.264 MP4 video using `imageio-ffmpeg`; FPS is configurable.
  - New `FractalStats` dataclass in `core/image.py`: collects interior-point statistics during the adaptive pre-pass render — min/max of `|z|` magnitudes, min/max of angles, min/max of imaginary-weighted averages; stored in `Image.stats` after rendering.
  - New `AnimationType` enum in `core/image.py` with values `gif` and `mp4`.
  - New animation constants in `core/image.py`: `MIN_FRAMES`, `MAX_FRAMES`, `MIN_DURATION`, `MAX_DURATION`, `MIN_FPS`, `MAX_FPS`, `MIN_LOOP`, `MAX_LOOP`, `DEFAULT_LOOP`, `DEFAULT_ANIMATION_TYPE`, `DEFAULT_DEST_MAGNIFICATION_10`, `MAX_ZOOM_MAGNIFICATION_10`.
  - New animation PNG metadata keys embedded in each frame of a zoom animation: `tranzoom:image:animation`, `tranzoom:animation:frame:initial_width_re`, `tranzoom:animation:frame:initial_height_im`, `tranzoom:animation:zoom:magnitude`, `tranzoom:animation:zoom:magnitude_per_step`, `tranzoom:animation:zoom:magnification_per_step`, `tranzoom:animation:zoom:magnification_per_step_mpq`, `tranzoom:animation:duration`, `tranzoom:animation:frames`, `tranzoom:animation:steps`, `tranzoom:animation:fps`, `tranzoom:animation:loop`.
  - New pixel-statistics PNG metadata keys embedded in all images: `tranzoom:image:exterior:pixel_count`, `tranzoom:image:interior:pixel_count`, `tranzoom:image:exterior:histogram_summary`, `tranzoom:image:interior:histogram_summary`, `tranzoom:image:exterior:cumulative_histogram_summary`, `tranzoom:image:interior:cumulative_histogram_summary`, `tranzoom:image:set_point:min`, `tranzoom:image:set_point:max`.
  - New `ProduceFractalImage()` utility in `cli/base.py`: centralizes image rendering, saving, and iTerm2-printing logic, shared by all image and zoom commands.
  - New `MPQFromFloatApprox()` utility in `core/frame.py`: converts a float to a `gmpy2.mpq` rational approximation using `fractions.Fraction`.
  - New dependencies: `ImageIO>=2.37`, `imageio-ffmpeg>=0.6`, `numpy>=2.4` (for GIF/MP4 animation support).

- Changed
  - **Breaking**: `--palette`, `--set-palette`, and `--set` moved from the `tranz image` subgroup callback to the `tranz` global callback; they now apply to `tranz zoom ai`, `tranz zoom manual`, and `tranz zoom auto` commands as well; usage changes from `tranz image --palette NAME ...` to `tranz --palette NAME image ...`.
  - **Breaking**: `GetBasicDataFromPNG()` renamed to `GetBasicDataFromImage()` in `core/image.py` to reflect support for GIF and other formats; any code that calls this by name must be updated.
  - **Breaking**: `tranzoom:version` PNG metadata key removed; the version is no longer embedded in individual images to keep metadata stable across re-renders.
  - **Breaking**: `tranzoom:iter_depth:min`, `tranzoom:iter_depth:max`, and `tranzoom:iter_depth:search` PNG metadata keys renamed to `tranzoom:image:iter_depth:min`, `tranzoom:image:iter_depth:max`, and `tranzoom:image:iter_depth:search`; images written by older versions will have the old keys which are not recognized by this version.
  - **Breaking**: `Image.escape` array changed from unsigned int32 (`array.array('I')`) to signed int32 (`array.array('i')`); interior Set points are now stored as negative values `-(int(floor(scale * |z|)) + 1)`, enabling interior coloring; code that reads raw escape values must be updated.
  - **Breaking**: `Image.escape_range` property now returns a 4-tuple `(exterior_min, exterior_max, interior_min, interior_max)` instead of a 2-tuple; exterior values are non-negative; interior values (if any Set points exist) are negative.
  - `tranz zoom ai` and `tranz zoom manual` now propagate the active palette, set-palette, and set-points configuration into the zoom loop, enabling interior coloring during interactive zoom sessions.
  - `Image.AsPNG()` and `Image.AsPixels()` now accept `set_pal` and `set_points` parameters for interior coloring.

- Fixed
  - N/A

## 1.3.0 - 2026-05-16

- Added
  - **Julia Set fractal rendering**: new `tranz image julia` command renders a Julia Set image with arbitrary-precision arithmetic; the Julia constant `c` is set via `POINT_RE` and `POINT_IM` positional arguments (or loaded from an existing tranZoom PNG's metadata); center, width, and height of the viewed plane are configurable; default constant is `0.27334+0.00742j` ("Julia Suzana"), default frame is `[(0, 0) ± (9/5, 11/5)]`.
  - **Julia Set zoom**: `tranz zoom [-f julia] ai|manual` runs zoom sessions on a Julia Set instead of the Mandelbrot Set; the Julia constant is set via `--julia-re` and `--julia-im` on the `tranz zoom` subgroup callback; the constant can also be loaded from an existing PNG's metadata by passing the PNG path as the first positional argument.
  - New `FrameAndPoint` class in `core/frame.py`: extends `Frame` with an extra exact `gmpy2.mpq` complex-plane point (used as the Julia Set constant `c`); provides `FromCenterAndPoint()` factory; `__str__` prints as `[(center) ± size @ (point_re, point_im)]`.
  - New `-s`/`--size S` option on the `tranz image` subgroup: sets the maximum pixel side of the output image and scales the other dimension proportionally to match the frame aspect ratio; overrides `-w`/`--width` and `-h`/`--height` when given; useful for non-square Julia frames.
  - New `--mark "(re, im)"` option on `tranz image`: draws a colored crosshair overlay at a given complex-plane coordinate on the output image; `--mark-color` (default `red`) and `--mark-width` (default `1`) are also configurable.
  - New `Color` enum in `core/image.py` with eight standard overlay colors: `BLACK`, `WHITE`, `RED`, `GREEN`, `BLUE`, `YELLOW`, `CYAN`, `MAGENTA`.
  - New `DrawCrossOverlay()` function in `core/image.py`: draws a crosshair at given pixel coordinates on an existing PNG.
  - New PNG metadata keys `tranzoom:frame:julia_re` and `tranzoom:frame:julia_im`: embedded in all Julia Set images so that the Julia constant can be loaded back from the PNG path via the CLI.
  - New `Frame.PixelDimensionsFromSize()` method: computes proportional `(width, height)` pixel dimensions given a desired max-side pixel count, honoring the frame's aspect ratio.
  - New `Frame.CoordToPixel()` and `Frame.CoordsTupleToPixel()` methods: convert exact complex-plane coordinates to pixel `(x, y)` coordinates within a given image size.
  - New `-f`/`--fractal` option on the `tranz zoom` subgroup: selects the fractal type (`mandelbrot` or `julia`; default `mandelbrot`).
  - New `--julia-re` and `--julia-im` options on the `tranz zoom` subgroup: set the Julia Set constant for Julia zoom sessions.
  - `tranz zoom ai` and `tranz zoom manual` now accept any output image size, configured via `-w`/`--width` and `-h`/`--height` on the `tranz zoom` subgroup callback; default is still 512×512.
  - New `tranzoom:image:overlay` PNG metadata key records whether the saved image has a grid/direction overlay drawn on it (`"true"`) or not (`"false"`).
  - New `DEFAULT_ZOOM_SIZE = 512` constant in `core/frame.py` separates the zoom default from the `image mandel` default (`DEFAULT_IMAGE_SIZE = 1024`).

- Changed
  - **Breaking**: `tranzoom:frame:fractal` PNG metadata value is now stored lowercase (e.g., `"mandelbrot"` instead of `"Mandelbrot"`); images written by older versions will show the old capitalized value when read back by this version.
  - **Breaking**: `-w`/`--width` and `-h`/`--height` moved out of the global `tranz` callback and into per-subgroup callbacks: `tranz image [-w W] [-h H] mandel ...` (default 1024×1024) and `tranz zoom [-w W] [-h H] ai|manual ...` (default 512×512).
  - **Breaking**: `--iter`/`-i` (max iterations) and `--palette` moved from `tranz image mandel` to the `tranz image` subgroup callback: `tranz image [--iter N] [--palette NAME] mandel ...`.
  - **Breaking**: `-n`/`--max-steps` moved from `tranz zoom ai` and `tranz zoom manual` to the `tranz zoom` subgroup callback: `tranz zoom [-n N] ai|manual ...`.
  - **Breaking**: `--iterm`/`--no-iterm` moved from the individual `tranz image mandel`, `tranz image read`, `tranz zoom ai`, and `tranz zoom manual` commands to the global `tranz` callback: `tranz [--iterm] ...`.
  - **Breaking**: PNG metadata key `tranzoom:image:palette` replaces the old key `tranzoom:palette`; images written by older versions will show `null` for the palette when read back by this version.
  - `Frame.precision` property removed; replaced by `Frame.Precision(pixel_width, pixel_height, max_iter=DEFAULT_ITER)` method — precision is now computed from actual image dimensions and iteration count rather than the pessimistic `MAX_IMAGE_SIZE` ceiling; more accurate for every frame and size combination.
  - `Frame.context` property removed; replaced by `Frame.Context(pixel_width, pixel_height, max_iter=DEFAULT_ITER)` method — same improvement as `Frame.Precision()`.
  - `_MPFR_MIN_PRECISION` increased from 80 to 140 bits (≈42 decimal digits) for improved robustness at low-magnification frames.
  - `_MPFR_MIN_GUARD_BITS` increased from 64 to 88 bits for a larger safety margin above the bare minimum.
  - `MAX_IMAGE_SIZE` increased from 8192 to 16384 pixels, allowing up to 16k×16k (~256 Mpx) images.
  - Iteration constants (`MIN_ITER`, `DEFAULT_ITER`, `HIGH_ITERS`, `MAX_ITER`) moved from `core/fractal.py` to `core/frame.py` for better cohesion.
  - `-m`/`--model` now defaults to `'qwen3-vl-32b-instruct@q8_0'` (a good general-purpose vision model) instead of requiring explicit specification for AI zoom.

- Fixed
  - Precision computation now uses actual image dimensions and iteration count rather than a pessimistic `MAX_IMAGE_SIZE` baseline, giving tighter and more accurate MPFR precision for every render.
  - Overlay line width is now dynamic (`max(1, max(w, h) // 150)`) so overlays scale correctly with any image size, not just 512×512.
  - Zoom overlay text labels now scale using `max(cx, cy)` instead of `min(cx, cy)`, fixing label sizing on non-square images.

## 1.2.0 - 2026-05-15

- Added
  - Better explanation of Frames in README, with examples of exact rational inputs.

- Changed
  - **Breaking**: `mandel` and `zoom` CLI apps merged into a single unified `tranz` CLI entry point.
  - **Breaking**: `mandel gen` → `tranz image mandel`; `mandel read` → `tranz image read`; `mandel markdown` → `tranz markdown`.
  - **Breaking**: `zoom ai` → `tranz zoom ai`; `zoom manual` → `tranz zoom manual`.
  - All AI model flags (`-m`/`--model`, `--spec-tokens`, `--seed`, `-c`/`--context`, `-x`/`--temperature`, `--gpu`, `--gpu-layers`, `--fp16`, `--use-mmap`, `--flash`, `--kv-cache`, `--timeout`) moved from the `zoom` CLI callback to the `tranz` global callback, making them available to all subcommands.
  - `mandel.py` and `zoom.py` replaced by `tranz.py` as the single CLI entry point.
  - `cli/gencommand.py` → `cli/imagecommand.py` (registers `tranz image` subgroup: `mandel` and `read` commands).
  - `cli/aicommand.py` → `cli/zoomcommand.py` (registers `tranz zoom` subgroup: `ai` and `manual` commands).
  - `mandel.md` + `zoom.md` auto-generated docs → `tranz.md`.
  - Dependency updates: `click>=8.3`, `cryptography>=48.0` (new), `Pillow>=12.2`, `rich>=15.0`, `transcrypto>=2.6.1`, `typer>=0.25`.

- Fixed
  - N/A

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
