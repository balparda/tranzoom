# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Base."""

from __future__ import annotations

import dataclasses
import enum
import logging
import pathlib
from collections import abc
from typing import TypedDict, cast

import click
import gmpy2
import typer
from transcrypto.cli import clibase
from transcrypto.core import aes
from transcrypto.utils import base as tbase
from transcrypto.utils import human, timer

from tranzoom import __version__
from tranzoom.core import ai, frame, frdb, image, palette


class Error(ai.Error, click.ClickException):
  """Base CLI/click exception."""


class UsageError(Error, click.UsageError):
  """Base CLI/click usage exception."""


# CLI enumerations


class CleanupOutputFormat(enum.Enum):
  """Output format for the cleanup command."""

  JPEG = 'jpeg'
  JPG = 'jpg'
  PNG = 'png'  # TODO: support formats: gif/mp4 videos


# gmpy2.mpq constants
_MPQ_ZERO: gmpy2.mpq = gmpy2.mpq('0')


# global CLI data, and some test stuff

# if `tests/data/images/demo-mandel-seahorse-tail.png` internal data changes this will change!
# this indicates that the mathematical computation or the setting of colors has changed;
# this should NOT change over metadata changes, as it is computed from raw pixel data
SEAHORSE_TAIL_HASH: str = 'e4fad99036a41cc87ad0997ee49677f54259d37178899086e62f16d5879de1d9'
SEAHORSE_ANIMATED_HASH: str = 'cfcd4250757a16c4d4c9d4594693ad0f02588796d0ddb328bbea6e889478e406'
SUZANA_WAVE_HASH: str = '8f06e7bcd0ea14dff1b6fc3c829cdc295367695fea882e2cf9e25bb1a6dfb5fc'
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
  image.DEFAULT_DEST_MAGNITUDE_10,
  help=(
    'Magnification magnitude to go through in the animation zoom; '
    'this can be a float (ex: "0.34") or a fraction of ints (rational number, ex: "123/451") and '
    'the number will be fed directly to multi-precision arithmetic so no precision is lost; '
    f'{-image.MAX_ZOOM_MAGNITUDE_10} ≤ mag ≤ {image.MAX_ZOOM_MAGNITUDE_10}; '
    'ATTENTION!! this is exponential 10**mag, so a value of 2.0 means 10**2 = 100x zoom; '
    f'default is {image.DEFAULT_DEST_MAGNITUDE_10}, '
    f'i.e., {10 ** float(image.DEFAULT_DEST_MAGNITUDE_10):.2f}x zoom'
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
    """Get a dict of the config values from the disk config.

    Returns:
      ConfigType: a dict of the config values, creates the default config if none on disk yet

    """
    if self.appconfig.path.exists():
      logging.info(f'Loading config from "{self.appconfig.path}"')
      return cast('ConfigType', self.appconfig.DeSerialize())
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
    self.appconfig.Serialize(cnf)
    logging.info(f'Saved config to "{self.appconfig.path}": {cnf}')


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
      info: tbase.JSONDict = image.GetBasicDataFromImage(img_path.read_bytes())[-1]
      if (
        image.META_CENTER_RE_KEY not in info
        or image.META_CENTER_IM_KEY not in info
        or image.META_WIDTH_RE_KEY not in info
        or image.META_HEIGHT_IM_KEY not in info
      ):
        raise Error(f'Image "{img_path}" missing tranZoom frame metadata keys')  # noqa: TRY301
      fract: str = str(info.get(image.META_FRACTAL_KEY, '')) or 'UNKNOWN'
      print_call(f'Reading frame from "{img_path}", [red]tranZoom[/], {fract} fractal...')
      return frame.Frame.FromCenter(
        fractal,
        str(info[image.META_CENTER_RE_KEY]),
        str(info[image.META_CENTER_IM_KEY]),
        str(info[image.META_WIDTH_RE_KEY]),
        height=str(info[image.META_HEIGHT_IM_KEY]),
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
) -> tuple[image.RenderParameters, image.ImageOutputConfig]:
  """Make a RenderParameters/ImageOutputConfig object from the ComputationParameters and the config.

  Will use the ComputationParameters/Frame and:
    - config.pal
    - config.set_pal
    - config.set_points
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
    tuple[image.RenderParameters, image.ImageOutputConfig]: a tuple of the RenderParameters
        and ImageOutputConfig

  """
  # add the mark? parse coordinates early to catch errors before expensive computation
  mark_coords: tuple[tuple[gmpy2.mpq, gmpy2.mpq], tuple[int, int]] | None = (
    params.CoordsTupleToPixel(config.mark_coords) if config.mark_coords else None
  )
  # build render and output configuration objects
  render: image.RenderParameters = image.RenderParameters(
    escaped_pal=config.pal,
    set_pal=None if config.set_points is None else config.set_pal,
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
) -> tuple[image.Image | None, bytes, str, image.RenderParameters]:
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
    tuple[image.Image, bytes, str, image.RenderParameters]: A tuple of
        (image.Image object, raw PNG bytes, internal hash of the raw PNG, RenderParameters)

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
  render: image.RenderParameters
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
  raw_png: bytes
  raw_hash: str
  full_path: pathlib.Path
  _, img, raw_png, raw_hash, full_path = db.CoreComputeImage(
    params,
    render,
    out,
    add_serial=add_serial,
    tm=tm,
    max_threads=config.max_threads,
    iterm=config.iterm,
    print_comm=config.console.print,
    force=config.img_force_redo,
  )
  # save the image to disk if requested
  if save_image:
    full_path.write_bytes(raw_png)
    config.console.print(f'Saved to {str(full_path)!r}, {human.HumanizedBytes(len(raw_png))}')
  return (img, raw_png, raw_hash, render)


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
      info: tbase.JSONDict = image.GetBasicDataFromImage(img_path.read_bytes())[-1]
      if image.META_CENTER_RE_KEY not in info or image.META_CENTER_IM_KEY not in info:
        raise Error(f'Image "{img_path}" missing tranZoom frame metadata keys') from err  # noqa: TRY301
      fract: str = str(info.get(image.META_FRACTAL_KEY, '')) or 'UNKNOWN'
      print_call(f'Reading frame from "{img_path}", [red]tranZoom[/], {fract} fractal...')
      return (
        gmpy2.mpq(str(info[image.META_CENTER_RE_KEY])),
        gmpy2.mpq(str(info[image.META_CENTER_IM_KEY])),
      )
    except Exception as err2:  # this error we cannot forgive
      raise UsageError(f'Error/not path: {point_re=}, {point_im=}') from err2
  except Exception as err:  # this error we cannot forgive
    raise UsageError(f'Error: {point_re=}, {point_im=}') from err
