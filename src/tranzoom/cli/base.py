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

from tranzoom.core import ai, fractal, frame, image, palette

# global CLI data, and some test stuff

# if `tests/data/images/demo-mandel-seahorse-tail.png` internal data changes this will change!
# this indicates that the mathematical computation or the setting of colors has changed;
# this should NOT change over metadata changes, as it is computed from raw pixel data
SEAHORSE_TAIL_HASH: str = '9191d8e0946361b47e25dbe4cb21246d3e21b27a2d7dec800b4e25fd699d6814'
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
  False,
  '--set/--no-set',
  help=(
    'If True, color the interior Set points with `--set-palette` instead of black; '
    'default is False (black)'
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


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class TranZoomConfig(clibase.CLIConfig):
  """TranZoom global context, storing the configuration."""

  img_output_path: pathlib.Path | None
  img_use_date: bool
  img_use_hash: bool
  img_path_prefix: str | None
  pal: palette.Palette
  set_pal: palette.Palette
  color_set_points: bool
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

  max_iter: int | None = None  # for `image` command
  mark_coords: str | None = None  # for `image` command
  mark_color: image.Color = image.DEFAULT_MARK_COLOR  # for `image` command
  mark_width: int = image.DEFAULT_MARK_WIDTH  # for `image` command

  max_steps: int = 0  # for `zoom` command
  fractal_type: frame.Fractal = frame.DEFAULT_FRACTAL  # for `zoom` command
  julia_re: str = frame.DEFAULT_JULIA_RE  # for `zoom` command
  julia_im: str = frame.DEFAULT_JULIA_IM  # for `zoom` command


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
      info: tbase.JSONDict = image.GetBasicDataFromPNG(img_path.read_bytes())[-1]
      if (
        image.META_CENTER_RE_KEY not in info
        or image.META_CENTER_IM_KEY not in info
        or image.META_WIDTH_RE_KEY not in info
        or image.META_HEIGHT_IM_KEY not in info
      ):
        raise ValueError(f'Image "{img_path}" missing tranZoom frame metadata keys')  # noqa: TRY301
      version: str = str(info.get(image.META_VERSION_KEY, '')) or 'UNKNOWN'
      fract: str = str(info.get(image.META_FRACTAL_KEY, '')) or 'UNKNOWN'
      print_call(
        f'Reading frame from "{img_path}", [red]tranZoom version {version}[/], {fract} fractal...'
      )
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
      info: tbase.JSONDict = image.GetBasicDataFromPNG(img_path.read_bytes())[-1]
      if image.META_CENTER_RE_KEY not in info or image.META_CENTER_IM_KEY not in info:
        raise ValueError(f'Image "{img_path}" missing tranZoom frame metadata keys')  # noqa: TRY301
      version: str = str(info.get(image.META_VERSION_KEY, '')) or 'UNKNOWN'
      fract: str = str(info.get(image.META_FRACTAL_KEY, '')) or 'UNKNOWN'
      print_call(
        f'Reading frame from "{img_path}", [red]tranZoom version {version}[/], {fract} fractal...'
      )
      return (
        gmpy2.mpq(str(info[image.META_CENTER_RE_KEY])),
        gmpy2.mpq(str(info[image.META_CENTER_IM_KEY])),
      )
    except Exception as err2:  # this error we cannot forgive
      raise click.UsageError(f'Error/not path: {point_re=}, {point_im=}') from err2
  except Exception as err:  # this error we cannot forgive
    raise click.UsageError(f'Error: {point_re=}, {point_im=}') from err
