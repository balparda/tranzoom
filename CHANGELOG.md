<!-- SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Changelog

All notable changes to this project will be documented in this file.

- [Changelog](#changelog)
  - [2.1.0 - 2026-06-20](#210---2026-06-20)
  - [2.0.0 - 2026-06-19](#200---2026-06-19)
  - [1.9.0 - 2026-06-11](#190---2026-06-11)
  - [1.8.0 - 2026-06-06](#180---2026-06-06)
  - [1.7.0 - 2026-06-04](#170---2026-06-04)
  - [1.6.3 - 2026-06-03](#163---2026-06-03)
  - [1.6.2 - 2026-06-02](#162---2026-06-02)
  - [1.6.1 - 2026-06-01](#161---2026-06-01)
  - [1.6.0 - 2026-05-30](#160---2026-05-30)
  - [1.5.2 - 2026-05-27](#152---2026-05-27)
  - [1.5.1 - 2026-05-26](#151---2026-05-26)
  - [1.5.0 - 2026-05-26](#150---2026-05-26)
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

## 2.1.0 - 2026-06-26

- Added
  - **Multi-process frame interpolation rendering** (`core/zoom.py`, `InterpolatedFrameStream()`): frame interpolation (`--i-frames`) now uses Python's `concurrent.futures.ProcessPoolExecutor` to parallelize rendering of interpolated frames across multiple CPU cores; new `InterpolateFrameWorker()` function runs as a separate process to compute individual interpolated frames (linear or quadratic); new `_InterpolationJob` and `_InterpolationResult` dataclasses encapsulate job distribution and result collection; `InterpolatedFrameStream()` accepts optional `max_threads` parameter (default None = use all available cores) to control parallelism; executor automatically disabled when `i_frames=0` (no interpolation) or single-threaded execution is requested; dramatically speeds up animation generation for high-FPS outputs (e.g., `--fps 10 --i-frames 7` now renders 73 total frames from 10 real frames with ~7× speedup due to parallelism).
  - **Animation metadata hash injection control** (`--inject/--no-inject` flag, `cli/base.py`, `cli/zoomcommand.py`): new `tranz zoom auto` flag allows users to control whether the final hash is re-injected into animation metadata after rendering; `--inject` (default False) re-saves the animation file to include the final computed hash in metadata, which requires re-processing (lossless for MP4, lossy for GIF); `--no-inject` skips this step for faster completion when the final hash in metadata is not critical; useful for testing or when metadata space is constrained; both GIF and MP4 re-saving is expensive but preserves content fidelity for MP4 via ffmpeg re-mux.

- Changed
  - **MP4 metadata re-muxing optimization** (`core/zoom.py`): `ReWriteVideoMP4Meta()` completely rewritten to use external ffmpeg re-muxing instead of re-encoding; new implementation calls `imageio_ffmpeg.get_ffmpeg_exe()` with `copy` codec and `map_metadata` flags for lossless stream copying; dramatically reduces MP4 re-processing time from full re-encode to simple container re-mux operation; preserves all video frames and streams without quality loss; uses `subprocess.run()` to invoke ffmpeg directly with proper error handling and metadata injection support.
  - **Test animation outputs** (`scripts/make_test_images.sh`, `tests_integration/test_cython_equivalence.py`, `tests_integration/test_installed_cli.py`): updated to account for MP4 re-muxing changes.
  - **Example outputs in README**: updated example command outputs to show new "Copy file to destination" message when animations are saved; examples now display Lanczos resampling method in output format `{[PNG*2/Lanczos: ...]}` to indicate interpolation method being used.

- Fixed
  - **MP4 video stability**: MP4 files created with metadata injection are now stable and byte-for-byte identical across multiple re-mux operations (ffmpeg re-mux with same metadata always produces identical output), whereas previous re-encoding approach introduced minor frame variations due to codec variability.
  - **Animation rendering consistency**: animations now properly track hash values through metadata injection workflow, ensuring that multiple renders with `--inject` flag produce consistent, reproducible metadata.

## 2.0.0 - 2026-06-19

- Added
  - **Image pixel interpolation** (`--i-pixels` flag, `pixels.py`, `frame.py`): new global flag `--i-pixels` adds interpolation between pixels to upscale final images; produces smoother, higher-resolution output from the same fractal computation; valid range 0–3 (0 = no interpolation, 3 = 4× resolution); effectively multiplies final image dimensions by `(i_pixels + 1)` so a 1024×1024 render with `--i-pixels 2` produces a 3072×3072 PNG; implemented via deterministic numpy-based interpolation using PIL's `Resampling` algorithms; default method is bilinear for best stability; metadata key `tranZoom:render:i_pixels` stores the interpolation level in PNG text chunks.
  - **Pixel interpolation resampling method** (`--resample` flag, `pixels.py`): new global flag `--resample METHOD` allows selection of interpolation algorithm for pixel upscaling; available methods include bilinear (stable and fast, recommended), bicubic (smoother but slightly slower), lanczos (maximum quality, slowest), and others from PIL's `Resampling` enum; default is lanczos; choice persists in metadata, allowing re-renders with same settings to maintain consistency; particularly useful for tuning final output quality when combined with `--i-pixels`.
  - **Animation frame interpolation** (`--i-frames` flag, `pixels.py`, `zoom.py`): new `tranz zoom auto` flag `--i-frames` generates interpolated frames between each real fractal-computed frame; produces smoother, higher-FPS animations from fewer fractal computations; valid range 0–7 (0 = no interpolation, 7 = 8× FPS); effectively multiplies final FPS by `(i_frames + 1)` so `--fps 10 --i-frames 2` produces 30 effective FPS; supports both linear interpolation (default for first/last frame pairs) and **quadratic interpolation** (uses curr, next, next+1 frames for smoother acceleration); `InterpolatedFrameStream()` yields real + interpolated frames in animation order; metadata key `tranZoom:zoom:frame:i_frames` stores the interpolation level.
  - **New pixels.py module** (`pixels.py`): extracted all pixel rendering logic from `image.py` into dedicated 1440-line module; handles color palette application, histogram equalization, PNG/GIF/MP4 encoding, mark/overlay drawing, and pixel interpolation; new classes `RenderParameters` (single-image rendering), `RenderAnimationParameters` (animation rendering), `Pixels` (raw RGBA pixel array), `RenderedZoomFrame` (rendered animation frame with metadata); separates fractal computation concerns (escape-time iteration, arbitrary precision) from rendering concerns (color mapping, file I/O, interpolation).
  - **Quadratic frame interpolation** (`zoom.py`): new `QuadraticInterpolatedFrame()` function uses three-point quadratic interpolation for smoother frame blending than linear interpolation; takes `(curr, next, next+1)` frames to compute intermediate frame with acceleration/deceleration curve; blends RGB pixel values via quadratic Lagrange polynomial; automatically falls back to linear interpolation for last frame pair or when `use_quadratic=False`; controlled by `DEFAULT_USE_QUADRATIC` constant (default True).
  - **Interpolation validation** (`frame.py`, `pixels.py`): new `ValidateIPixels()` and `ValidateIFrames()` functions enforce interpolation parameter bounds; `MAX_INTERPOLATION_PIXELS = 3` caps pixel interpolation to prevent excessive memory use; `MAX_INTERPOLATION_FRAMES = 7` caps frame interpolation for animation stability; both raise `Error` on out-of-range values with clear diagnostic message.
  - **Bilinear pixel blending** (`pixels.py`): new `_BilinearInterpolate()` helper performs weighted RGBA blending for sub-pixel coordinates; uses 2×2 pixel neighborhood with horizontal/vertical fractional weights; clamps output to valid 0–255 range; used by pixel interpolation to produce smooth upscaled images without aliasing artifacts.

- Changed
  - **Major refactoring: image.py → pixels.py split** (`image.py`, `pixels.py`): image.py reduced by ~1746 lines (moved to pixels.py); `RenderParameters` and `RenderAnimationParameters` classes migrated entirely to pixels.py; all PNG/GIF/MP4 encoding moved to pixels.py; palette application, color normalization, and histogram equalization moved to pixels.py; image.py now focused exclusively on fractal computation (`Image`, `ComputationParameters`, `FractalStats`, `Histogram`); pixels.py handles all post-computation rendering concerns.
  - **Render parameters refactored** (`pixels.py`, `base.py`, `imagecommand.py`, `zoomcommand.py`): `RenderParameters` now includes `i_pixels` field (default 0); `RenderAnimationParameters` now includes `i_frames` field (default 0); `FromRender()` factory method creates animation parameters from base render parameters; all CLI commands updated to pass `i_pixels`/`i_frames` from user flags; metadata serialization/deserialization updated to preserve interpolation settings.
  - **Animation frame stream pipeline** (`zoom.py`): `InterpolatedFrameStream()` replaces old frame-by-frame rendering loop; yields `bytes` (PNG-encoded frames) in animation order from an iterable of `(curr, next)` frame pairs; automatically inserts `i_frames` interpolated frames between each real frame pair; tracks mutable hashes for all frames (real + interpolated) for metadata; supports quadratic or linear interpolation mode via `use_quadratic` parameter.
  - **Image size calculation** (`frame.py`): `ComputationParameters.Size()` method added with optional `i_pixels` parameter; returns final disk size as `(width * (i_pixels + 1), height * (i_pixels + 1))`; replaces direct `.size` property access when interpolation is active; used in DB size estimation and CLI output.
  - **CLI help text updated** (`base.py`): `-w/--width`, `-h/--height`, and `-s/--size` flags now include note: `NOTE: if --i-pixels is given, the effective width/height/size will be w/h/s*(i+1), so keep that in mind`; `--fps` flag includes note: `NOTE: if --i-frames is given, the effective FPS will be fps*(i+1), so keep that in mind`; clarifies relationship between computation parameters and final output dimensions/framerate.
  - **Zoom metadata expanded** (`image.py`, `base.py`): `tranZoom:zoom:frame:i_frames` key stores frame interpolation level in animation metadata; zoom hash computation includes `i_frames` in `RenderAnimationParameters` serialization so different interpolation levels produce different hashes; `tranz image read` displays interpolation settings when reading GIF/MP4 files.
  - **Test image hashes updated** (`base.py`): all test image hashes regenerated after pixel/frame interpolation changes; `SEAHORSE_TAIL_HASH`, `SUZANA_WAVE_HASH`, `SEAHORSE_ANIMATED_HASH`, `T_GIF_*_HASH` constants updated; `TEST_IMAGE_DATA_HASHES` dict updated with new frame counts and data hashes for test animations (seahorse: 45→31 frames, seeds300: 20→10 frames); reflects new default animation parameters and frame interpolation.
  - **Integration test coverage** (`tests_integration/test_cython_equivalence.py`): expanded by ~670 lines to cover pixel/frame interpolation; validates interpolated images/animations produce consistent output across Python/Hybrid/Cython optimization modes; tests bilinear pixel blending, linear frame interpolation, and quadratic frame interpolation; ensures interpolation does not introduce computation artifacts.

- Fixed
  - **Zoom color banding** (`zoom.py`, `pixels.py`): fixed per-frame color flickering in zoom animations by applying `ZoomColorNorm` to interpolated frames (not just real frames); interpolated frames now use the same color normalization histogram anchors as their surrounding real frames; eliminates visual discontinuities when `--i-frames > 0`.
  - **Interpolation edge cases** (`pixels.py`, `zoom.py`): fixed last-frame interpolation handling; quadratic interpolation correctly falls back to linear for final frame pair (no next+1 available); bilinear pixel interpolation clamps output to valid RGBA range to prevent overflow/underflow artifacts on extreme color boundaries.
  - **Memory efficiency** (`zoom.py`, `frdb.py`): removed unnecessary `prev`/`next` frame retention during interpolation; `InterpolatedFrameStream()` uses single-frame lookahead instead of buffering three frames; reduces peak memory usage during animation rendering; particularly important for high-resolution animations with `--i-pixels > 0`.
  - **Metadata consistency** (`image.py`, `pixels.py`): ensured `i_pixels` and `i_frames` are correctly persisted in all PNG text chunks; `tranz image read` now displays interpolation metadata for both still images (`i_pixels`) and animations (`i_frames`); metadata roundtrip (render → save → read → re-render) preserves interpolation settings exactly.

## 1.9.0 - 2026-06-11

- Added
  - **Smooth interior (Set) point coloring** (`image.py`, `fractalfast.py`, `fractalc.pyx`): interior points now support fractional remainder values for smooth coloring interpolation, eliminating harsh banding at set boundaries; `Histogram.InterpolateBucket()` method added to both exterior and interior histograms for unified smooth color mapping; `ZoomColorNorm.InterpolateInternal()` now accepts a `remainder` parameter for sub-integer color blending, matching the precision of exterior smooth coloring.
  - **Test image generation scripts** (`scripts/make_test_images.sh`): new script automates generation of test animation GIFs for integration test suite; generates three Julia Set animations (blob, dragon, suzana) and two Mandelbrot animations (seahorse, seeds300) for deterministic integration test coverage; script uses `poetry run tranz --opt python` to ensure pixel-perfect reproducible output.
  - **Demo image generation script** (`scripts/make_demo_images.sh`): renamed from `make_examples.sh`; generates all official demo images (full set, seahorse, seahorse tail, julia suzana, etc.) for documentation and README; used by `make demo` target.
  - **New make targets** (`Makefile`): `make timages` runs test image generation script; `make demo` runs demo image generation script; facilitates local reproduction of test/demo content and integration test setup.
  - **Cython equivalence tests** (`tests_integration/test_cython_equivalence.py`): new 468-line integration test module that validates pure Python and Cython fractal computation produce pixel-identical output; tests Mandelbrot/Julia rendering, interior coloring, smooth escape values, and histogram statistics across multiple zooms; prevents performance optimization regressions that silently change pixel output.

- Changed
  - **CLI animation code refactoring** (`cli/base.py`, `cli/zoomcommand.py`): large portion of zoom animation logic moved from `zoomcommand.py` (reduced by 539 lines) to `base.py` (expanded by 554 lines) for better code organization and reuse; animation computation, parameter handling, and rendering consolidated in a single module; helper functions like depth estimation and progress bars centralized.
  - **Interior histogram interpolation** (`image.py`): `InterpolateInt()` method renamed to `InterpolateInternal()` for symmetry with `InterpolateExternal()` (formerly `InterpolateExt()`); method signature changed to accept `(key: int, remainder: float)` for smooth coloring instead of just `key`; internal histogram lookup now delegates to `Histogram.InterpolateBucket()` for consistent blending logic.
  - **Frame constant canonicalization** (`frame.py`): new `CanonicalMPFR()` helper function added to canonicalize arbitrary-precision floats to a canonical form (base 2 with consistent representation); improves hashing and comparison of equivalent MPFR values; used internally for frame coordinate consistency.
  - **Dependency updates** (`pyproject.toml`): `typer` bumped from pinned `0.25.1` to `>=0.26.7` (was previously pinned due to type stub issues; now compatible); `transai` bumped to `>=1.3.3`; `transcrypto` bumped to `>=2.7`; removed `click==8.3.3` and `cryptography>=48.0` dependencies (no longer needed after Typer update).
  - **Fractal computation refactoring** (`fractalfast.py`, `fractalc.pyx`): ~434 lines changed in pure Python; interior statistics handling updated to use smooth remainder values; escape-time iteration refined to track fractional component for smooth coloring; Cython version receives equivalent changes.
  - **Integration test structure** (`tests_integration/test_installed_cli.py`): simplified assertions and test organization; added Cython equivalence test module with comprehensive output validation across multiple render configurations.

- Fixed
  - **Interior point edge cases** (`image.py`): fixed bug where interior points with missing histogram data (e.g., all-interior images) would cause incorrect palette lookup; now explicitly handles `escaped_at < 0 and not histogram.count` case by rendering as black; improved error logging for invalid pixel states.
  - **Smooth coloring blend clamping** (`image.py`): fixed potential out-of-range palette values in `InterpolateExternal()` and `InterpolateInternal()` by adding explicit clamping to `[0.0, _ALMOST_ONE]` range; prevents rare edge cases where histogram interpolation produces values slightly outside valid palette range.
  - **Animation parameter calculation** (`base.py`): fixed animation depth estimation to correctly handle frames with mixed interior/exterior content; `_FrameEstimatedIters()` now accurately weights computational load as `d/5 + 4d × n_interior/(5 × n_px)` instead of treating all pixels equally.
  - **Typer compatibility** (`cli/base.py`, `pyproject.toml`): resolved type stub compatibility issues that forced `typer==0.25.1` pinning; upgraded to `typer>=0.26.7` which has proper type checking support and modern Click integration; removed workarounds for older type stub limitations.

## 1.8.0 - 2026-06-06

- Added
  - **Automated Cython wheel building** (`pyproject.toml`, `build_extensions.py`): Poetry now automatically builds Cython extensions when creating wheels via `poetry build`; the `[tool.poetry.build]` section specifies `scripts/build_extensions.py` as the build script; this ensures wheels include compiled `.so`/`.pyd`/`.dylib` files for maximum performance out-of-the-box; no separate `make cython` step needed before `poetry build`.
  - **Wheel-aware integration tests** (`tests_integration/test_installed_cli.py`): integration test now assumes the package is already installed in the current environment (by CI workflow or manual `poetry build` + `pip install dist/*.whl`); test uses `shutil.which('tranz')` to locate the installed console script instead of building/installing a wheel itself; simpler test logic with clear documentation on how to run locally.

- Changed
  - **Build system dependencies** (`pyproject.toml`): `Cython`, `gmpy2`, and `setuptools` added to `[build-system] requires` section; these are now explicitly declared as build-time dependencies needed for wheel compilation; ensures Poetry installs them automatically when running `poetry build`; still remain in `[project.dependencies]` for runtime use and in-place development compilation with `make cython`.
  - **CI workflow** (`.github/workflows/ci.yaml`): integration job now explicitly builds wheel with `poetry build -f wheel --clean`, installs it into a clean venv (`.venv-wheel-test`), then runs pytest from that venv; test validates the wheel's console scripts work correctly in a fresh environment; separates wheel building from test execution for clearer CI structure.
  - **Wheel includes extensions** (`pyproject.toml`): `include` section updated to bundle compiled extensions (`.so`, `.pyd`, `.dylib`) in wheels; sdist includes Cython source files (`.pyx`) and generated C files (`.c`) for source builds; wheels ship with pre-compiled extensions for immediate performance on supported platforms.
  - **Integration test documentation** (`README.md`): updated testing section to reflect new workflow where wheel is built separately, then installed, then tested; local development instructions now show explicit steps: `poetry build -f wheel --clean`, then `pip install dist/*.whl`, then `pytest tests_integration/`; clarifies that CI automates this entire sequence.

- Fixed
  - **Removed obsolete wheel-building code** (`tests_integration/test_installed_cli.py`): removed calls to `config.EnsureAndInstallWheel()` and `config.EnsureConsoleScriptsPrintExpectedVersion()` from transcrypto; these were redundant since the CI workflow already builds/installs the wheel before running tests; test now directly uses the already-installed CLI via `shutil.which('tranz')`.

## 1.7.0 - 2026-06-04

- Added
  - **Full Cython optimization** (`fractalc.pyx`): new pure-Cython module (1346 lines) with direct gmpy2 C-API usage for maximum performance; implements `MandelbrotComputation()` and `JuliaComputation()` using raw GMP/MPFR/MPC C calls with explicit `mpfr_t` and `mpq_t` manipulation; bypasses Python object overhead entirely for inner computation loops; provides up to ~2× speedup over hybrid mode for deep-zoom, high-precision renders; automatically loaded when available, falls back to hybrid/Python if import fails.
  - **Hybrid Cython mode** (`fractalfast.py`): enhanced pure-Python module (676 lines) now structured for Cython's pure-Python mode; can be compiled to native extension using type annotations that Cython optimizes; provides intermediate performance between pure Python and full Cython; exports `CYTHON` boolean to detect compilation status; always present as pure-Python fallback.
  - **Three-tier optimization system** (`frame.py`, `fractal.py`): new `Optimization` enum with three levels: `PYTHON` (pure Python, no compilation), `HYBRID` (Cython pure-Python mode, compiled `fractalfast.py`), and `CYTHON` (full Cython, compiled `fractalc.pyx`); `OptimizationToUse()` function determines available optimization at runtime; `ComputeFractal()` and `FractalAdaptiveIterations()` accept optional `optimization` parameter to specify minimum required level.
  - **CLI optimization option** (`tranz.py`, `base.py`): new global `--opt` flag to specify minimum optimization level for computation; options: `python`, `hybrid`, `cython`; default `None` uses maximum available; if requested level is unavailable, raises error (except `python` with `hybrid` loaded uses `hybrid`); affects all render and zoom commands.
  - **Cython build system** (`build_ext.py`): new build script for compiling both `fractalfast.py` and `fractalc.pyx` to native extensions; auto-discovers Homebrew GMP/MPFR/MPC library paths on macOS; links against `libgmp`, `libmpfr`, `libmpc` C libraries; uses `setuptools` + `Cython.Build.cythonize`; run via `make cython` (or `poetry run python build_ext.py build_ext --inplace`); produces `.so` (macOS/Linux) or `.pyd` (Windows) extensions placed alongside source files.
  - **`make cython` and `make clean-cython` targets** (`Makefile`): `make cython` compiles both Cython modules to native extensions; `make clean-cython` removes build artifacts (`.c`, `.so`, `.pyd`, `build/` directory); compiled extensions are gitignored; `make install` now runs `make cython` automatically.
  - **Benchmark script** (`scripts/benchmark.py`): micro-benchmark comparing pure Python, hybrid, and full Cython performance for `EncodeIntFloatTo64()` calls; reports timing for encode/decode operations and combined workflow; used for performance regression testing during development.

- Changed
  - **Runtime dependencies** (`pyproject.toml`): added `cython>=3.2` and `setuptools>=82.0` as runtime dependencies (were dev-only); Cython compilation now supported out-of-the-box for users who install from PyPI; wheels still ship pure-Python fallbacks, but users can compile locally with `make cython` for acceleration.
  - **Fractal computation loader** (`fractal.py`): module-level import now loads `fractalfast` (pure-Python or hybrid), then attempts to import `fractalc` (full Cython); `PY_MANDELBROT_COMPUTATION`, `PY_JULIA_COMPUTATION`, `PY_NORM_ESCAPE`, `PY_ENCODE_INT_64` always available from `fractalfast`; `CY_MANDELBROT_COMPUTATION`, `CY_JULIA_COMPUTATION`, `CY_NORM_ESCAPE`, `CY_ENCODE_INT_64` set to `None` if `fractalc` import fails; `OptimizationToUse()` determines best available at runtime.
  - **Ruff exclusions** (`pyproject.toml`): `fractalc.pyx` excluded from Ruff linting (not valid Python syntax); `build_ext.py` allowed subprocess usage for Homebrew detection (S404, S603, S607) and no `__init__.py` required (INP001).
  - **Pyright exclusions** (`pyproject.toml`): `fractalc.pyx` excluded from Pyright type checking; pure Cython syntax incompatible with Python type checker.
  - **Test coverage exclusions** (`pyproject.toml`): `build_ext.py` excluded from coverage reporting; build scripts not part of runtime code coverage.
  - **Integration test determinism** (`tests_integration/test_installed_cli.py`): all integration test CLI calls now include `--opt python` to force pure-Python computation; ensures deterministic pixel-perfect output hashes regardless of Cython availability; prevents CI flakiness when Cython extensions are present.
  - **Performance section** (`README.md`): updated to reflect three-tier optimization system; documented Cython acceleration as optional but recommended for deep zooms; added note that PyPI wheels ship pure-Python but users can compile locally.

- Fixed
  - **Import warning message** (`fractal.py`): when `fractalc` import fails, warning now correctly states "will be limited to PYTHON/CY HYBRID computation" if hybrid is loaded, or "PURE PYTHON computation" if not; previously always said "PYTHON/CY HYBRID" even when pure Python was the only option.
  - 2 bugs on animation DB saving and loading partially done animations.

## 1.6.3 - 2026-06-03

- Added
  - **`_FrameEstimatedIters()` helper** (`zoomcommand.py`): new internal function that estimates the computational load for an animation frame as `d/5 + 4d × n_interior/(5 × n_px)` — a weighted sum of a fixed base (1/5 of depth) plus a load proportional to the fraction of interior (Set) pixels; used both for the progress bar total and for per-frame updates, giving significantly more accurate ETAs for frames with mixed interior and exterior content.

- Changed
  - **`FractalStats` nullable interior-stats fields** (`image.py`, `fractal.py`, `zoomcommand.py`): the eight interior-stats fields (`max_lo`, `max_hi`, `min_lo`, `min_hi`, `ang_lo`, `ang_hi`, `imag_lo`, `imag_hi`) are now typed `gmpy2.mpfr | None` instead of using magic sentinel values (`(4, 0)` for max/min, `(1, 0)` for ang/imag) to signal "no data collected"; `__post_init__()` validation, serialization, deserialization, stats aggregation in `ComputeFractal()`, stats interpolation in `_DepthAndStatsForFrame()`, and `MakeImageMeta()` all updated accordingly; `None` fields are omitted from image metadata instead of being written as magic-value strings.
  - **`tqdm.rich` progress bars** (`fractal.py`, `zoomcommand.py`): per-pixel progress bars in `_MandelbrotComputation()` and `_JuliaComputation()`, the depth pre-pass bar, and the render bar in `Auto()` now use `tqdm.rich.tqdm` for richer terminal display; `TqdmExperimentalWarning` is suppressed with `warnings.catch_warnings()`; the outer computation bar in `Auto()` intentionally remains `tqdm.tqdm` because it has a live sub-bar and both would fight for the same terminal line.
  - **Animation computation progress bar unit** (`zoomcommand.py`): the main animation computation bar was renamed from `'Frames'/'fr'` to `'Iter'/'it'`, reflecting that its work unit is now estimated iterations rather than frame count.

- Fixed
  - **`FractalStats` stats aggregation with nullable fields** (`fractal.py`): `ComputeFractal()` was calling `min()`/`max()` directly over stats fields from parallel worker tasks, which would raise `TypeError` if any field was `None`; aggregation now filters `None` values and uses `default=None`, producing `None` when all workers had no data for a field; both `_MandelbrotComputation()` and `_JuliaComputation()` now emit `None` for stats fields when the pixel-level sentinel condition (`hi < lo`) is met, replacing the old magic-value output.
  - **AI zoom missing depth reset** (`ai.py`): the `dataclasses.replace(params, ...)` call inside `ZoomLoop()` was missing `depth=frame.MIN_ITER`, causing the AI zoom to carry over a stale `max_iter` depth from the previous frame into the next frame's computation parameters.

## 1.6.2 - 2026-06-02

- Added
  - **`SmoothDepths()` function** (`frame.py`): new function that converts raw per-frame max-iteration estimates into smoothed depth values; operates in log-space with a centered 5-tap zero-phase FIR filter plus a robust local spike clamp (median absolute deviation, configurable `spike_down_sigma` / `spike_up_sigma`); a `_ReflectIndex()` helper provides symmetric boundary conditions; output is always in `(MIN_ITER, MAX_ITER]` and never equals the sentinel `MIN_ITER`; a variable-strength safety margin is applied proportional to local log-depth variation.
  - **`ConcurrenceToUse()` helper** (`frame.py`): extracted and centralizes the logic for determining the number of parallel render processes, replacing inline boilerplate in `ComputeFractal()`; raises `Error` on invalid input; respects `MAX_CONCURRENCE` and `AVAILABLE_CPU` limits.
  - **Per-frame adaptive depth with depth key frames** (`zoomcommand.py`, `image.py`): before rendering animation frames, `tranz zoom auto` now pre-computes optimal iteration depths for a set of "depth key frames" (one per ≈2× zoom step, controlled by `MAGNITUDE_PER_DEPTH_MARKER = gmpy2.mpq('3/10')`); raw depths are smoothed with `SmoothDepths()` to avoid jarring depth jumps between adjacent frames; non-depth frames receive a linearly interpolated depth between the two nearest depth key frames; the smoothed depths (and associated `FractalStats`) are saved to the DB so a second run with the same zoom parameters can skip the entire depth pre-pass.
  - **Depth pre-computation progress bar** (`zoomcommand.py`): a `tqdm` bar (yellow, unit `fr`) tracks progress across the depth key frame probe pass; the main frame-rendering bar now uses total iteration depth (sum of all per-frame `max_iter`) as its work unit, giving a more accurate ETA.
  - **`MAGNITUDE_PER_DEPTH_MARKER` constant** (`image.py`): `gmpy2.mpq('3/10')`, one depth probe per ≈2× zoom; controls the density of depth key frames and therefore the smoothness of the per-frame depth variation.
  - **`FractalStats` serialization** (`image.py`): `FractalStats` now extends `SerializingFractalObject`; added `__post_init__()` validation, `__str__()`, a `json` property, and a `FromJson()` static method; `FractalStats` objects can now be stored in and retrieved from the DB as part of `DepthFrameData`.
  - **`KeyFrameData` and `DepthFrameData` TypedDicts** (`frdb.py`): new typed storage structures for marker and depth frames; `KeyFrameData` holds `idx` (frame index) and `frm` (frame hash); `DepthFrameData` extends it with `orig_depth`, `smooth_depth`, and `stats` (serialized `FractalStats`); used in the updated `ZoomData`.
  - **`FractalDatabase.FindFrame()` method** (`frdb.py`): look up a `Frame` object and its `FrameData` by hash; returns `(None, None)` if not found or if `use_db` is False.
  - **`FractalDatabase.AddFrameToDB()` method** (`frdb.py`): add a `Frame` to the frames dict if not already present; no-op if already stored; called automatically by `AddZoomToDB()` for all frames.
  - **`META_ZOOM_MARKER_INDEX_LIST_KEY` and `META_ZOOM_DEPTH_FRAMES_LIST_KEY`** (`image.py`): new `tranZoom:zoom:marker:index` and `tranZoom:zoom:depth:frames` metadata keys stored in the final GIF/MP4 output; the marker key is a list of frame indices; the depth key is a list of `(idx, orig_depth, smooth_depth)` triples, one per depth key frame.
  - **`FractalAdaptiveIterations()` made public** (`fractal.py`): renamed from `_FractalAdaptiveIterations()` to `FractalAdaptiveIterations()`; keyword-only parameters added; now called directly from `zoomcommand.py` for the depth pre-computation pass without going through `ComputeFractal()`.
  - **`MIN_IMAGE_PX` and `MAX_IMAGE_PX` constants** (`frame.py`): convenience pixel-count constants `MIN_IMAGE_SIZE**2` and `MAX_IMAGE_SIZE**2`; used in `FractalStats.__post_init__()` validation.

- Changed
  - **`tranz zoom auto` removes `--max-iter` option** (`zoomcommand.py`): iteration depth is now always computed adaptively per frame using the depth key frame pre-pass and interpolation; the `--max-iter` flag has been removed; there is no longer a way to manually override depth for animations.
  - **`ZoomParameters.Frames()` return type** (`image.py`): changed from `tuple[list[Frame], list[tuple[int, Frame]]]` to `tuple[list[Frame], list[tuple[int, Frame]], list[tuple[int, Frame]]]`; the third element is the list of depth key frames (selected at `MAGNITUDE_PER_DEPTH_MARKER` intervals); a new `_FramesSubset()` helper generalizes both marker and depth frame selection, replacing duplicated logic.
  - **`ZoomData` TypedDict updated** (`frdb.py`): `data_hash` changed to `str | None` (depth-only pre-pass saves to DB before file creation); `rendered_path` changed to `str | None`; `markers` changed from `list[tuple[int, str]]` to `list[KeyFrameData]`; new `depths: list[DepthFrameData]` field for depth key frame storage.
  - **`FractalDatabase.AddZoomToDB()` signature updated** (`frdb.py`): `data_hash` and `path` are now `str | None`; added `depths` parameter (`list[tuple[int, frame.Frame, int, int, image.FractalStats]]`); now calls `AddFrameToDB()` for every frame before inserting the zoom entry; path and hash indices are only updated when the respective values are non-`None`.
  - **`FractalDatabase.DoComputation()` accepts `stats` parameter** (`frdb.py`): optional `image.FractalStats` pre-collected from a depth probe; passed through to `ComputeFractal()` to skip the re-probe when stats are already known; parameter ordering regularized to keyword-only after `max_threads`.
  - **`MAX_PRE_PROCESS_CONCURRENCE` removed** (`frame.py`): the separate pre-process concurrency limit is gone; `ConcurrenceToUse()` now uses `MAX_CONCURRENCE` uniformly for both probe and full-resolution renders.
  - **Zoom summary includes depth frame count** (`zoomcommand.py`): the zoom start log line now reports both marker and depth frame counts, e.g. `with 40 frames (2 markers, 5.00%, and 4 depth frames, 10.00%)` instead of just `with 40 frames`.
  - **Frame log includes depth** (`zoomcommand.py`): each frame log line now shows `Frame N / M - depth D` so you can see the per-frame iteration depth as the animation renders.
  - **`MIN_IMAGE_SIZE` raised from 16 to 24** (`frame.py`): the minimum image size (also used as the probe image size for adaptive depth estimation) was raised from 16 to 24; this gives a 576-pixel sample (vs. the previous 256) for a more reliable histogram during the auto-depth pre-pass, and tightens the minimum accepted image dimension in the CLI from 16 to 24 pixels.
  - **Powers-of-1000 example** (`scripts/make_examples.sh`): `--set imaginary` removed from the powers-of-1000 zoom rendering script; these images are now rendered without interior set coloring.
  - **Config serialize/deserialize with `silent=True`** (`base.py`): `TranZoomConfig.LoadConfig()` and `SetConfig()` now call `DeSerialize(silent=True)` / `Serialize(silent=True)`, suppressing spurious log chatter during routine config I/O.
  - **`SEAHORSE_ANIMATED_HASH` and `SUZANA_WAVE_HASH` updated** (`base.py`): reflect the changed render output produced by the improved per-frame adaptive depth computation.

- Fixed
  - **Adaptive depth probe: outlier trimming** (`fractal.py`): the auto-depth probe now skips the top `_ITER_OUTLIER_SKIP = 3` extreme-outlier pixels from the histogram tail when estimating the max escape iteration; this prevents a small number of isolated deep-escape pixels from artificially inflating the depth estimate and causing unnecessarily deep (slow) renders.
  - **Memory warning suppressed in streaming mode** (`zoomcommand.py`): the "large zoom render memory" warning is no longer emitted when `--stream` is active, because streaming processes frames one at a time and does not hold the full frame set in memory; the check is now inside the DB context so it can correctly inspect the streaming flag.

## 1.6.1 - 2026-06-01

- Added
  - **Size and memory estimation** (`frame.py`, `image.py`, `zoomcommand.py`): new `DeepSize()` function for recursive deep-size estimation; `self_sz` property on `SerializingFractalObject`, `Image`, and `Image.Histogram`; `ComputationParameters.disk_sz_bytes`, `.mem_sz_bytes`, `.comp_memory_sz_bytes`, `.png_sz_bytes()`; `ZoomParameters.data_sz_bytes`, `.comp_memory_sz_bytes`, `.animation_sz_bytes()`; size threshold constants in `frame.py` (`THRESHOLD_LARGE_PNG_BYTES` 50 MB, `THRESHOLD_LARGE_FRAME_MEMORY_BYTES` 20 GB, `THRESHOLD_LARGE_ANIMATION_BYTES` 2 GB, `THRESHOLD_LARGE_ZOOM_MEMORY_BYTES` 32 GB).
  - **Pre-computation size/memory warnings** (`base.py`, `zoomcommand.py`): before starting any expensive computation or animation, warnings are now printed if estimated on-disk file sizes exceed 50 MB (single image) or 2 GB (animation), or if estimated peak RAM exceeds 20 GB (single image) or 32 GB (animation).
  - **`FractalDatabase.is_read_write` property** (`frdb.py`): convenience property returning `True` iff the database is in-use and not read-only.
  - **Streaming frame mode in `tranz zoom auto`** (`zoomcommand.py`): when the DB is read-write, individual frames are loaded from disk on demand during animation rendering (`_SmartImage()`) rather than held all in RAM simultaneously; this reduces peak memory proportionally to the number of frames.
  - **DB periodic check-pointing in `tranz zoom auto`** (`zoomcommand.py`): the DB is saved to disk after every 5 computed frames (`_N_FRAMES_PER_DB_SAVE = 5`), protecting against data loss during long-running zoom operations.
  - **File sizes in completion log messages** (`frdb.py`, `base.py`, `zoomcommand.py`): saved-image log lines now include the actual on-disk file size as a humanized byte string (e.g., `Saved to 'file.png', 4.2 MB`).

- Changed
  - **Multiprocessing constants moved to `frame.py`** (`fractal.py` → `frame.py`): `AVAILABLE_CPU`, `MAX_PRE_PROCESS_CONCURRENCE`, and `MAX_CONCURRENCE` moved from `fractal.py` to `frame.py`; `fractal.MAX_CONCURRENCE` and `fractal.AVAILABLE_CPU` are no longer public — use `frame.MAX_CONCURRENCE` and `frame.AVAILABLE_CPU`; `MAX_CONCURRENCE` reduced from 16 to 12.
  - **`Image.Histogram` memory reduction** (`image.py`): `linear`, `d_linear`, `cumulative`, and `d_bucket_cumulative` are now `@property` methods computed on-the-fly from the stored `d_cumulative` and `bucket_cumulative`; only `d_cumulative`, `d_bucket_linear`, and `bucket_cumulative` are stored as dataclass fields, reducing per-histogram memory.
  - **`Image.ZoomColorNorm.FromMarkers()` renamed to `FromSortedMarkers()`** (`image.py`): signature changed from `dict[int, Image]` to `abc.Iterable[tuple[int, Image]]`; callers must pass an iterable of `(idx, Image)` pairs in sorted order to enable single-pass processing.
  - **`FractalDatabase.DoComputation()` return type** (`frdb.py`): widened from `tuple[ComputationParameters, Image]` to `tuple[ComputationParameters, Image, bool]`; the third element is `True` if the image was freshly computed, `False` if loaded from cache.
  - **`FractalDatabase.DoRender()` return type** (`frdb.py`): widened from `tuple[bytes, str, Path]` to `tuple[bytes, str, Path, bool]`; the fourth element is `True` if the render was done from scratch, `False` if loaded from disk cache.
  - **`FractalDatabase.SaveImageData()` strips histograms before saving** (`frdb.py`): histograms are stripped before serialization and restored afterward; `LoadImageData()` now automatically calls `RebuildHistograms()` after deserialization; this reduces the on-disk size of cached image data.
  - **`tranz zoom auto` single-pass rendering** (`zoomcommand.py`): the previous two-pass approach (marker frames first, then regular frames) is replaced by a single unified loop over all frames in order; marker frames are still distinguished in the log (magenta color) and identified for `ZoomColorNorm` construction; the final success message no longer includes a separate `(markers)` timer.
  - **`MAGNITUDE_PER_FRAME_MARKER`** (`image.py`): changed from `1` (one marker every exactly 10× zoom) to `13/14` (one marker every ≈8.5× zoom); finer color normalization anchoring for smoother color consistency across animation frames.
  - **`max_denominator` rational precision in `ZoomParameters.Frames()`** (`image.py`): increased 100× from `100 × 10^ceil(mag)` to `10_000 × 10^ceil(mag)` to reduce coordinate rounding errors at high zoom depth.
  - **`SEAHORSE_ANIMATED_HASH`** (`base.py`): updated to reflect the animation produced by the changed marker interval.

- Fixed
  - **Missing local type annotations in `Frame.__str__()` and `Frame.IsSquare()`** (`frame.py`): the `cx, cy = self.center` and `dx, dy = self.size` unpacking assignments were missing explicit `gmpy2.mpq` type annotations, causing strict type checker warnings.

## 1.6.0 - 2026-05-30

- Added
  - **`tranz image clean` command** (`imagecommand.py`, `image.py`, `base.py`): new command to read a tranZoom fractal image and save a clean copy with all tranZoom metadata stripped; accepts `--hash/--no-hash` (keep safe frame/computation/render/image hashes; default keep), `--path/--no-path` (randomize filename to `fractal-<HEX20>.ext`; default keep), and `--out FORMAT` (`jpeg`/`jpg`/`png`; default `jpeg`); JPEG is recommended for sharing (smaller, and slight lossy compression adds noise); for PNG output, hashes are stored as PNG tEXt chunks; for JPEG output, hashes are serialized as compact JSON in the EXIF `ImageDescription` tag.
  - **`CleanSavePNG` / `CleanSaveJPG`** (`image.py`): new helper functions for creating stripped copies of fractal images; `CleanSavePNG` accepts optional `extra_meta` to embed selected metadata as PNG tEXt chunks; `CleanSaveJPG` accepts optional `extra_meta` and embeds it as compact JSON in the EXIF `ImageDescription` tag (0x010E); when `extra_meta` is None, both produce fully metadata-free output.
  - **`META_SAFE_HASHES`** (`image.py`): new constant `set[str]` listing the metadata keys safe to keep in a shared image (frame hash, computation hash, zoom hash, render hash, image data hash); these depend on fractal coordinates or raw pixel data and cannot be reverse-engineered for any non-trivial frame.
  - **`META_ZOOM_HASH_KEY`** (`image.py`): new metadata key `tranZoom:zoom:hash` written to animated GIF/MP4 files by `tranz zoom auto`.
  - **`JPEG_QUALITY`** (`image.py`): new public constant (`95`) for JPEG output quality.
  - **Richer PNG metadata keys** (`image.py`): renamed and added keys for better organization — `META_COMPUTATION_WIDTH_KEY`, `META_COMPUTATION_HEIGHT_KEY`, `META_COMPUTATION_SEARCH_DEPTH_KEY`, `META_COMPUTATION_COLOR_SET_KEY`, `META_COMPUTATION_HASH_KEY`, `META_FRAME_HASH_KEY`, `META_RENDER_HASH_KEY` (previously some of these were `META_IMAGE_WIDTH_KEY`, `META_IMAGE_HEIGHT_KEY`, etc.); all new keys are written by `MakeImageMeta`.
  - **`--readonly-db/--no-readonly-db` global flag** (`tranz.py`, `base.py`): new CLI flag to open the fractal DB in read-only mode (reads are allowed but no writes or saves occur); previously `db_read_only` was always `False` at the CLI level and was only settable programmatically.
  - **Marker frames for zoom animations** (`image.py`, `zoomcommand.py`, `frdb.py`): `ZoomParameters.Frames()` now returns a `tuple[list[Frame], list[tuple[int, Frame]]]` — `(all_frames, marker_frames)` — where `marker_frames` is a subset of `all_frames` placed at regular 10× magnification intervals (one per `MAGNITUDE_PER_FRAME_MARKER` decade, default every 10× zoom) using an O(log n) bisect-based search; marker frames are computed first before any regular frames to enable cross-frame color normalization.
  - **`Image.ZoomColorNorm` / `Image.FrameColorNorm`** (`image.py`): two new inner classes for stable color normalization across zoom animations; `ZoomColorNorm` is built from the marker `Image` objects via `ZoomColorNorm.FromMarkers()` and provides per-frame `FrameColorNorm` anchors via `ForFrame()`; `AsPixels()` now accepts a `zoom_norm` parameter; this eliminates per-frame palette shifts that previously caused visible flickering in long animations.
  - **`RenderParameters.prev_marker` / `next_marker`** (`image.py`): two new optional `Frame` fields on `RenderParameters`, carrying the surrounding marker frames for `ZoomColorNorm` interpolation; included in the render key (hash) and serialized to JSON.
  - **`MAGNITUDE_PER_FRAME_MARKER` and `MAX_TOLERATED_MARKER_MAG_ERROR`** (`image.py`): two new constants — `MAGNITUDE_PER_FRAME_MARKER = mpq('1')` (one marker every 10× zoom) and `MAX_TOLERATED_MARKER_MAG_ERROR = 0.06` (6% max error for marker placement).
  - **`FractalDatabase.DoComputation()`** (`frdb.py`): new method extracted from `CoreComputeImage()`; handles the full fractal computation phase (DB lookup → disk-cache load → actual `ComputeFractal` call → `SaveImageData` + `AddComputationToDB`); returns `(params, image.Image)`.
  - **`FractalDatabase.DoRender()`** (`frdb.py`): new method extracted from `CoreComputeImage()`; handles the rendering phase (palette application, PNG/GIF/MP4 bytes generation, optional DB cache); accepts `zoom_norm`, `silent`, and `no_meta` optional parameters; returns `(bytes, hash, path)`.
  - **`FractalDatabase.FindComputation()`** (`frdb.py`): new method that looks up a computation in the DB given its `ComputationParameters`; extracted from the old `FindImage()` method to allow independent computation and render lookups.
  - **`FractalDatabase.FindRender()`** (`frdb.py`): renamed from `FindImage()`; now delegates the computation lookup to `FindComputation()`.
  - **`ReWriteAnimatedGIFMeta()` and `ReWriteVideoMP4Meta()`** (`image.py`): two new functions to rewrite GIF/MP4 metadata without re-rendering or re-encoding frames; used by `tranz zoom auto` to inject final metadata (including the zoom hash) after assembling frames in a temporary file.
  - **MP4 support in `GetBasicDataFromImage()`** (`image.py`): previously raised `NotImplementedError` for MP4 input; now detects MP4 via the `ftyp` box header, reads frame size via `imageio`/`ffmpeg`, and reads container tags (including the JSON comment field written by `WriteVideoMP4`) via a `subprocess` `ffmpeg -f ffmetadata` call; `tranz image read` now accepts GIF and MP4 inputs in addition to PNG.
  - **`tqdm` progress bar for rendering phase in `tranz zoom auto`** (`zoomcommand.py`): a `tqdm` progress bar is now shown during the frame-rendering (palette application) phase of zoom animation generation.
  - **`tranz image read` validates file existence** (`imagecommand.py`): now raises a clear error if the specified path does not exist or is not a file, instead of letting the OS raise an opaque error.
  - **`--pass` global flag for DB encryption** (`tranz.py`, `base.py`, `frdb.py`): new CLI option to AES-encrypt the local fractal DB and computation data; omit for no encryption; `--pass ""` triggers a secure hidden-input prompt (password not visible in shell history); `--pass "pwd"` passes inline (convenient for scripts, but visible in process list); when encryption is active, compression is always enabled regardless of `--db-compression`; opening an encrypted DB without `--pass` now raises a descriptive error instead of a cryptic decode failure.

- Changed
  - **`ZoomParameters.Frames()` return type** (`image.py`): changed from `list[frame.Frame]` to `tuple[list[frame.Frame], list[tuple[int, frame.Frame]]]`; callers now receive `(all_frames, marker_frames)` where each marker is an `(index, Frame)` pair so callers can locate the marker in `all_frames` without a linear scan.
  - **`ZoomData.markers` DB schema** (`frdb.py`): changed from `list[str]` (Frame hashes only) to `list[tuple[int, str]]` (index + Frame hash pairs), matching the new `Frames()` return type; existing DB entries with the old schema are not forward-compatible.
  - **`FractalDatabase.FindImage()` renamed to `FindRender()`** (`frdb.py`): the method that finds a cached render is now named `FindRender()` to distinguish it from the new `FindComputation()` method; all callers updated.
  - **`FractalDatabase.CoreComputeImage()` refactored** (`frdb.py`): the monolithic `CoreComputeImage()` method is now a thin wrapper that calls `DoComputation()` then `DoRender()`; the `require_img_obj` parameter has been removed.
  - **Zoom animation architecture overhaul** (`zoomcommand.py`): `tranz zoom auto` now (1) computes all marker frames first (calling `db.DoComputation()` only), (2) builds `ZoomColorNorm` from the marker `Image` objects for consistent cross-frame color mapping, (3) computes the remaining regular frames, and (4) renders and assembles all frames in a single streaming pass using Python generators so only one rendered frame lives in memory at a time; the GIF/MP4 is written to a `tempfile.TemporaryDirectory` first, then metadata is injected via `ReWriteAnimatedGIFMeta` / `ReWriteVideoMP4Meta` and the file is moved to its final destination.
  - **`SEAHORSE_ANIMATED_HASH`** (`base.py`): updated to reflect the new color normalization output (marker-based `ZoomColorNorm` produces a deterministically different animation).
  - **Frame generation performance optimization** (`image.py`): the frame loop now tracks magnification using a cheap float approximation instead of an mpfr call at every iteration; `limit_denominator` is applied only every 10 steps on the internal high-precision tracking frame (with a larger max_denominator), and once per step on the output reduced frame; cumulative error logging added; generation is now sub-second even for very large frame counts.
  - **`WriteAnimatedGIF` accepts lazy iterables** (`image.py`): the `frames` parameter type changed from `list[bytes]` to `abc.Iterable[bytes]`; frames are consumed lazily one at a time so they do not all need to fit in memory; the old up-front length check is replaced by a post-generation frame-count validation.
  - **`use_db` threaded into `FractalDatabase`** (`frdb.py`, `base.py`, `tranz.py`): `FractalDatabase.__init__()` now accepts a `use_db: bool` parameter (default `True`); when `False`, the DB behaves as if it does not exist — no load, no save, and all lookup/add operations are silently skipped — allowing tranZoom to run fully without any DB overhead.
  - **`FractalDatabase.LoadImageData`** (`frdb.py`): return type widened to `image.Image | None`; returns `None` when `use_db` is `False`.
  - **`FractalDatabase.AddComputationToDB` and `AddRenderToDB`** (`frdb.py`): return types widened to include `None`; return `None` when `use_db` is `False`.

- Fixed
  - **Zoom color consistency** (`image.py`, `zoomcommand.py`): each frame was previously normalized independently against its own histogram, causing visible per-frame hue shifts across long animations; the new `ZoomColorNorm` system normalizes all frames against shared marker histograms so the same escape-iteration value maps to a consistent palette position throughout the animation.
  - **Memory usage in `tranz zoom auto`** (`zoomcommand.py`): the old implementation accumulated all rendered frame bytes in a `list[bytes]` in memory before assembling the animation, requiring all frames to fit in memory simultaneously; the new generator-based approach renders and discards each frame one at a time during GIF/MP4 assembly, keeping peak memory proportional to one frame.
  - **`WriteAnimatedGIF` frame-count validation** (`image.py`): the old up-front `len(frames) != n_frames` check was incompatible with lazy iterables; the check is now done after generation by counting frames as they are consumed.

## 1.5.2 - 2026-05-27

- Added
  - **8 new palettes** (`palette.py`): `aurora` (night-sky → polar-green aurora → white), `plasma`
    (dark void → purple → magenta → white), `forest` (dark soil → forest green → lime-yellow),
    `coral` (deep abyss → teal → coral → pale pink), `gold`, `toxic`, `iris`, `ember`.
  - **`ZoomParameters.Frames()`** (`image.py`): new method to generate all `Frame` objects for a
    zoom animation, computing each zoomed frame from the initial frame and magnification.
  - **`ZoomParameters` computed properties** (`image.py`): `n_steps`, `n_seconds`, `fps`,
    `mag_per_step`, `scalar_magnification`, `scalar_magnification_per_step`.
  - **`Frame.mag2` property** (`frame.py`): magnification-squared / area-ratio, an exact `mpq`
    value without the `sqrt()` overhead; used internally by `Frame.magnification`.
  - **`FractalDatabase.FindZoom()`** (`frdb.py`): new method to look up a cached zoom (video/GIF)
    by its `ZoomParameters`.
  - **`FractalDatabase.AddZoomToDB()`** (`frdb.py`): new method to persist a rendered zoom
    (video/GIF) record in the DB, including all composed frames and marker frames.
  - **Zoom DB caching** (`zoomcommand.py`): `tranz zoom auto` now checks the DB before rendering;
    if a matching zoom entry exists and the file is on disk, it is served from cache immediately.
  - **Sentinel depth index** (`frdb.py`): new `sentinel_cps_idx` field in `_DBType` (and
    `_DBTypeFactory`) that maps a sentinel `cp_hash` (depth = `MIN_ITER` = 1000) to the actual
    `cp_hash` with the real computed depth, enabling frame recovery across sessions.
  - **CLI helper functions** (`cli/base.py`): `MakeFrameFromCLIArgs()`, `MakeFrameFromConfig()`,
    `MakeComputationParameters()`, `MakeRenderParameters()` — extracted from repeated code in
    zoom command handlers to eliminate duplication.
  - **Zoom header log line** (`zoomcommand.py`): `tranz zoom auto` now prints a summary header
    before the first frame: dimensions, palette, fractal type, magnitude, duration, FPS, frame
    count, and per-step scalar magnification percentage.
  - **Jumpy-zoom warning** (`zoomcommand.py`): if scalar magnification per frame exceeds
    `THRESHOLD_JUMPY_ZOOM_PER_FRAME`, a red warning is printed suggesting more frames or less
    total magnification.
  - **New zoom PNG metadata keys** (`image.py`): `META_ZOOM_TYPE_KEY`, `META_ZOOM_INITIAL_WIDTH_RE_KEY`,
    `META_ZOOM_INITIAL_HEIGHT_IM_KEY`, `META_ZOOM_MAGNITUDE_KEY`, `META_ZOOM_FRAMES_KEY`,
    `META_ZOOM_SECONDS_KEY`, `META_ZOOM_LOOP_KEY`, `META_ZOOM_STEPS_KEY`, `META_ZOOM_FPS_KEY`,
    `META_ZOOM_MAGNITUDE_PER_STEP_KEY`, `META_ZOOM_MAGNIFICATION_PER_STEP_KEY`.

- Changed
  - **`MAX_TOLERATED_FRAME_MAG_ERROR` and `MAX_TOLERATED_TOTAL_MAG_ERROR`** moved from
    `cli/zoomcommand.py` to `image.py` (public constants); `MAX_TOLERATED_TOTAL_MAG_ERROR` tightened
    from `0.02` (2%) to `0.0001` (0.01%) for more accurate zoom frame validation.
  - **`DEFAULT_DEST_MAGNIFICATION_10` → `DEFAULT_DEST_MAGNITUDE_10`** and
    **`MAX_ZOOM_MAGNIFICATION_10` → `MAX_ZOOM_MAGNITUDE_10`** renamed in `image.py` for
    consistency ("magnitude" = log₁₀ of the zoom factor, "magnification" = the linear factor).
    `DEFAULT_DEST_MAGNITUDE_10` is now `str = '1'` (exact rational, was `float = 1.0`).
  - **`ZoomParameters.__repr__`** updated to include `fps` and use named fields:
    `(mag:…, n:…, d:…, fps:…, l:…)` instead of the old `([MAG], [N_FRAMES], [DURATION], [LOOP])`.
  - **`FindImage()` return type** (`frdb.py`): now returns a 5-tuple
    `(ComputationParameters, ImageCoreKey, FrameData | None, ComputationData | None, ImageData | None)`;
    the first element is the (possibly depth-resolved) `ComputationParameters`; callers updated.
  - **`ZoomData.tm`** (`frdb.py`): type changed from `int | None` to `int` (always set on creation).
  - **`ZoomData.markers`** (`frdb.py`): minimum length changed from `>= 1` to `>= 2` (first & last
    frame are always markers).
  - **`DEFAULT_MPQ_ZOOM`** (`frame.py`): default zoom factor changed from `5/3` (≈ 1.67x) to `2`
    (2x).
  - **`ZoomParameters` validation** (`image.py`): added explicit FPS range check and `n_steps > 1`
    guard alongside the existing frame-count and duration checks.
  - **Breaking: animation metadata keys renamed** from `META_ANIM_*` to `META_ZOOM_*` throughout
    `image.py` and `zoomcommand.py`; existing GIF/MP4 files written by v1.5.1 will have stale
    `tranzoom:animation:*` metadata keys when read by this version.
  - **`_DBType` docstring** completed with all field descriptions (`frdb.py`).
  - `tranz zoom ai` and `tranz zoom manual` now use the new shared
    `MakeFrameFromConfig()` / `MakeComputationParameters()` / `MakeRenderParameters()` helpers.
  - **`CoreComputeImage` render info log line** (`frdb.py`): the generation log line now prints
    both `params` and `render` (`"{params} + {render}"`) instead of only `params`, giving more
    context on every fractal generation.

- Fixed
  - **AI diagonal step bug** (`ai.py`): diagonal directions (NE/SE/SW/NW) were computed using
    `width_step * DEFAULT_MPQ_STEP_DIAGONAL` and `height_step * DEFAULT_MPQ_STEP_DIAGONAL`,
    resulting in a shorter step than the cardinal directions on a square grid. Since the grid is
    square, diagonal steps now use the same distance as cardinal steps (`width_step` /
    `height_step` directly).
  - **iTerm2 display on loaded/cached images** (`ai.py`): `db.CoreComputeImage()` now returns a
    5-tuple `(params, …)` but the caller was unpacking only 4 values, causing the wrong variable
    to be used for iTerm2 display; fixed by correctly unpacking all 5 elements.
  - **Missing grid overlay on zoom start** (`ai.py`): grid overlay was not applied to the initial
    render when entering `ZoomLoop`; the render parameters are now patched with
    `OverlayType.GRID` before the loop starts (if no other overlay is set).

## 1.5.1 - 2026-05-26

- Changed
  - New ruff version

- Fixed
  - README examples

## 1.5.0 - 2026-05-26

- Added
  - **Smooth coloring** (`fractal.py`, `image.py`): the escape-time renderer now computes a fractional smooth-escape value `nu ∈ [0, 1)` for each exterior pixel using the standard normalized iteration count formula, alongside the integer iteration count `n`. Pixel data is now 8 bytes (packed `int32` + `float32` via `EncodeIntFloatTo64`/`Decode64ToIntFloat`), replacing the previous 4-byte `int32`. `NormalizeSmoothEscape()` ensures `nu` is always well-formed. Result: smooth, band-free color gradients at all zoom depths.
  - **`Image.Histogram` inner class** (`image.py`): new nested class storing a complete histogram for a pixel category (exterior or interior), with raw linear counts, raw bucket counts, cumulative variants, total count, and min/max values. `BucketCumulativeBefore()` and `InterpolateBucket()` methods enable smooth histogram-equalized color mapping using `(n, nu)` values.
  - **`Image.RebuildHistograms()`** (`image.py`): new method that rebuilds exterior and interior histograms from the current escape data, called automatically during PNG rendering.
  - **DB computation caching** (`frdb.py`): `FractalDatabase` now persists raw `Image` objects to disk (via `SaveImageData`/`LoadImageData`, using very high compression) so that re-renders of the same frame with the same computation parameters skip the expensive fractal computation entirely and go straight to PNG rendering. Cache lookup is performed at the start of every `CoreComputeImage()` call.
  - **DB render caching** (`frdb.py`): `FractalDatabase` also caches rendered PNG files; if the same frame + render parameters were already rendered and the PNG file still exists on disk, `CoreComputeImage()` returns the cached PNG immediately without re-rendering.
  - **`FractalDatabase.FindImage()`** (`frdb.py`): new method that looks up all DB records for a given `(ComputationParameters, RenderParameters)` pair, returning `(ImageCoreKey, FrameData | None, ComputationData | None, ImageData | None)`.
  - **`FractalDatabase.AddComputationToDB()`** and **`FractalDatabase.AddRenderToDB()`** (`frdb.py`): new methods for inserting computation and render records into the DB, updating timestamps on repeated renders and maintaining the path/hash indexes.
  - **`--force`/`--no-force` global flag** (`tranz.py`): new option that bypasses both computation and render caches, forcing full re-computation and re-rendering even when matching DB entries exist; default is `--no-force`.
  - **`ExistingPathsFilter` and `CoreKeyFromData`** module-level callables (`frdb.py`): `ExistingPathsFilter` filters a list of paths to those that actually exist on disk; `CoreKeyFromData` builds an `ImageCoreKey` from a `(ComputationParameters, RenderParameters)` pair.
  - New constants `BIT_31`, `BIT_32`, `BIT_64`, `MAX_UINT32` in `frame.py` for low-level bit manipulation shared with encoding/decoding helpers.
  - `scripts/benchmark.py`: new standalone script for benchmarking pixel encode/decode throughput.
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
  - Command `tranz config deletedatabase` for easy DB wipe.

- Changed
  - **Breaking: PNG metadata key prefix changed** from hardcoded `'tranzoom:'` to `f'{__app__}:'` (= `'tranZoom:'`); all PNG images written by this version use `tranZoom:*` keys; images written by older versions (`tranzoom:*`) are not readable by this version.
  - **Breaking: PNG metadata keys reorganized**: `tranzoom:image:iter_depth:min` and `tranzoom:image:iter_depth:max` removed; `tranzoom:image:iter_depth:search` renamed to `tranZoom:image:depth`; pixel count keys consolidated to `tranZoom:image:exterior:count` and `tranZoom:image:set:count`; added per-category `n:min`, `n:max`, `nu:min`, `nu:max`, `bucket:min`, `bucket:max` keys; histogram summary keys restructured to `exterior:hist:linear`, `exterior:hist:linear:cumulative`, `exterior:hist:bucket`, `exterior:hist:bucket:cumulative` (and matching `set:hist:*` variants).
  - **Breaking: `ImageData.rendered_path` → `rendered_paths`** (TypedDict field): now a `list[str]` of all known on-disk paths for a render, instead of a single `str | None`; `tm` is now always required.
  - **`CoreComputeImage()` moved from module-level function to `FractalDatabase.CoreComputeImage()` method** (`frdb.py`): the DB instance is now the dispatch point for all rendering, enabling seamless cache lookup/store; callers updated throughout (`cli/base.py`, `core/ai.py`).
  - **`require_img_obj` parameter** added to `FractalDatabase.CoreComputeImage()` and `ProduceFractalImage()`: when `False`, the returned `image.Image` may be `None` (used by static image commands that do not need the `Image` object after saving); `tranz image mandel` and `tranz image julia` pass `require_img_obj=False`.
  - **`_BuildCumulative` and `_PixelPalette` made private** (`image.py`): `BuildCumulative` renamed to `_BuildCumulative` (signature changed to accept `Iterable[tuple[int, float]]` instead of `list[int]`); `PixelPalette` renamed to `_PixelPalette`.
  - `ComputationData.raw_data_path` is now `str | None` (path is relative, managed by the DB; `None` means no raw data saved to disk for this entry).
  - `scripts/template.py` renamed to `scripts/_template.py`.
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
