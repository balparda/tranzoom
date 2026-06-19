# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Base."""

from __future__ import annotations

import dataclasses
import enum
import logging
import pathlib
import tempfile
import warnings
from collections import abc
from typing import NoReturn, TypedDict, cast

import gmpy2
import tqdm
import tqdm.rich
import typer
import typer._click.exceptions
from tqdm.std import TqdmExperimentalWarning
from transcrypto.cli import clibase
from transcrypto.core import aes, hashes
from transcrypto.utils import human, timer

from tranzoom import __version__
from tranzoom.core import ai, fractal, frame, frdb, image, palette, pixels, zoom


class Error(ai.Error, typer._click.exceptions.ClickException):  # noqa: SLF001
  """Base CLI/click exception."""


class UsageError(Error, typer._click.exceptions.UsageError):  # noqa: SLF001
  """Base CLI/click usage exception."""


# CLI enumerations


class CleanupOutputFormat(enum.Enum):
  """Output format for the cleanup command."""

  JPEG = 'jpeg'
  JPG = 'jpg'
  PNG = 'png'  # TODO: support formats: gif/mp4 videos


# how many frames to compute before saving to DB
_N_FRAMES_PER_DB_SAVE: int = 5

# gmpy2.mpq constants
_MPQ_ZERO: gmpy2.mpq = gmpy2.mpq('0')


# global CLI data, and some test stuff

# if any of these hashes change: the mathematical computation or the setting of colors has changed!
# this should NOT change over metadata changes, as it is computed from raw pixel data
# PNG - really only change if core computation changes, so these are more important to be stable
SEAHORSE_TAIL_HASH: str = '525aaf4c4a58391f1386889a54d54dfb91f099050af5783f97322e1f33e8b275'
SUZANA_WAVE_HASH: str = 'c748e691dbbfbec2c7008cb902f608e99f11950be2f469f0231a276bc8dbf3a2'
# GIF - these may change for core computation, or if the animation frame machinery changes
SEAHORSE_ANIMATED_HASH: str = 'd9204b9c2aec64555ca7ce48226301684737cce8b673febe86629c2e8a36ae19'
T_GIF_SEAHORSE_HASH: str = 'b4b514074d358c97ec2440557f920329195f8b1fb6ba38285c6dcb06c368119a'
T_GIF_SEEDS_300_HASH: str = 'b94ceeda67d96a2ce9f79a122d387e366c80799258b4bb02b2b5d17f93cb5d0e'
T_GIF_JULIA_SUZANA_HASH: str = '22d7b81e71b5f7a8c04950b627050a3e466ff0d3241fb4f720999c17d57db571'
T_GIF_JULIA_DRAGON_HASH: str = 'f749955dc69b0c5282c75e5470f7b132824e0b4deb5af6e8c8339a4bea040a3b'
T_GIF_JULIA_BLOB_HASH: str = 'a50bd733d704f9e5d2e726035bcef87b606b5adfed1b506dfe5bb9d36d3b57bd'
# SHA of all the frame's data - like above: computation or animation frame machinery changes
TEST_IMAGE_DATA_HASHES: dict[str, tuple[int, str]] = {
  # name: (number of frames, hash of all the frames)
  # these are the hashes of the raw object data of the frame pickled to disk, not to be confused
  # with the frames' hash we compute; both are data dependent only, but they WILL BE DIFFERENT
  'seahorse': (31, 'b9d56f228b0b4d31d116c37109d9af5eeb5ac3d707a440e4970f186137954ce1'),
  'seeds300': (10, '54c49efbaf685916ad0240d14ec070934a6cd604e4eecb447be637f85a89bfac'),
  'suzana': (21, '57fb14828e1adeebd6c8fa5d3fe7f75ac0a4cf8e5864235ff77dc89aa20dbca5'),
  'dragon': (8, '23fbaca543e2e319ab621d964772b32b04dc5605160a83f031bee38444403f9a'),
  'blob': (8, 'd7e54a7b817cca30ae14b9ad03d8c81bd72e8c8ece62fdf8dc569de7d030c917'),
}
# these are tested from `tests/cli/base_test.py`, `tests_integration/test_installed_cli.py`, and
# `tests_integration/test_cython_equivalence.py`!

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
    'NOTE: if `--i-pixels` is given, the effective width will be w*(i+1), so keep that in mind; '
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
    'NOTE: if `--i-pixels` is given, the effective height will be h*(i+1), so keep that in mind; '
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
    'NOTE: if `--i-pixels` is given, the effective Size will be s*(i+1), so keep that in mind; '
    'default is None, i.e., follow the explicit `-w/--width` and `-h/--height` options'
  ),
)
IMAGE_INTERPOLATION_PIXELS_OPTION: typer.models.OptionInfo = typer.Option(
  0,
  '--i-pixels',
  min=0,
  max=frame.MAX_INTERPOLATION_PIXELS,
  help=(
    'Extra interpolated pixels for every produced pixel; '
    'effectively, final width=w*(i+1) and height=h*(i+1); '
    f'0 ≤ i ≤ {frame.MAX_INTERPOLATION_PIXELS}; default is 0; '
    'so 0 is no interpolation, 1 means add 1 interpolated pixel between every pair of pixels, etc'
  ),
)
IMAGE_INTERPOLATION_RESAMPLE_OPTION: typer.models.OptionInfo = typer.Option(
  pixels.DEFAULT_RESAMPLING.name.lower(),
  '--resample',
  help=(
    f'Interpolation resampling method; default is "{pixels.DEFAULT_RESAMPLING.name.lower()}"; '
    '"bilinear" has the most stable results; "lanczos" is the most accurate but slowest; '
    'available values: ' + ', '.join(sorted(repr(c.name.lower()) for c in pixels.Resampling))
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
USE_DB_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--db/--no-db',
  help=(
    'Use local DB in `--db`? True means use it, False means do not use it; default is False; '
    'this option can also be loaded from the disk config, but if given should override the config'
  ),
)
READONLY_DB_OPTION: typer.models.OptionInfo = typer.Option(
  False,
  '--readonly-db/--no-readonly-db',
  help=(
    'Use local DB in readonly mode? True means DB may be read from but not altered; '
    'default is False, i.e., fully functional read+write DB'
  ),
)
DB_PATH_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '-d',
  '--db-path',
  exists=True,
  file_okay=False,
  dir_okay=True,
  readable=True,
  writable=True,
  help=(
    'The local DB root directory path, ex: "~/foo/bar/"; '
    'if not given (DEFAULT), the DB will be saved in the current app config directory, i.e.: '
    'on MacOS this is "/Users/[user]/Library/Application Support/[app_name]{/[version]}"; '
    'on Windows: "C:\\Users\\[user]\\AppData\\Local{\\[app_author]}\\[app_name]{\\[version]}"; '
    'on Linux: "/home/[user]/.config/[app_name]{/[version]}"'
  ),
)
USE_DB_COMPRESSION_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--db-compression/--no-db-compression',
  help=(
    'Use compression for the local DB to save space? '
    'True means use it but the file will be unreadable by humans, '
    'False means do not use it and file will be readable; '
    'default is False, a larger, readable file; '
    'this option can also be loaded from the disk config, but if given should override the config'
  ),
)
DB_PASSWORD_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--pass',
  help=(
    'DB password to encrypt the local DB and computation data; '
    'do NOT provide it for no encryption (DEFAULT); '
    'provide it empty ("") for terminal password input, i.e., '
    '`--pass ""` will prompt the user for a password, and this is safer because the '
    'password will not show in the shell history; '
    'your third option is to provide the password directly in the CLI, i.e., '
    '`--pass "my.password"`, but this is not recommended unless you are calling the CLI '
    'from a script and have other means to protect the password, because the password will '
    'be visible in the shell history and process list; '
    'the password provided by CLI or by user input will never be persisted to disk or logs; '
    'NOTE: if you encrypt your data, it WILL be compressed, i.e., '
    'the `--db-compression` option will be ignored and treated as True'
  ),
)
IMAGE_FORCE_REDO_OPTION: typer.models.OptionInfo = typer.Option(
  False,
  '--force/--no-force',
  help=(
    'If True, forces re-computation and re-saving of the image(s)/computation(s) even if an '
    'image/computation with the same parameters already exists; if False will use existing (DB) '
    'entries to avoid redundant computations/rendering as much as possible/reasonable; '
    'default is False, so we will try to avoid redundant computations/rendering'
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
  '--julia-re',
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
  '--julia-im',
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
  pixels.DEFAULT_MARK_COLOR.name.lower(),
  '--mark-color',
  help=(
    f'Color of the crosshair overlay; default is "{pixels.DEFAULT_MARK_COLOR.name.lower()}"; '
    'available colors: ' + ', '.join(sorted(repr(c.name.lower()) for c in pixels.Color))
  ),
)
MARK_WIDTH_OPTION: typer.models.OptionInfo = typer.Option(
  pixels.DEFAULT_MARK_WIDTH,
  '--mark-width',
  min=pixels.MIN_MARK_WIDTH,
  max=pixels.MAX_MARK_WIDTH,
  help=(
    f'Width of the crosshair overlay; {pixels.MIN_MARK_WIDTH} ≤ w ≤ {pixels.MAX_MARK_WIDTH}; '
    f'default is {pixels.DEFAULT_MARK_WIDTH}'
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
  # everywhere we check MIN_ITER <= i <= MAX_ITER, but we use MIN_ITER as a sentinel value for AUTO!
  min=frame.MIN_ITER + 1,  # steer users away from the sentinel value
  max=frame.MAX_ITER,
  help=(
    'Maximum iterations (depth) to compute before determining escape; '
    f'{frame.MIN_ITER + 1} ≤ iter ≤ {frame.MAX_ITER}; '  # steer users away from the sentinel value
    f'default is None (automatic search for optimal iterations --- recommended)'
  ),
)
MAX_THREADS_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--threads',
  min=1,
  max=frame.MAX_CONCURRENCE,
  help=(
    'Number of threads to use for rendering; default is None, which means to use all available '
    f'CPU cores; will be limited to {frame.MAX_CONCURRENCE} threads'
  ),
)
PYTHON_OPTIMIZATION_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--opt',
  help=(
    'MIN optimization level to use for computation; '
    f'available levels: {sorted(o.value for o in frame.Optimization)}; '
    'the default is None, which means to use the max available optimization; '
    'if option is given then behavior is: '
    'given CYTHON, but CYTHON not available, will raise an Error; '
    'given HYBRID, but HYBRID not available, will raise an Error; '
    'given PYTHON, but loaded HYBRID, will use HYBRID (but not CYTHON), no errors'
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
  '-m',  # transai has '-m', but also: '-t' (tokens), '-x' (temperature), '-g' (gpu)
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
  zoom.DEFAULT_DEST_MAGNITUDE_10,
  help=(
    'Magnification magnitude to go through in the animation zoom; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'{-zoom.MAX_ZOOM_MAGNITUDE_10} ≤ mag ≤ {zoom.MAX_ZOOM_MAGNITUDE_10}; '
    'ATTENTION!! this is exponential 10**mag, so a value of 2.0 means 10**2 = 100x zoom; '
    f'default is {zoom.DEFAULT_DEST_MAGNITUDE_10}, '
    f'i.e., {10 ** float(zoom.DEFAULT_DEST_MAGNITUDE_10):.2f}x zoom'
  ),
)
ANIM_DURATION_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--duration',
  min=zoom.MIN_DURATION,
  max=zoom.MAX_DURATION,
  help=(
    f'GIF/video duration, in seconds; {zoom.MIN_DURATION} ≤ d ≤ {zoom.MAX_DURATION} or None; '
    'pick 2 out of `--duration`, `--frames` and `--fps`, and the third will be computed; '
    f'default is None'
  ),
)
ANIM_FRAMES_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--frames',
  min=zoom.MIN_FRAMES,
  max=zoom.MAX_FRAMES,
  help=(
    f'Number of frames in GIF/video; {zoom.MIN_FRAMES} ≤ fr ≤ {zoom.MAX_FRAMES} or None; '
    'pick 2 out of `--duration`, `--frames` and `--fps`, and the third will be computed; '
    f'default is None'
  ),
)
ANIM_FPS_OPTION: typer.models.OptionInfo = typer.Option(
  None,
  '--fps',
  min=zoom.MIN_FPS,
  max=zoom.MAX_FPS,
  help=(
    f'Frames per second (FPS) for the GIF/video; {zoom.MIN_FPS} ≤ fps ≤ {zoom.MAX_FPS} or None; '
    'pick 2 out of `--duration`, `--frames` and `--fps`, and the third will be computed; '
    'NOTE: if `--i-frames` is given, the effective FPS will be fps*(i+1), so keep that in mind; '
    f'default is None'
  ),
)
ANIM_TYPE_OPTION: typer.models.OptionInfo = typer.Option(
  pixels.DEFAULT_ANIMATION_TYPE,
  '--anim',
  help=(
    f'Type of animation to produce; possible values: '
    f'{", ".join(repr(t.value) for t in pixels.AnimationEncoding)}; '
    f'default is "{pixels.DEFAULT_ANIMATION_TYPE.value}"'
  ),
)
ANIM_LOOP_OPTION: typer.models.OptionInfo = typer.Option(
  zoom.DEFAULT_LOOP,
  '--loop',
  min=zoom.MIN_LOOP,
  max=zoom.MAX_LOOP,
  help=(
    f'Number of loops for the GIF (NOT MP4!); {zoom.MIN_LOOP} ≤ loop ≤ {zoom.MAX_LOOP}; '
    f'default is {zoom.DEFAULT_LOOP}; zero (0) means infinite loops'
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
ANIM_INTERPOLATION_FRAMES_OPTION: typer.models.OptionInfo = typer.Option(
  0,
  '--i-frames',
  min=0,
  max=pixels.MAX_INTERPOLATION_FRAMES,
  help=(
    f'Extra interpolated frames for every video frame; effectively, final FPS=fps*(i+1); '
    f'0 ≤ i ≤ {pixels.MAX_INTERPOLATION_FRAMES}; default is 0; '
    'so 0 is no interpolation, 1 means add 1 interpolated frame between every pair of frames, etc'
  ),
)

CONFIG_SETTABLE_KEYS: dict[str, type] = {
  # the keys you can actually read/set
  'use_db': bool,
  'db_compression': bool,
}

# Cleanup Options
CLEANUP_LEAVE_HASHES_OPTION: typer.models.OptionInfo = typer.Option(
  True,
  '--hash/--no-hash',
  help=(
    'If True, will keep the hashes in the image metadata; '
    'if False, hashes will be removed; we believe hashes cannot leak relevant information, so: '
    'default is True'
  ),
)
CLEANUP_CLEAN_PATH_OPTION: typer.models.OptionInfo = typer.Option(
  False,
  '--path/--no-path',
  help=(
    'If True, will clean the path of the image to a generic "fractal-<HASH>.png/jpg", '
    'where the HASH is randomly generated and means nothing, it is there to avoid file name clash; '
    'if False, the path will not be cleaned; we believe paths to be generally safe, so: '
    'default is False'
  ),
)
CLEANUP_OUTPUT_FORMAT_OPTION: typer.models.OptionInfo = typer.Option(
  CleanupOutputFormat.JPEG,
  '--out',
  help=(
    f'Output format for the cleaned image; possible values: '
    f'{", ".join(repr(f.value) for f in CleanupOutputFormat)}; '
    f'default is "{CleanupOutputFormat.JPEG.value}": save as JPEG because (1) if you are '
    'cleaning you want to share, and JPEG is share-friendly, and (2) some small amount of loss '
    'introduces randomness that can help with privacy'
  ),
)


# Config Options
CONFIG_KEY_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  ...,
  help=(f'Config key to set, possible values: {sorted(CONFIG_SETTABLE_KEYS)}'),
)
CONFIG_VALUE_ARGUMENT: typer.models.ArgumentInfo = typer.Argument(
  ...,
  help=('Config value to set'),
)


class ConfigType(TypedDict):
  """Config object type.

  Should be suitable for JSON and pickle serialization, so no complex types or custom classes.
  Don't use sets. Tuples are also bad, they get converted to lists, then comparison fails.
  """

  app_version: str  # package version (tranzoom.__version__) at time of last save
  last_save: int  # timestamp of last save

  # actual options come here:
  use_db: bool  # default is False, USE_DB_OPTION
  db_compression: bool  # default is False, USE_DB_COMPRESSION_OPTION
  # if you add a key here, remember to add it to CONFIG_SETTABLE_KEYS!!!


def _ConfigTypeFactory(overrides: dict[str, object] | None = None) -> ConfigType:
  """Create new ConfigType object with default values.

  Args:
    overrides (dict[str, object] | None): dict of fields to override from the defaults; if None,
        will use all defaults

  Returns:
    ConfigType: A new ConfigType object with default values.

  """
  obj: ConfigType = {
    'app_version': __version__,  # set to current package version on creation
    'last_save': timer.Now(),
    'use_db': False,  # this is where USE_DB_OPTION default lives
    'db_compression': False,  # this is where USE_DB_COMPRESSION_OPTION default lives
  }
  obj.update(overrides or {})  # type: ignore[typeddict-item]
  return obj


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class TranZoomConfig(clibase.CLIConfig):
  """TranZoom global context, storing the configuration."""

  img_output_path: pathlib.Path | None
  img_use_date: bool
  img_use_hash: bool
  img_path_prefix: str | None
  img_force_redo: bool
  use_db: bool
  db_read_only: bool
  db_compress: bool
  aes_key: aes.AESKey | None
  pal: palette.Palette
  set_pal: palette.Palette
  set_points: frame.SetHighlightAlgorithm | None
  max_threads: int | None
  python_optimization: frame.Optimization | None
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
  i_pixels: int = 0  # for `image` and `zoom` commands
  resample: pixels.Resampling = pixels.DEFAULT_RESAMPLING  # for `image` and `zoom` commands

  max_iter: int | None = None  # for `image` command, also `zoom auto`
  mark_coords: str | None = None  # for `image` command, also `zoom auto`
  mark_color: pixels.Color = pixels.DEFAULT_MARK_COLOR  # for `image` command, also `zoom auto`
  mark_width: int = pixels.DEFAULT_MARK_WIDTH  # for `image` command, also `zoom auto`

  max_steps: int = 0  # for `zoom` command
  fractal_type: frame.Fractal = frame.DEFAULT_FRACTAL  # for `zoom` command
  julia_re: str = frame.DEFAULT_JULIA_RE  # for `zoom` command
  julia_im: str = frame.DEFAULT_JULIA_IM  # for `zoom` command

  def OpenDB(self) -> frdb.FractalDatabase:
    """Make a fractal database instance from the config. This is also a context! Prefer context use.

    Returns:
      frdb.FractalDatabase: an instance of the fractal database ready to be used

    """
    compress: bool = self.db_compress or (self.aes_key is not None)  # always compress on encrypt
    return frdb.FractalDatabase(
      self.appconfig,
      use_db=self.use_db,
      read_only=self.db_read_only,
      aes_key=self.aes_key,
      compress_save=compress,  # either compress unreadable or not compress readable
      format_json=not compress,
    )

  def GetConfig(self) -> ConfigType:
    """Config values from the disk config.

    Returns:
      ConfigType: a dict of the config values, creates the default config if none on disk yet

    """
    if self.appconfig.path.exists():
      logging.info(f'Loading config from "{self.appconfig.path}"')
      return cast('ConfigType', self.appconfig.DeSerialize(silent=True))
    return _ConfigTypeFactory()

  def SetConfig(self, cnf: ConfigType) -> None:
    """Set a dict of the config values, save config to disk.

    Args:
      cnf (ConfigType): The config dict to save; will be updated with the current app_version
          and last_save timestamp before writing.

    """
    cnf.update(
      # always update these fields
      {
        'app_version': __version__,  # set to current package version on creation
        'last_save': timer.Now(),
      }
    )
    self.appconfig.Serialize(cnf, silent=True)
    logging.info(f'Saved config to "{self.appconfig.path}": {cnf}')


def MakePointFromCLIArgs(
  point_re: frame.ExactInputType,
  point_im: frame.ExactInputType,
  print_call: abc.Callable[[str], None],
) -> tuple[gmpy2.mpq, gmpy2.mpq]:
  """Make a point or die. Tries float/mpq first, then tries reading from a file metadata.

  Args:
    point_re (frame.ExactInputType): the real part of the point
    point_im (frame.ExactInputType): the imaginary part of the point
    print_call (abc.Callable[[str], None]): a callable to print messages, used for logging during
        frame creation

  Returns:
    tuple[gmpy2.mpq, gmpy2.mpq]: A valid point

  Raises:
    UsageError: if arguments can't be turned into a valid point
    Error: (not really)

  """
  try:
    # the happy path is simple... if these conversions work, we return the point and we're done
    cx: gmpy2.mpq = point_re if isinstance(point_re, gmpy2.mpq) else gmpy2.mpq(point_re)
    cy: gmpy2.mpq = point_im if isinstance(point_im, gmpy2.mpq) else gmpy2.mpq(point_im)
    return (cx, cy)
  except ValueError as err:
    if 'invalid' not in str(err).lower():
      raise UsageError(f'Error: {point_re=}, {point_im=}') from err
    # maybe the user gave us an image path instead of coordinates? let's try to read it as image
    try:
      # convert and validate path
      img_path: pathlib.Path = pathlib.Path(str(point_re)).expanduser().resolve()
      if not img_path.exists() or not img_path.is_file():
        raise Error(f'Image "{img_path}" does not exist or is not a file') from err  # noqa: TRY301
      # make sure we have the needed metadata
      info: pixels.ObjInfo = pixels.GetBasicData(img_path.read_bytes())[0]
      if image.META_CENTER_RE_KEY not in info.meta or image.META_CENTER_IM_KEY not in info.meta:
        raise Error(f'Image "{img_path}" missing tranZoom frame metadata keys') from err  # noqa: TRY301
      fract: str = str(info.meta.get(image.META_FRACTAL_KEY, '')) or 'UNKNOWN'
      print_call(f'Reading frame from "{img_path}", [red]tranZoom[/], {fract} fractal...')
      return (
        gmpy2.mpq(str(info.meta[image.META_CENTER_RE_KEY])),
        gmpy2.mpq(str(info.meta[image.META_CENTER_IM_KEY])),
      )
    except Exception as err2:  # this error we cannot forgive
      raise UsageError(f'Error/not path: {point_re=}, {point_im=}') from err2
  except Exception as err:  # this error we cannot forgive
    raise UsageError(f'Error: {point_re=}, {point_im=}') from err


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
    fractal (frame.Fractal): the fractal type to create the frame for
    center_re (str): the real part of the center, or an image path to read the frame from
    center_im (str): the imaginary part of the center (ignored if center_re is an image path)
    f_width (str): the width of the frame (ignored if center_re is an image path)
    f_height (str | None): the height of the frame (ignored if center_re is an image path)
    print_call (abc.Callable[[str], None]): a callable to print messages, used for logging during
        frame creation

  Returns:
    frame.Frame: A valid frame object

  Raises:
    UsageError: if arguments can't be turned into a valid frame
    Error: (not really)

  """
  try:
    # the happy path is one line... if these coords work, we return the frame and we're done
    return frame.Frame.FromCenter(fractal, center_re, center_im, f_width, height=f_height)
  except ValueError as err:
    if 'invalid' not in str(err).lower() and 'illegal' not in str(err).lower():
      raise UsageError(f'Error: {center_re=}, {center_im=}, {f_width=}, {f_height=}') from err
    # maybe the user gave us an image path instead of coordinates? let's try to read it as image
    try:
      # convert and validate path
      img_path: pathlib.Path = pathlib.Path(center_re).expanduser().resolve()
      if not img_path.exists() or not img_path.is_file():
        raise Error(f'Image "{img_path}" does not exist or is not a file')  # noqa: TRY301
      # make sure we have the needed metadata
      info: pixels.ObjInfo = pixels.GetBasicData(img_path.read_bytes())[0]
      if (
        image.META_CENTER_RE_KEY not in info.meta
        or image.META_CENTER_IM_KEY not in info.meta
        or image.META_WIDTH_RE_KEY not in info.meta
        or image.META_HEIGHT_IM_KEY not in info.meta
      ):
        raise Error(f'Image "{img_path}" missing tranZoom frame metadata keys')  # noqa: TRY301
      fract: str = str(info.meta.get(image.META_FRACTAL_KEY, '')) or 'UNKNOWN'
      print_call(f'Reading frame from "{img_path}", [red]tranZoom[/], {fract} fractal...')
      return frame.Frame.FromCenter(
        fractal,
        str(info.meta[image.META_CENTER_RE_KEY]),
        str(info.meta[image.META_CENTER_IM_KEY]),
        str(info.meta[image.META_WIDTH_RE_KEY]),
        height=str(info.meta[image.META_HEIGHT_IM_KEY]),
      )
    except Exception as err2:  # this error we cannot forgive
      raise UsageError(
        f'Error/not path: {center_re=}, {center_im=}, {f_width=}, {f_height=}'
      ) from err2
  except Exception as err:  # this error we cannot forgive
    raise UsageError(f'Error: {center_re=}, {center_im=}, {f_width=}, {f_height=}') from err


def MakeFrameFromConfig(
  config: TranZoomConfig,
  center_re: str,
  center_im: str,
  f_width: str,
  f_height: str | None,
) -> frame.Frame:
  """Make a Frame object from the config, considering Mandelbrot of Julia.

  Will use the config parameters:
    - config.console.print (for error messages)
    - config.fractal_type
    - config.julia_re
    - config.julia_im

  Args:
    config (TranZoomConfig): the global configuration with all the options needed for rendering
    center_re (str): the real part of the center point, as a string to be parsed to multi-precision
    center_im (str): the imaginary part of the center point, as a string to be parsed to
        multi-precision
    f_width (str): the width of the frame, as a string to be parsed to multi-precision
    f_height (str | None): the height of the frame, as a string to be parsed to multi-precision,
        or None

  Returns:
    frame.Frame: a Frame object ready for rendering

  """
  # create frame
  frm: frame.Frame = MakeFrameFromCLIArgs(
    config.fractal_type, center_re, center_im, f_width, f_height, config.console.print
  )
  # if it is a Julia, make the Julia point and add it to the frame
  julia_re: gmpy2.mpq
  julia_im: gmpy2.mpq
  julia_re, julia_im = MakePointFromCLIArgs(config.julia_re, config.julia_im, config.console.print)
  return (
    frame.Frame.FromCenter(
      frame.Fractal.JULIA,
      *frm.center,
      frm.size[0],
      height=frm.size[1],
      point_re=julia_re,
      point_im=julia_im,
    )
    if config.fractal_type == frame.Fractal.JULIA
    else frm
  )


def MakeComputationParameters(
  frm: frame.Frame, config: TranZoomConfig
) -> frame.ComputationParameters:
  """Make a ComputationParameters/width/height object from a frame and the config.

  Will use the Frame and:
    - config.img_size
    - config.img_width
    - config.img_height
    - config.set_points
    - config.max_iter

  Args:
    frm (frame.Frame): the frame to make the parameters for; must be already validated and ready
    config (TranZoomConfig): the global configuration with all the options needed for rendering

  Returns:
    frame.ComputationParameters: a ComputationParameters object

  """
  # determine width and height
  width: int
  height: int
  width, height = (
    frm.PixelDimensionsFromSize(config.img_size)
    if config.img_size
    else (config.img_width, config.img_height)
  )
  return (
    frame.ComputationParameters(
      frm=frm, width=width, height=height, set_points=config.set_points, depth=config.max_iter
    )
    if config.max_iter
    else frame.ComputationParameters(  # depth=default, not None
      frm=frm, width=width, height=height, set_points=config.set_points
    )
  )


def MakeRenderParameters(
  params: frame.ComputationParameters,
  config: TranZoomConfig,
) -> tuple[pixels.RenderParameters, image.ImageOutputConfig]:
  """Make a RenderParameters/ImageOutputConfig object from the ComputationParameters and the config.

  Will use the ComputationParameters/Frame and:
    - config.pal
    - config.set_pal
    - config.set_points
    - config.i_pixels
    - config.mark_coords
    - config.mark_color
    - config.mark_width
    - config.img_output_path
    - config.img_use_date
    - config.img_use_hash
    - config.img_path_prefix

  Args:
    params (frame.ComputationParameters): the computation parameters
    config (TranZoomConfig): the global configuration with all the options needed

  Returns:
    tuple[pixels.RenderParameters, image.ImageOutputConfig]: a tuple of the RenderParameters
        and ImageOutputConfig

  """
  # add the mark? parse coordinates early to catch errors before expensive computation
  mark_coords: tuple[tuple[gmpy2.mpq, gmpy2.mpq], tuple[int, int]] | None = (
    params.CoordsTupleToPixel(config.mark_coords, i_pixels=config.i_pixels)
    if config.mark_coords
    else None
  )
  # build render and output configuration objects
  render: pixels.RenderParameters = pixels.RenderParameters(
    escaped_pal=config.pal,
    set_pal=None if config.set_points is None else config.set_pal,
    i_pixels=config.i_pixels,
    resample=config.resample,
    mark_re=_MPQ_ZERO if mark_coords is None else mark_coords[0][0],
    mark_im=_MPQ_ZERO if mark_coords is None else mark_coords[0][1],
    mark_color=None if mark_coords is None else config.mark_color,
    mark_width=config.mark_width,
  )
  return (
    render,
    image.ImageOutputConfig(
      path=config.img_output_path,
      use_date=config.img_use_date,
      use_hash=config.img_use_hash,
      prefix=config.img_path_prefix or DEFAULT_IMAGE_PREFIX[params.frm.fractal],
    ),
  )


def ProduceFractalImage(
  db: frdb.FractalDatabase,
  frm: frame.Frame,
  config: TranZoomConfig,
  *,
  tm: int | None = None,
  add_serial: int | None = None,
  save_image: bool = True,
) -> tuple[image.Image | None, pixels.Pixels, bytes, str, pixels.RenderParameters]:
  """Produce fractal image from a frame and a config, and save it to disk, print it to iTerm2, etc.

  Args:
    db (frdb.FractalDatabase): the fractal database instance to use
    frm (frame.Frame): the frame to produce the image from; must be already validated and ready
        for rendering
    config (TranZoomConfig): the global configuration with all the options needed for rendering
        and saving the image
    tm (int | None): Optional timestamp to use for the date in the file name. If None, the
        current time is used.
    add_serial (int | None): Optional serial number to include in the file name for uniqueness;
        if None, no serial number is included; if provided, it is formatted as a zero-padded
        5-digit number between the date and hash.
    save_image (bool): If True, will save the final image to disk; if False, the image will
        not be saved; default is True.

  Returns:
    tuple[image.Image | None, pixels.Pixels, bytes, str, pixels.RenderParameters]: A tuple of
        (image.Image object, pixels.Pixels object, raw PNG bytes, data hash, RenderParameters)

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
  # build parameters
  params: frame.ComputationParameters = MakeComputationParameters(frm, config)
  render: pixels.RenderParameters
  out: image.ImageOutputConfig
  render, out = MakeRenderParameters(params, config)
  # warn if size estimates are large, before starting expensive computation
  png_sz: int
  jpg_sz: int
  png_sz, jpg_sz = params.png_sz_bytes()
  if max(png_sz, jpg_sz) > frame.THRESHOLD_LARGE_PNG_BYTES:
    config.console.print(
      f'[red]Warning: large on-disk size estimate: '
      f'PNG ~{human.HumanizedBytes(png_sz)}, JPG ~{human.HumanizedBytes(jpg_sz)}[/]\n'
    )
  frame_mem: int = params.comp_memory_sz_bytes
  if frame_mem > frame.THRESHOLD_LARGE_FRAME_MEMORY_BYTES:
    config.console.print(
      f'[red]Warning: large render memory estimate: ~{human.HumanizedBytes(frame_mem)}[/]\n'
    )
  # compute the image via the unified core primitive
  img: image.Image | None
  pix: pixels.Pixels
  data_hash: str
  full_path: pathlib.Path
  _, img, pix, data_hash, full_path = db.CoreComputeImage(
    params,
    render,
    out,
    add_serial=add_serial,
    tm=tm,
    max_threads=config.max_threads,
    iterm=config.iterm,
    print_comm=config.console.print,
    optimization=config.python_optimization,
    force=config.img_force_redo,
  )
  # save the image to disk if requested
  raw_png: bytes
  file_hash: str
  raw_png, file_hash, _ = pix.PNG()  # <=< <<<<< <=< THIS is where the PNG is actually generated!
  if save_image:
    full_path.write_bytes(raw_png)
    config.console.print(
      f'Saved to {str(full_path)!r} ({file_hash[:16]!r}), {human.HumanizedBytes(len(raw_png))}'
    )
  return (img, pix, raw_png, data_hash, render)


def ProduceFractalAnimation(  # noqa: C901, PLR0912, PLR0914, PLR0915
  config: TranZoomConfig,
  out: image.ImageOutputConfig,
  zoom_params: zoom.ZoomParameters,
  save_frames: bool,
) -> tuple[pathlib.Path, int]:
  """Make the animation file, returning its path and size.

  Args:
    config (TranZoomConfig): the shared config with all options.
    out (image.ImageOutputConfig): the image output config with all options for rendering.
    zoom_params (zoom.ZoomParameters): the parameters of the zoom to render.
    save_frames (bool): whether to save the individual frames as images in the output directory.

  Returns:
    tuple[pathlib.Path, int]: A tuple of the path to the saved animation file and its size in bytes.

  Raises:
    Error: on error, usually a bug
    UsageError: on error, usually invalid user input

  """
  # TODO: split this monster method
  # generate frames, markers, depth frames; do first because it can fail and we want to fail early
  all_frames: list[frame.Frame]
  all_markers: list[tuple[int, frame.Frame]]
  all_depth: list[tuple[int, frame.Frame]]
  all_frames, all_markers, all_depth = zoom_params.Frames()  # could go boom!
  logging.debug(f'Marker frames: {[idx for idx, _ in all_markers]}')
  # we should be good to go, all options check out; log and warn if needed
  final_width: int
  final_height: int
  final_width, final_height = zoom_params.img.Size(i_pixels=zoom_params.render.i_pixels)
  real_sz_str: str = (
    f' (on disk: {final_width} \u00d7 {final_height})' if zoom_params.render.i_pixels else ''
  )
  config.console.print(
    f'\n{zoom_params.img.width} \u00d7 {zoom_params.img.height}{real_sz_str} '
    f'{zoom_params.render.anim.value.upper()!r}: '
    f'{zoom_params.render.escaped_pal.value!r} {zoom_params.img.frm.fractal.value.capitalize()!r} '
    f'[magenta]10^{float(zoom_params.mag):.4f} magnitude ZOOM[/], '
    f'{human.HumanizedSeconds(float(zoom_params.n_seconds))} long, '
    f'at {float(zoom_params.fps):.2f}*{zoom_params.render.i_frames + 1} FPS, '
    f'with {zoom_params.n_frames}|{zoom_params.all_frames} frames ({len(all_markers)} markers, '
    f'{100.0 * len(all_markers) / zoom_params.n_frames:.2f}%, and {len(all_depth)} depth frames, '
    f'{100.0 * len(all_depth) / zoom_params.n_frames:.2f}%), '
    f'{100.0 * (float(zoom_params.scalar_magnification_per_step) - 1.0):.4f}%/step, '
    f'{fractal.OptimizationToUse(config.python_optimization)[1]}...'
  )
  config.console.print(f'[yellow]ZOOM:[/] {zoom_params} ... {all_frames[-1]}\n')
  # sanity checks and warnings before we start the expensive rendering loop
  frdb.WarnUserAnimationParams(zoom_params, print_comm=config.console.print)
  # create path callback missing only the hash
  timestamp: int = timer.Now()
  full_path: abc.Callable[[str], pathlib.Path] = lambda h: pixels.MakeImagePath(
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix or DEFAULT_IMAGE_PREFIX[zoom_params.img.frm.fractal],
    h,
    tm=timestamp,
    suffix=zoom_params.render.anim.value.lower(),
  )
  # DB
  did_comp: bool
  depth_tmr: timer.Timer | None = None
  all_img_obj: dict[int, image.Image] = {}  # to keep images if not streaming
  all_params: dict[int, frame.ComputationParameters] = {}
  with config.OpenDB() as db:
    streaming: bool = db.is_read_write
    video_hash: str
    cp: frdb.ComputationData | None
    video_path: pathlib.Path
    # warn on large memory usage
    zoom_mem: int = zoom_params.comp_memory_sz_bytes
    if not streaming and zoom_mem > frame.THRESHOLD_LARGE_ZOOM_MEMORY_BYTES:
      config.console.print(
        f'[red]Warning: large zoom render memory estimate: ~{human.HumanizedBytes(zoom_mem)}[/]\n'
      )
    # see if we have a cache of this zoom
    zoom_data: frdb.ZoomData | None = db.FindZoom(zoom_params)
    if zoom_data:
      video_hash = zoom_data['data_hash'] or ''
      old_path: pathlib.Path | None = (
        pathlib.Path(zoom_data['rendered_path']) if zoom_data['rendered_path'] else None
      )
      if video_hash and old_path and old_path.exists() and old_path.is_file():
        # we do have the video!
        config.console.print(
          f'[red]DB render[/], {video_hash!r}@{timer.TimeStr(zoom_data["tm"])} -> "{old_path}"\n'
        )
        video_path = full_path(video_hash)
        if video_path != old_path:
          video_data: bytes = old_path.read_bytes()
          video_path.write_bytes(video_data)
        # log and shortcircuit
        config.console.print(
          f'Success: {zoom_params.render.anim.value.upper()} {video_hash!r} from disk'
        )
        return (video_path, video_path.stat().st_size)
    # produce the depth computations for all the depth frames: this will save us a lot of trouble
    max_iter: int
    idx: int
    jj: int
    stats: image.FractalStats
    depth_computations: dict[int, tuple[frame.Frame, int, int, image.FractalStats]] = {}
    params: frame.ComputationParameters = zoom_params.img  # starting value, to replace frm & depth
    if zoom_data is None or not streaming:
      n_threads: int = frame.ConcurrenceToUse(config.max_threads)
      config.console.print(f'[yellow]Making {len(all_depth)} depth computations...[/]')
      with timer.Timer(emit_log=False) as depth_tmr:
        with warnings.catch_warnings():
          warnings.simplefilter('ignore', category=TqdmExperimentalWarning)
          depth_bar: tqdm.rich.tqdm[tuple[int, frame.Frame]] = tqdm.rich.tqdm(
            all_depth,
            desc='Depth',
            unit='fr',
            dynamic_ncols=True,
            smoothing=0.1,
            colour='yellow',
          )
        for idx, frm in depth_bar:
          params = dataclasses.replace(params, frm=frm, depth=frame.MIN_ITER)
          max_iter, stats = fractal.FractalAdaptiveIterations(
            params.frm,
            set_points=params.set_points,
            progress_bar=False,
            n_processes=n_threads,
            optimization=config.python_optimization,
            print_comm=config.console.print,
          )
          depth_computations[idx] = (frm, max_iter, max_iter, stats)
        # we have them, now we can smooth them and replace them into the dict of proposed depths
        jagged_depths: list[int] = [depth_computations[idx][1] for idx, _ in all_depth]
        logging.debug(f'Raw depths for depth frames: {jagged_depths}')
        smoothed_depths: list[int] = frame.SmoothDepths(jagged_depths)
        del jagged_depths
        logging.debug(f'Smoothed depths for depth frames: {smoothed_depths}')
        for jj, (idx, _) in enumerate(all_depth):
          frm, max_iter, _, stats = depth_computations[idx]
          depth_computations[idx] = (frm, max_iter, smoothed_depths[jj], stats)
        del smoothed_depths
        # this is our first milestone; add to DB; commit
        if streaming:
          db.AddZoomToDB(
            zoom_params,
            timestamp,
            None,
            None,
            all_frames,
            all_markers,
            [(i, *depth_computations[i]) for i in sorted(depth_computations)],
          )
          db.Save()
      # depth computations done, log
      config.console.print(f'{len(all_depth)} depth computations done in {depth_tmr}\n')
    else:
      # we already have the zoom data in the DB, so load it
      for dfd in zoom_data['depths']:
        df: frame.Frame | None = db.FindFrame(dfd['frm'])[0]
        if not df:
          raise Error(f'Depth frame {dfd["idx"]} references frame {dfd["frm"]} not in DB')
        depth_computations[dfd['idx']] = (
          df,
          dfd['orig_depth'],
          dfd['smooth_depth'],
          image.FractalStats.FromJson(dfd['stats']),
        )
      # depth computations loaded, sanity check and log
      if set(depth_computations) != (depth_set := {idx for idx, _ in all_depth}):
        raise Error(
          'Depth computations in DB do not match the expected depth frames for this zoom: '
          f'{set(depth_computations.keys())} vs {depth_set}; bug! report!'
        )
      config.console.print(f'{len(all_depth)} depth computations loaded from disk\n')
    # from DB or computed, now we have the depths
    sorted_depth_keys: list[int] = sorted(depth_computations)

    def _DepthAndStatsForFrame(i: int) -> tuple[int, image.FractalStats]:
      """Depth/stats for a Frame index, interpolating from depth_computations.

      Args:
        i (int): The index of the frame in the zoom sequence.

      Returns:
        tuple[int, image.FractalStats]: A tuple containing the interpolated max iteration depth and
            fractal statistics for the frame at index i.

      """
      if i in depth_computations:
        return (depth_computations[i][2], depth_computations[i][3])
      # interpolate: find the two bracketing keys in depth_computations
      lo_idx: int = sorted_depth_keys[0]
      hi_idx: int = sorted_depth_keys[-1]
      for k in sorted_depth_keys:
        if k <= i:
          lo_idx = k
        else:
          hi_idx = k
          break
      # linearly interpolate max_iter between the two bracketing depths
      lo_depth: int = depth_computations[lo_idx][2]
      hi_depth: int = depth_computations[hi_idx][2]
      t: float = (i - lo_idx) / (hi_idx - lo_idx) if hi_idx != lo_idx else 0.0
      interpolated_depth: int = round(lo_depth + t * (hi_depth - lo_depth))
      # interpolate each FractalStats field independently; if either endpoint is None, result None
      lo_stats: image.FractalStats = depth_computations[lo_idx][3]
      hi_stats: image.FractalStats = depth_computations[hi_idx][3]
      t_mpfr: gmpy2.mpfr = gmpy2.mpfr(t)
      interpolated_stats: image.FractalStats = image.FractalStats(
        n_px=round(lo_stats.n_px + t * (hi_stats.n_px - lo_stats.n_px)),
        n_interior=round(lo_stats.n_interior + t * (hi_stats.n_interior - lo_stats.n_interior)),
        max_lo=(lo_stats.max_lo + t_mpfr * (hi_stats.max_lo - lo_stats.max_lo))
        if lo_stats.max_lo is not None and hi_stats.max_lo is not None
        else None,
        max_hi=(lo_stats.max_hi + t_mpfr * (hi_stats.max_hi - lo_stats.max_hi))
        if lo_stats.max_hi is not None and hi_stats.max_hi is not None
        else None,
        min_lo=(lo_stats.min_lo + t_mpfr * (hi_stats.min_lo - lo_stats.min_lo))
        if lo_stats.min_lo is not None and hi_stats.min_lo is not None
        else None,
        min_hi=(lo_stats.min_hi + t_mpfr * (hi_stats.min_hi - lo_stats.min_hi))
        if lo_stats.min_hi is not None and hi_stats.min_hi is not None
        else None,
        ang_lo=(lo_stats.ang_lo + t_mpfr * (hi_stats.ang_lo - lo_stats.ang_lo))
        if lo_stats.ang_lo is not None and hi_stats.ang_lo is not None
        else None,
        ang_hi=(lo_stats.ang_hi + t_mpfr * (hi_stats.ang_hi - lo_stats.ang_hi))
        if lo_stats.ang_hi is not None and hi_stats.ang_hi is not None
        else None,
        imag_lo=(lo_stats.imag_lo + t_mpfr * (hi_stats.imag_lo - lo_stats.imag_lo))
        if lo_stats.imag_lo is not None and hi_stats.imag_lo is not None
        else None,
        imag_hi=(lo_stats.imag_hi + t_mpfr * (hi_stats.imag_hi - lo_stats.imag_hi))
        if lo_stats.imag_hi is not None and hi_stats.imag_hi is not None
        else None,
      )
      return (interpolated_depth, interpolated_stats)

    # produce the frames
    n_frames_actually_computed: int = 0
    total_depth: int = sum(
      zoom.FrameEstimatedIters(*_DepthAndStatsForFrame(jj)) for jj in range(zoom_params.n_frames)
    )
    cmp_bar: tqdm.tqdm[NoReturn] = tqdm.tqdm(
      # BEWARE: the tqdm-rich.tqdm bar is visually nicer BUT it cannot live with another bar because
      # they will both fight for the same console space (the current line), so bars that are meant
      # to have sub-bars (like here) need to be "regular" tqdm.tqdm instead
      total=total_depth,
      desc='Iter',
      unit='it',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='magenta',
    )
    with timer.Timer(emit_log=False) as frames_tmr:
      d_all_markers: dict[int, frame.Frame] = dict(all_markers)  # for quick lookup
      for idx, frm in enumerate(all_frames):
        max_iter, stats = _DepthAndStatsForFrame(idx)
        params = dataclasses.replace(params, frm=frm, depth=max_iter)
        # log
        log_color: str = (
          '[magenta]Marker '
          if idx in d_all_markers
          else ('[cyan]Depth ' if idx in depth_computations else '[yellow]')
        )
        config.console.print(
          f'{log_color}Frame {idx + 1} / {zoom_params.n_frames}[/] - depth {max_iter}'
        )
        # if we are streaming it is super worth it to check before loading!
        if streaming:
          params, _, cp = db.FindComputation(params)
          if cp and cp['raw_data_path']:
            all_params[idx] = params
            config.console.print('Computation in DB cache\n')
            cmp_bar.update(zoom.FrameEstimatedIters(max_iter, stats))  # update progress bar
            continue
        # we really need to compute: feed frame to the producer
        img: image.Image
        params, img, did_comp = db.DoComputation(
          params,  # send frm
          max_threads=config.max_threads,
          optimization=config.python_optimization,
          stats=stats,
          print_comm=config.console.print,
          force=config.img_force_redo,
        )
        n_frames_actually_computed += bool(did_comp)  # count only actually computed frames
        # save
        all_params[idx] = params
        if not streaming:
          all_img_obj[idx] = img
        # DB checkpoint
        if (
          streaming
          and n_frames_actually_computed
          and not n_frames_actually_computed % _N_FRAMES_PER_DB_SAVE
        ):
          config.console.print('\n[bright_blue](DB checkpoint)[/]')
          db.Save()  # commit to disk every N computations
        # write a space and update the bar, and we're done with this frame
        config.console.print()
        cmp_bar.update(zoom.FrameEstimatedIters(max_iter, stats))  # update progress bar
      del d_all_markers
    # we have all frames; if we're using DB and have done computations, make sure it is all saved
    cmp_bar.close()
    if streaming and n_frames_actually_computed:
      db.Save()
      config.console.print('\n[bright_blue](DB save)[/]\n')
    # we should have all images either in memory or in DB; so now we we rely on _SmartImage()

    def _SmartImage(i: int) -> image.Image:
      """Image object for frame i, either from memory (not streaming) or DB (streaming).

      Args:
        i (int): The index of the frame in the zoom sequence.

      Returns:
        image.Image: The Image object for the frame at index i.

      Raises:
        Error: If the image data for frame i is not found in the DB when streaming

      """
      if not streaming:
        return all_img_obj[i]  # noqa: F821
      img_obj: image.Image | None = db.LoadImageData(f'img_{all_params[i].sha}.Data')
      if not img_obj:
        raise Error(f'Image data for frame {i} not found in DB; bug; report!')
      return img_obj

    # build ZoomColorNorm from the marker images: anchors color normalization so the same
    # escape-iteration value maps to a consistent palette position across the whole animation,
    # eliminating wild per-frame palette shifts (one color anchor per MAGNITUDE_PER_FRAME_MARKER
    # zoom decades, i.e., one marker every 10x zoom by default)
    zoom_norm: image.Image.ZoomColorNorm = image.Image.ZoomColorNorm.FromSortedMarkers(
      (i, _SmartImage(i)) for i, _ in all_markers
    )  # use the original all_markers b/c it is sorted
    config.console.print(
      f'[yellow]ZOOM:[/] [green]Color norm[/]: built from {len(all_markers)} marker frames\n'
    )
    # render the final animation, first to a temporary path because we do not have the hash yet...
    with tempfile.TemporaryDirectory() as tmpdir, timer.Timer(emit_log=False) as render_tmr:
      # make the rendering progress bar
      config.console.print(f'[yellow]Render:[/] {zoom_params.render}')
      with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=TqdmExperimentalWarning)
        p_bar: tqdm.rich.tqdm[NoReturn] = tqdm.rich.tqdm(
          total=zoom_params.n_frames,
          desc='Render',
          unit='fr',
          dynamic_ncols=True,
          smoothing=0.1,
          colour='yellow',
          disable=False,  # for debugging rendering, set to True to disable the progress bar
        )
      # start try..finally for the progress bar
      try:

        def _TwoFrameRenderStream() -> abc.Iterator[
          tuple[zoom.RenderedZoomFrame, zoom.RenderedZoomFrame | None]
        ]:
          """Render base frames with a rolling [curr, next] window.

          At most two rendered base-frame byte payloads are retained by this stream.

          The stream shape is:
            (frame0, frame1)
            (frame1, frame2)
            ...
            (frameN-2, frameN-1)
            (frameN-1, None)

          Yields:
            tuple[zoom.RenderedZoomFrame, zoom.RenderedZoomFrame | None]: A tuple of
                the current frame and the next frame (or None if at the end)

          """
          curr_frame: zoom.RenderedZoomFrame = _StreamingRenderFrame(0)
          next_frame: zoom.RenderedZoomFrame | None = _StreamingRenderFrame(1)  # (MIN_FRAMES is 3)
          for i in range(zoom_params.n_frames):
            yield (curr_frame, next_frame)
            if next_frame is None:
              break
            curr_frame = next_frame
            next_frame = _StreamingRenderFrame(i + 2) if i + 2 < zoom_params.n_frames else None

        def _StreamingRenderFrame(i: int) -> zoom.RenderedZoomFrame:
          """Render a single frame, returning the image data. Only one in memory at a time.

          Args:
            i (int): The index of the frame in the zoom sequence.

          Returns:
            zoom.RenderedZoomFrame: The rendered image data for the frame at index i.

          """
          # render the frame, get the image data and hash
          img_data: pixels.Pixels
          data_hash: str
          img_path: pathlib.Path
          img_data, data_hash, img_path, _ = db.DoRender(
            _SmartImage(i),  # get the Image object for this frame
            zoom_params.render,
            out,
            add_serial=i + 1,
            tm=timestamp,
            iterm=False,  # disable, we want silence
            print_comm=config.console.print,
            force=config.img_force_redo,
            zoom_norm=zoom_norm.ForFrame(i)[-1],
            silent=True,  # we will have a progress bar
          )
          # save per-frame-normalized image to disk if requested (for individual frame inspection)
          if save_frames:
            # saving frames is costly (but not too much), we do it here b/c the user asked for it
            raw_png: bytes
            file_hash: str
            raw_png, file_hash, _ = img_data.PNG()  # WASTEFUL!: this will be done again later
            img_path.write_bytes(raw_png)
            config.console.print(
              f'Saved frame {i + 1} to {str(img_path)!r} '
              f'({file_hash[:16]!r}), {human.HumanizedBytes(len(raw_png))}'
            )
          # update progress bar, return data
          if p_bar:
            p_bar.update(1)
          return zoom.RenderedZoomFrame(
            idx=i, data=img_data, data_hash=data_hash, img_path=img_path
          )

        # render the video to a temporary path, using the two-frame stream to interpolate frames
        tmp_path: pathlib.Path = (
          pathlib.Path(tmpdir) / f'temp_video.{zoom_params.render.anim.value.lower()}'
        )
        all_hash: list[str] = []
        frame_bytes: abc.Iterable[bytes] = zoom.InterpolatedFrameStream(  # generator! memory!
          # we must keep all of this as generators to save rendering memory
          _TwoFrameRenderStream(),  # this will yield (curr, next) tuples of rendered frames
          all_hash,  # this will be filled with the hashes of the rendered frames
          i_frames=zoom_params.render.i_frames,
          zoom_per_step=float(zoom_params.scalar_magnification_per_step),
          use_quadratic=zoom.DEFAULT_USE_QUADRATIC,
        )
        if zoom_params.render.anim == pixels.AnimationEncoding.GIF:
          zoom.WriteAnimatedGIF(
            frame_bytes,  # generator! memory!
            tmp_path,
            zoom_params.img.width,
            zoom_params.img.height,
            zoom_params.all_frames,
            float(zoom_params.n_seconds),
            loop=zoom_params.loop,
          )
        elif zoom_params.render.anim == pixels.AnimationEncoding.MP4:
          zoom.WriteVideoMP4(
            frame_bytes,  # generator! memory!
            tmp_path,
            zoom_params.img.width,
            zoom_params.img.height,
            zoom_params.all_frames,
            float(zoom_params.n_seconds),
          )
        else:
          raise UsageError(f'Unsupported animation type: {zoom_params.render.anim}')
      finally:
        # we are done, close the progress bar, free memory
        p_bar.close()
      # we can finally compute the hash, which is stable if the image data and order does not change
      video_hash = hashes.Hash256(('|'.join(all_hash)).encode('ascii')).hex()
      # create metadata
      meta: dict[str, str] = image.MakeImageMeta(  # use destination frame (final) as reference
        _SmartImage(zoom_params.n_frames - 1), zoom_params.render, video_hash
      )
      del all_img_obj  # this should help free all generated images from memory
      # add video-specific metadata
      meta[image.META_IMAGE_ANIMATION_KEY] = zoom_params.render.anim.value.lower()
      meta.update(
        # the extra animation keys
        {
          image.META_ZOOM_TYPE_KEY: zoom_params.render.anim.value.lower(),
          image.META_ZOOM_INITIAL_WIDTH_RE_KEY: str(all_frames[0].size[0]),
          image.META_ZOOM_INITIAL_HEIGHT_IM_KEY: str(all_frames[0].size[1]),
          image.META_ZOOM_MAGNITUDE_KEY: str(zoom_params.mag),
          image.META_ZOOM_FRAMES_KEY: str(zoom_params.n_frames),
          image.META_ZOOM_SECONDS_KEY: str(zoom_params.n_seconds),
          image.META_ZOOM_LOOP_KEY: str(zoom_params.loop),
          image.META_ZOOM_STEPS_KEY: str(zoom_params.n_steps),
          image.META_ZOOM_FPS_KEY: str(zoom_params.fps),
          image.META_ZOOM_I_FPS_KEY: str(zoom_params.ifps),
          image.META_ZOOM_I_FRAMES_KEY: str(zoom_params.render.i_frames),
          image.META_ZOOM_ALL_FRAMES_KEY: str(zoom_params.all_frames),
          image.META_ZOOM_MAGNITUDE_PER_STEP_KEY: str(zoom_params.mag_per_step),
          image.META_ZOOM_MAGNIFICATION_PER_STEP_KEY: str(
            zoom_params.scalar_magnification_per_step
          ),
          image.META_ZOOM_MARKER_INDEX_LIST_KEY: str([idx for idx, _ in all_markers]),
          image.META_ZOOM_DEPTH_FRAMES_LIST_KEY: str(
            # we include pre- and post-smoothing depths for all depth frames
            [
              (idx, depth_computations[idx][1], depth_computations[idx][2])
              for idx in sorted_depth_keys
            ]
          ),
          image.META_ZOOM_HASH_KEY: zoom_params.sha,
        }
      )
      # move the file!
      video_path = full_path(video_hash)
      if zoom_params.render.anim == pixels.AnimationEncoding.GIF:
        zoom.ReWriteAnimatedGIFMeta(tmp_path, video_path, meta)
      elif zoom_params.render.anim == pixels.AnimationEncoding.MP4:
        zoom.ReWriteVideoMP4Meta(tmp_path, video_path, meta)
    # closed temporary directory, video is saved in final destination with final metadata
    config.console.print('[yellow]Render:[/] [green]DONE[/]\n')
    # we just freed the temporary directory; add to DB
    db.AddZoomToDB(
      zoom_params,
      timestamp,
      video_hash,
      str(video_path),
      all_frames,
      all_markers,
      [(idx, *depth_computations[idx]) for idx in sorted_depth_keys],
    )
  # done, close DB, final log and iTerm2
  config.console.print(
    f'Success: {zoom_params.render.anim.value.upper()} {video_hash!r} in '
    f'{depth_tmr or "-"} (depth) + {frames_tmr} (frames) + {render_tmr} (render)'
  )
  return (video_path, video_path.stat().st_size)
