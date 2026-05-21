# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Base."""

from __future__ import annotations

import dataclasses
import pathlib
from collections import abc

import click
import gmpy2
import typer
from transcrypto.cli import clibase
from transcrypto.utils import base as tbase
from transcrypto.utils import timer

from tranzoom.core import ai, fractal, frame, image, palette

# global CLI data, and some test stuff

# if `tests/data/images/demo-mandel-seahorse-tail.png` internal data changes this will change!
# this indicates that the mathematical computation or the setting of colors has changed;
# this should NOT change over metadata changes, as it is computed from raw pixel data
SEAHORSE_TAIL_HASH: str = 'bc8befe1492f4d296cf93994ba201ef06c3fa4858a47a657bb7f136f42bceb5d'
SEAHORSE_ANIMATED_HASH: str = '91b99d972c26a6a4d6116064b4528136a9104436cac3d9f48d679df37a875d97'
SUZANA_WAVE_HASH: str = '4be1409a9c55b4f9cbe21f45fa29d0bfc11622bffc248a5639fbffdea0cd80fe'
# this is tested from `tests/cli/base_test.py` & `tests_integration/test_installed_cli.py`!

# CLI options that can be re-used

DEFAULT_IMAGE_PREFIX: dict[frame.Fractal, str] = {
  frame.Fractal.MANDELBROT: 'mandel',
  frame.Fractal.JULIA: 'julia',
}
DEFAULT_VISION_MODEL: str = 'qwen3-vl-32b-instruct@q8_0'

# Image: output image
IMAGE_WIDTH_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_IMAGE_SIZE,
  '-w',
  '--width',
  min=frame.MIN_IMAGE_SIZE,
  max=frame.MAX_IMAGE_SIZE,
  help=(
    f'Width of the image; {frame.MIN_IMAGE_SIZE} ≤ w ≤ {frame.MAX_IMAGE_SIZE}; '
    f'default is {frame.DEFAULT_IMAGE_SIZE}'
  ),
)
IMAGE_HEIGHT_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_IMAGE_SIZE,
  '-h',
  '--height',
  min=frame.MIN_IMAGE_SIZE,
  max=frame.MAX_IMAGE_SIZE,
  help=(
    f'Height of the image; {frame.MIN_IMAGE_SIZE} ≤ h ≤ {frame.MAX_IMAGE_SIZE}; '
    f'default is {frame.DEFAULT_IMAGE_SIZE}'
  ),
)
IMAGE_SIZE_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '-s',
  '--size',
  min=frame.MIN_IMAGE_SIZE,
  max=frame.MAX_IMAGE_SIZE,
  help=(
    'Size of the image: *overrides* both `-w/--width` and `-h/--height` by determining the '
    'max pixel length of the final image, which will be proportional to the given frame, i.e., '
    'the final dimensions will be scaled accordingly and, given a size S, will be either '
    '(S, x), (x, S) or (S, S), where x < S, and will make the final image ratio/proportion be '
    f'the same as the frame; {frame.MIN_IMAGE_SIZE} ≤ S ≤ {frame.MAX_IMAGE_SIZE}; '
    'default is None, i.e., follow the explicit `-w/--width` and `-h/--height` options'
  ),
)
IMAGE_ZOOM_WIDTH_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_ZOOM_SIZE,
  '-w',
  '--width',
  min=frame.MIN_IMAGE_SIZE,
  max=frame.MAX_IMAGE_SIZE,
  help=(
    f'Width of the image; {frame.MIN_IMAGE_SIZE} ≤ w ≤ {frame.MAX_IMAGE_SIZE}; '
    f'default is {frame.DEFAULT_ZOOM_SIZE}'
  ),
)
IMAGE_ZOOM_HEIGHT_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_ZOOM_SIZE,
  '-h',
  '--height',
  min=frame.MIN_IMAGE_SIZE,
  max=frame.MAX_IMAGE_SIZE,
  help=(
    f'Height of the image; {frame.MIN_IMAGE_SIZE} ≤ h ≤ {frame.MAX_IMAGE_SIZE}; '
    f'default is {frame.DEFAULT_ZOOM_SIZE}'
  ),
)
IMAGE_PATH_OUTPUT_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '-o',
  '--out',
  exists=True,
  file_okay=False,
  dir_okay=True,
  readable=True,
  writable=True,
  help=(
    'The local output root directory path, ex: "~/foo/bar/"; '
    'if not given, the image will be saved in the current working directory'
  ),
)
IMAGE_PREFIX_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--prefix',
  help=(
    'Image save prefix; default: None, meaning use "mandel" for Mandelbrot and "julia" for Julia '
    '(the final file name will be "<prefix>[-<date>][-<hash20>].png", note the date and the hash '
    'can be turned off with --no-date and --no-hash, respectively)'
  ),
)
IMAGE_INCLUDE_DATE_OPTION: typer.models.OptionInfo = typer.Option(
  True,
  '--date/--no-date',
  help=(
    'If True, file names will include the date-time as YYYYMMDDhhmmss; '
    'if False, file names will not include the date-time; default is True'
  ),
)
IMAGE_INCLUDE_HASH_OPTION: typer.models.OptionInfo = typer.Option(
  True,
  '--hash/--no-hash',
  help=(
    'If True, file names will include the hash; '
    'if False, file names will not include the hash; default is True'
  ),
)
IMAGE_PRINT_ITERM_OPTION: typer.models.OptionInfo = typer.Option(
  False,
  '--iterm/--no-iterm',
  help=(
    'If True, will output the image to iTerm2 '
    '(only use on macOS with iTerm2! <https://iterm2.com/documentation-images.html>); '
    'if False, will not output the image to iTerm2; default is False'
  ),
)

# Image: input image
IMAGE_PATH_INPUT_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  ...,
  exists=True,
  file_okay=True,
  dir_okay=False,
  readable=True,
  writable=False,
  help=('The local input file path, ex: "~/foo/bar/file.png"'),
)

# Frame: the default frame is the one that shows the whole Mandelbrot set, which is centered at
# -0.75+0j and has width 2.5; the height is the same as the width by default;
# The set <https://en.wikipedia.org/wiki/Mandelbrot_set> is contained in the rectangle with corners
# -2.5-1.25j and 0.5+1.25j, which is exactly our default here
FRAME_CENTER_RE_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_FRAME_CENTER_RE,
  help=(
    'Real part of the center point; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    'ALTERNATIVELY: you can use this to input an existing PNG image path, and it will read the '
    "frame from the given image's metadata (overriding/ignoring the other CLI frame parameters!); "
    f'default is {frame.DEFAULT_FRAME_CENTER_RE!r}'
  ),
)
FRAME_CENTER_IM_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_FRAME_CENTER_IM,
  help=(
    'Imaginary part of the center point; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'default is {frame.DEFAULT_FRAME_CENTER_IM!r}'
  ),
)
FRAME_WIDTH_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_FRAME_SIZE,
  help=(
    'Width of the frame in the real plane; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'default is {frame.DEFAULT_FRAME_SIZE!r}'
  ),
)
FRAME_HEIGHT_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  None,
  help=(
    'Height of the frame in the imaginary plane; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    'default is None, i.e, the same as width'
  ),
)
JULIA_RE_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_JULIA_RE,
  help=(
    'Real part of the Julia Set constant; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    'ALTERNATIVELY: you can use this to input an existing PNG image path, and it will read the '
    "Julia Set constant from the given image's metadata frame *CENTER* "
    f'(overriding/ignoring the imaginary parameter part!); default is {frame.DEFAULT_JULIA_RE!r}'
  ),
)
JULIA_RE_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_JULIA_RE,
  help=(
    'Real part of the Julia Set constant; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    'ALTERNATIVELY: you can use this to input an existing PNG image path, and it will read the '
    "Julia Set constant from the given image's metadata frame *CENTER* "
    f'(overriding/ignoring the imaginary parameter part!); default is {frame.DEFAULT_JULIA_RE!r}'
  ),
)
JULIA_IM_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_JULIA_IM,
  help=(
    'Imaginary part of the Julia Set constant; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'default is {frame.DEFAULT_JULIA_IM!r}'
  ),
)
JULIA_IM_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_JULIA_IM,
  help=(
    'Imaginary part of the Julia Set constant; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'default is {frame.DEFAULT_JULIA_IM!r}'
  ),
)
JULIA_CENTER_RE_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_JULIA_CENTER_RE,
  help=(
    'Real part of the center point; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    'ALTERNATIVELY: you can use this to input an existing PNG image path, and it will read the '
    "frame from the given image's metadata (overriding/ignoring the other CLI frame parameters!); "
    f'default is {frame.DEFAULT_JULIA_CENTER_RE!r}'
  ),
)
JULIA_CENTER_IM_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_JULIA_CENTER_IM,
  help=(
    'Imaginary part of the center point; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'default is {frame.DEFAULT_JULIA_CENTER_IM!r}'
  ),
)
JULIA_WIDTH_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_JULIA_WIDTH,
  help=(
    'Width of the frame in the real plane; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'default is {frame.DEFAULT_JULIA_WIDTH!r}'
  ),
)
JULIA_HEIGHT_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  frame.DEFAULT_JULIA_HEIGHT,
  help=(
    'Height of the frame in the imaginary plane; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'default is {frame.DEFAULT_JULIA_HEIGHT!r}'
  ),
)
MARK_COORDINATES_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--mark',
  help=(
    'A point formatted as "(re, im)" to add a crosshair overlay, `re` and `im` multi-precision; '
    'this can be a float (ex: "(0.34, -0.56)") or a fraction of ints '
    '(rational numbers, ex: "(123/451, 789/1011)") or any combination of these, and '
    'the numbers will be fed directly to multi-precision arithmetic so no precision is lost; '
    'default is None, i.e., do not mark overlay on the image'
  ),
)
MARK_COLOR_OPTION: typer.models.OptionInfo = typer.Option(
  image.DEFAULT_MARK_COLOR.name.lower(),
  '--mark-color',
  help=(
    f'Color of the crosshair overlay; default is "{image.DEFAULT_MARK_COLOR.name.lower()}"; '
    'available colors: ' + ', '.join(sorted(repr(c.name.lower()) for c in image.Color))
  ),
)
MARK_WIDTH_OPTION: typer.models.OptionInfo = typer.Option(
  image.DEFAULT_MARK_WIDTH,
  '--mark-width',
  min=image.MIN_MARK_WIDTH,
  max=image.MAX_MARK_WIDTH,
  help=(
    f'Width of the crosshair overlay; {image.MIN_MARK_WIDTH} ≤ w ≤ {image.MAX_MARK_WIDTH}; '
    f'default is {image.DEFAULT_MARK_WIDTH}'
  ),
)

# Computation Options
FRACTAL_TYPE_OPTION: typer.models.OptionInfo = typer.Option(
  frame.DEFAULT_FRACTAL,
  '-f',
  '--fractal',
  help=(
    f'Fractal type to generate; '
    f'possible values: {", ".join(repr(f.value) for f in frame.Fractal)}; '
    f'default: {frame.DEFAULT_FRACTAL.value!r}'
  ),
)
MAX_ITERATIONS_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '-i',
  '--iter',
  min=frame.MIN_ITER,
  max=frame.MAX_ITER,
  help=(
    'Maximum iterations (depth) to compute before determining escape; '
    f'{frame.MIN_ITER} ≤ iter ≤ {frame.MAX_ITER}; '
    f'default is None (automatic search for optimal iterations --- recommended)'
  ),
)
MAX_THREADS_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--threads',
  min=1,
  max=fractal.MAX_CONCURRENCE,
  help=(
    'Number of threads to use for rendering; default is None, which means to use all available '
    f'CPU cores; will be limited to {fractal.MAX_CONCURRENCE} threads'
  ),
)
MAX_STEPS_OPTION: typer.models.OptionInfo = typer.Option(
  0,
  '-n',
  '--max-steps',
  min=0,
  help=(
    'Maximum number of zoom steps to run; 0 means run until manually stopped (Ctrl+C); '
    'default is 0 (unlimited, run forever)'
  ),
)

# Color options
PALETTE_OPTION: typer.models.OptionInfo = typer.Option(
  palette.DEFAULT_PALETTE,
  '--palette',
  help=(
    f'Color palette to use for rendering; default is {palette.DEFAULT_PALETTE.value!r}; '
    f'available palettes: {sorted(p.value for p in palette.PALETTES)}'
  ),
)
SET_PALETTE_OPTION: typer.models.OptionInfo = typer.Option(
  palette.DEFAULT_SET_PALETTE,
  '--set-palette',
  help=(
    f'Color palette to use for rendering the interior Set points; '
    f'default is {palette.DEFAULT_SET_PALETTE.value!r}; '
    f'available palettes: {sorted(p.value for p in palette.PALETTES)}'
  ),
)
COLOR_SET_POINTS_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--set',
  help=(
    'Which algorithm to use for coloring the interior Set points, either None, or one of '
    f'{", ".join(repr(a.value) for a in frame.SetHighlightAlgorithm)}; '
    'default is None, do not color the Set points (i.e., they will be black)'
  ),
)

# AI Options
MODEL_OPTION: typer.models.OptionInfo = typer.Option(
  DEFAULT_VISION_MODEL,
  '-m',
  '--model',
  help=(
    'LLM vision model to load and use: '
    'the model must be compatible with the LMStudio client libraries and must support vision; '
    'will NOT get the model for you, so make sure you either have it available in your LMStudio; '
    'should be a string you would use with `lms get <THIS>` or `https://huggingface.co/<THIS>`; '
    f'default: {DEFAULT_VISION_MODEL!r}, a good general-purpose vision model'
  ),
)
AI_QUERY_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '-q',
  '--query',
  help=('Query to be added to the default prompt; default is None, no additional query'),
)
MAX_CHAT_MEMORY_OPTION: typer.models.OptionInfo = typer.Option(
  ai.DEFAULT_MEMORY_SIZE,
  '--memory',
  min=0,
  max=ai.MAX_MEMORY_SIZE,
  help=(
    f'Maximum number of iterations the LLM will remember; 0 ≤ m ≤ {ai.MAX_MEMORY_SIZE}; '
    f'0 (zero) means no memory, every AI call is independent; default is {ai.DEFAULT_MEMORY_SIZE}'
  ),
)
AI_OUTPUT_REASON_FIELD_OPTION: typer.models.OptionInfo = typer.Option(
  False,
  '--reason/--no-reason',
  help=(
    'If True, LLM sector evaluations will include an extra `reason` field for the AI output, '
    'which is great for debugging and understanding the LLM, but is much slower on the LLM; '
    'if False, the field will not be included, which is faster; default is False'
  ),
)

# Animation Options
ANIM_DEST_MAGNIFICATION_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  image.DEFAULT_DEST_MAGNIFICATION_10,
  min=-image.MAX_ZOOM_MAGNIFICATION_10,
  max=image.MAX_ZOOM_MAGNIFICATION_10,
  help=(
    'Magnification magnitude to go through in the animation zoom; '
    'ATTENTION!! this is exponential 10**mag, so a value of 2.0 means 10**2 = 100x zoom; '
    f'default is {image.DEFAULT_DEST_MAGNIFICATION_10:.2f}, '
    f'i.e., {10**image.DEFAULT_DEST_MAGNIFICATION_10:.2f}x zoom'
  ),
)
ANIM_DURATION_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--duration',
  min=image.MIN_DURATION,
  max=image.MAX_DURATION,
  help=(
    f'GIF/video duration, in seconds; {image.MIN_DURATION} ≤ d ≤ {image.MAX_DURATION} or None; '
    'pick 2 out of `--duration`, `--frames` and `--fps`, and the third will be computed; '
    f'default is None'
  ),
)
ANIM_FRAMES_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--frames',
  min=image.MIN_FRAMES,
  max=image.MAX_FRAMES,
  help=(
    f'Number of frames in GIF/video; {image.MIN_FRAMES} ≤ fr ≤ {image.MAX_FRAMES} or None; '
    'pick 2 out of `--duration`, `--frames` and `--fps`, and the third will be computed; '
    f'default is None'
  ),
)
ANIM_FPS_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--fps',
  min=image.MIN_FPS,
  max=image.MAX_FPS,
  help=(
    f'Frames per second (FPS) for the GIF/video; {image.MIN_FPS} ≤ fps ≤ {image.MAX_FPS} or None; '
    'pick 2 out of `--duration`, `--frames` and `--fps`, and the third will be computed; '
    f'default is None'
  ),
)
ANIM_TYPE_OPTION: typer.models.OptionInfo = typer.Option(
  image.DEFAULT_ANIMATION_TYPE,
  '--anim',
  help=(
    f'Type of animation to produce; possible values: '
    f'{", ".join(repr(t.value) for t in image.AnimationType)}; '
    f'default is "{image.DEFAULT_ANIMATION_TYPE.value}"'
  ),
)
ANIM_LOOP_OPTION: typer.models.OptionInfo = typer.Option(
  image.DEFAULT_LOOP,
  '--loop',
  min=image.MIN_LOOP,
  max=image.MAX_LOOP,
  help=(
    f'Number of loops for the GIF (NOT MP4!); {image.MIN_LOOP} ≤ loop ≤ {image.MAX_LOOP}; '
    f'default is {image.DEFAULT_LOOP}; zero (0) means infinite loops'
  ),
)
ANIM_SAVE_FRAMES_OPTION: typer.models.OptionInfo = typer.Option(
  False,
  '--save-frames/--no-save-frames',
  help=(
    'If True, will save the intermediate frames of the animation; '
    'if False, intermediate frames will not be saved; default is False'
  ),
)


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class TranZoomConfig(clibase.CLIConfig):
  """TranZoom global context, storing the configuration."""

  img_output_path: pathlib.Path | None
  img_use_date: bool
  img_use_hash: bool
  img_path_prefix: str | None
  pal: palette.Palette
  set_pal: palette.Palette
  set_points: frame.SetHighlightAlgorithm | None
  max_threads: int | None
  model: str
  spec_tokens: int | None
  seed: int | None
  context: int
  temperature: float
  gpu: float
  gpu_layers: int
  fp16: bool
  use_mmap: bool
  flash: bool
  kv_cache: int | None
  timeout: float
  iterm: bool

  img_width: int = frame.DEFAULT_IMAGE_SIZE  # both `image` and `zoom` use, different defaults
  img_height: int = frame.DEFAULT_IMAGE_SIZE  # both `image` and `zoom` use, different defaults
  img_size: int | None = None  # for `image` and `zoom` commands, overrides width/height if given

  max_iter: int | None = None  # for `image` command, also `zoom auto`
  mark_coords: str | None = None  # for `image` command, also `zoom auto`
  mark_color: image.Color = image.DEFAULT_MARK_COLOR  # for `image` command, also `zoom auto`
  mark_width: int = image.DEFAULT_MARK_WIDTH  # for `image` command, also `zoom auto`

  max_steps: int = 0  # for `zoom` command
  fractal_type: frame.Fractal = frame.DEFAULT_FRACTAL  # for `zoom` command
  julia_re: str = frame.DEFAULT_JULIA_RE  # for `zoom` command
  julia_im: str = frame.DEFAULT_JULIA_IM  # for `zoom` command


def ProduceFractalImage(
  frm: frame.Frame,
  config: TranZoomConfig,
  *,
  tm: int | None = None,
  add_serial: int | None = None,
  save_image: bool = True,
) -> tuple[image.Image, bytes, str]:
  """Produce fractal image from a frame and a config, and save it to disk, print it to iTerm2, etc.

  Args:
    frm: the frame to produce the image from; must be already validated and ready for rendering
    config: the global configuration with all the options needed for rendering and saving the image
    tm (int | None): Optional timestamp to use for the date in the file name. If None, the
        current time is used.
    add_serial (int | None): Optional serial number to include in the file name for uniqueness;
        if None, no serial number is included; if provided, it is formatted as a zero-padded
        5-digit number between the date and hash.
    save_image (bool): If True, will save the final image to disk; if False, the image will
        not be saved; default is True.

  Returns:
    A tuple of (image.Image object, raw PNG bytes, internal hash of the raw PNG)

  This is a high-level function that takes care of all the steps needed to produce the final image,
  including:
  - determining the image dimensions from the config
  - logging the rendering parameters
  - rendering the image from the frame using the fractal module
  - converting the rendered image to PNG and getting its hash
  - optionally adding a crosshair overlay if mark coordinates are given
  - saving the image to disk with a name based on the date and hash
  - optionally printing the image to iTerm2 if the corresponding option is set

  """
  # determine width and height
  width: int
  height: int
  width, height = (
    frm.PixelDimensionsFromSize(config.img_size)
    if config.img_size
    else (config.img_width, config.img_height)
  )
  # add the mark?
  mark_coords: tuple[int, int] | None = (
    frm.CoordsTupleToPixel(config.mark_coords, width, height)
    if config.mark_coords  # do this early to check the inputs ASAP
    else None
  )
  # log
  set_points_str: str = f', "{config.set_points.value}" interior' if config.set_points else ''
  config.console.print(
    f'\n{width}x{height} {frm.fractal.value.capitalize()} in '
    f'frame {frm}, precision ± {frm.Precision(width, height)} bits, '  # approx: b/c iters
    f'10^{frm.magnification[1]:.2f} magnitude, '
    f'{"AUTO" if config.max_iter is None else config.max_iter} iterations'
    f'{set_points_str}...'
  )
  # render the image
  raw_png: bytes
  raw_hash: str
  with timer.Timer(emit_log=False) as tmr:
    img: image.Image = {
      frame.Fractal.MANDELBROT: fractal.Mandelbrot,
      frame.Fractal.JULIA: fractal.Julia,
    }[frm.fractal](
      frm,  # type: ignore[arg-type]  # we know this is the right type of frame
      width,
      height,
      max_iter=config.max_iter,
      set_points=config.set_points,
      n_processes=config.max_threads,
      print_comm=config.console.print,
    )
    # fractal is ready, convert to PNG
    raw_png, raw_hash = img.AsPNG(
      pal=config.pal, set_pal=config.set_pal, set_points=config.set_points
    )
    if mark_coords:
      # we were asked to mark a coordinate with a crosshair overlay: do it
      raw_png = image.DrawCrossOverlay(
        raw_png, mark_coords[0], mark_coords[1], col=config.mark_color, lw=config.mark_width
      )
  # print stats
  config.console.print(f'{frm.fractal.value.capitalize()} image {raw_hash!r} in {tmr}')
  # save the image to a file named by its time/hash
  if save_image:
    full_path: pathlib.Path = image.MakeImagePath(
      config.img_output_path,
      config.img_use_date,
      config.img_use_hash,
      config.img_path_prefix or DEFAULT_IMAGE_PREFIX[frm.fractal],
      raw_hash,
      tm=tm,
      add_serial=add_serial,
    )
    full_path.write_bytes(raw_png)
    config.console.print(f'Saved to "{full_path}"')
  config.console.print()
  # iterm
  if config.iterm:
    image.PrintITerm2(raw_png)
    config.console.print()
  return (img, raw_png, raw_hash)


def MakeFrameFromCLIArgs(
  fractal: frame.Fractal,
  center_re: str,
  center_im: str,
  f_width: str,
  f_height: str | None,
  print_call: abc.Callable[[str], None],
) -> frame.Frame:
  """Make a frame or die. Tries float/mpq first, then tries reading from a file metadata.

  Args:
    fractal: the fractal type to create the frame for
    center_re: the real part of the center, or an image path to read the frame from
    center_im: the imaginary part of the center (ignored if center_re is an image path)
    f_width: the width of the frame (ignored if center_re is an image path)
    f_height: the height of the frame (ignored if center_re is an image path)
    print_call: a callable to print messages, used for logging during frame creation

  Returns:
    A valid frame object

  Raises:
    click.UsageError: if arguments can't be turned into a valid frame
    ValueError: internally (but this is caught and turned into UsageError with a helpful message)

  """
  try:
    # the happy path is one line... if these coords work, we return the frame and we're done
    return frame.Frame.FromCenter(fractal, center_re, center_im, f_width, f_height)
  except ValueError as err:
    if 'invalid' not in str(err).lower():
      raise click.UsageError(f'Error: {center_re=}, {center_im=}, {f_width=}, {f_height=}') from err
    # maybe the user gave us an image path instead of coordinates? let's try to read it as image
    try:
      # convert and validate path
      img_path: pathlib.Path = pathlib.Path(center_re).expanduser().resolve()
      if not img_path.exists() or not img_path.is_file():
        raise ValueError(f'Image "{img_path}" does not exist or is not a file')  # noqa: TRY301
      # make sure we have the needed metadata
      info: tbase.JSONDict = image.GetBasicDataFromImage(img_path.read_bytes())[-1]
      if (
        image.META_CENTER_RE_KEY not in info
        or image.META_CENTER_IM_KEY not in info
        or image.META_WIDTH_RE_KEY not in info
        or image.META_HEIGHT_IM_KEY not in info
      ):
        raise ValueError(f'Image "{img_path}" missing tranZoom frame metadata keys')  # noqa: TRY301
      fract: str = str(info.get(image.META_FRACTAL_KEY, '')) or 'UNKNOWN'
      print_call(f'Reading frame from "{img_path}", [red]tranZoom[/], {fract} fractal...')
      return frame.Frame.FromCenter(
        fractal,
        str(info[image.META_CENTER_RE_KEY]),
        str(info[image.META_CENTER_IM_KEY]),
        str(info[image.META_WIDTH_RE_KEY]),
        str(info[image.META_HEIGHT_IM_KEY]),
      )
    except Exception as err2:  # this error we cannot forgive
      raise click.UsageError(
        f'Error/not path: {center_re=}, {center_im=}, {f_width=}, {f_height=}'
      ) from err2
  except Exception as err:  # this error we cannot forgive
    raise click.UsageError(f'Error: {center_re=}, {center_im=}, {f_width=}, {f_height=}') from err


def MakePointFromCLIArgs(
  point_re: frame.ExactInputType,
  point_im: frame.ExactInputType,
  print_call: abc.Callable[[str], None],
) -> tuple[gmpy2.mpq, gmpy2.mpq]:
  """Make a point or die. Tries float/mpq first, then tries reading from a file metadata.

  Args:
    point_re: the real part of the point
    point_im: the imaginary part of the point
    print_call: a callable to print messages, used for logging during frame creation

  Returns:
    A valid point

  Raises:
    click.UsageError: if arguments can't be turned into a valid point
    ValueError: internally (but this is caught and turned into UsageError with a helpful message)

  """
  try:
    # the happy path is simple... if these conversions work, we return the point and we're done
    cx: gmpy2.mpq = point_re if isinstance(point_re, gmpy2.mpq) else gmpy2.mpq(point_re)
    cy: gmpy2.mpq = point_im if isinstance(point_im, gmpy2.mpq) else gmpy2.mpq(point_im)
    return (cx, cy)
  except ValueError as err:
    if 'invalid' not in str(err).lower():
      raise click.UsageError(f'Error: {point_re=}, {point_im=}') from err
    # maybe the user gave us an image path instead of coordinates? let's try to read it as image
    try:
      # convert and validate path
      img_path: pathlib.Path = pathlib.Path(str(point_re)).expanduser().resolve()
      if not img_path.exists() or not img_path.is_file():
        raise ValueError(f'Image "{img_path}" does not exist or is not a file')  # noqa: TRY301
      # make sure we have the needed metadata
      info: tbase.JSONDict = image.GetBasicDataFromImage(img_path.read_bytes())[-1]
      if image.META_CENTER_RE_KEY not in info or image.META_CENTER_IM_KEY not in info:
        raise ValueError(f'Image "{img_path}" missing tranZoom frame metadata keys')  # noqa: TRY301
      fract: str = str(info.get(image.META_FRACTAL_KEY, '')) or 'UNKNOWN'
      print_call(f'Reading frame from "{img_path}", [red]tranZoom[/], {fract} fractal...')
      return (
        gmpy2.mpq(str(info[image.META_CENTER_RE_KEY])),
        gmpy2.mpq(str(info[image.META_CENTER_IM_KEY])),
      )
    except Exception as err2:  # this error we cannot forgive
      raise click.UsageError(f'Error/not path: {point_re=}, {point_im=}') from err2
  except Exception as err:  # this error we cannot forgive
    raise click.UsageError(f'Error: {point_re=}, {point_im=}') from err
