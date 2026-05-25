# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Image operations for Mandelbrot rendering.

For info on the PNG format and metadata handling, see:
https://pillow.readthedocs.io/en/stable/PIL.html#PIL.PngImagePlugin.PngInfo
"""

from __future__ import annotations

import array
import base64
import dataclasses
import enum
import io
import json
import logging
import math
import pathlib
import struct
import sys
import time
from collections import abc
from typing import cast

import gmpy2
import imageio
import numpy as np
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont, PngImagePlugin
from transcrypto.core import hashes
from transcrypto.utils import base as tbase
from transcrypto.utils import timer

from tranzoom.core import frame, palette

# metadata keys for PNG tEXt chunks; used to store the frame parameters and other info in the PNG;
# don't add "version", or "date", or other metadata that can change without changing the
# actual image/mathematical data;
# keys use a "tranzoom:" namespace to avoid collisions with other metadata
# all are converted to str for storage in PNG metadata, but the original types are indicated below
META_IMAGE_ANIMATION_KEY = 'tranzoom:image:animation'  # AnimationType or "none" if static image
META_IMAGE_WIDTH_KEY = 'tranzoom:image:width'  # int, in pixels
META_IMAGE_HEIGHT_KEY = 'tranzoom:image:height'  # int, in pixels
META_IMAGE_HASH_KEY = 'tranzoom:image:hash'  # str, like "abcdef1234567890", a SHA256
META_ITER_DEPTH_MIN_KEY = 'tranzoom:image:iter_depth:min'  # int
META_ITER_DEPTH_MAX_KEY = 'tranzoom:image:iter_depth:max'  # int
META_ITER_SEARCH_DEPTH_KEY = 'tranzoom:image:iter_depth:search'  # int
META_SET_POINT_MIN_KEY = 'tranzoom:image:set_point:min'  # int
META_SET_POINT_MAX_KEY = 'tranzoom:image:set_point:max'  # int
META_IMAGE_COLOR_SET_KEY = 'tranzoom:image:color_set'  # frame.SetHighlightAlgorithm or "none"
META_RENDER_PALETTE_KEY = 'tranzoom:render:palette'  # str, like "sunset", one of palette.Palette
META_RENDER_SET_PALETTE_KEY = 'tranzoom:render:set_palette'  # str, interior Set palette name
META_RENDER_OVERLAY_KEY = 'tranzoom:render:overlay'  # image.OverlayType or "none"
META_RENDER_MARK_RE_KEY = 'tranzoom:render:mark_re'  # gmpy2.mpq
META_RENDER_MARK_IM_KEY = 'tranzoom:render:mark_im'  # gmpy2.mpq
META_RENDER_MARK_COLOR_KEY = 'tranzoom:render:mark_color'  # Color.name.lower() or "none" (=no mark)
META_RENDER_MARK_WIDTH_KEY = 'tranzoom:render:mark_width'  # int
META_PIXEL_EXTERIOR_COUNT_KEY = 'tranzoom:image:exterior:pixel_count'  # int; count escaped
META_PIXEL_INTERIOR_COUNT_KEY = 'tranzoom:image:interior:pixel_count'  # int; count set
META_IMAGE_STATS_MAX_LO_KEY = 'tranzoom:image:stats:max_lo'  # gmpy2.mpfr
META_IMAGE_STATS_MAX_HI_KEY = 'tranzoom:image:stats:max_hi'  # gmpy2.mpfr
META_IMAGE_STATS_MIN_LO_KEY = 'tranzoom:image:stats:min_lo'  # gmpy2.mpfr
META_IMAGE_STATS_MIN_HI_KEY = 'tranzoom:image:stats:min_hi'  # gmpy2.mpfr
META_IMAGE_STATS_ANG_LO_KEY = 'tranzoom:image:stats:ang_lo'  # gmpy2.mpfr
META_IMAGE_STATS_ANG_HI_KEY = 'tranzoom:image:stats:ang_hi'  # gmpy2.mpfr
META_IMAGE_STATS_IMAG_LO_KEY = 'tranzoom:image:stats:imag_lo'  # gmpy2.mpfr
META_IMAGE_STATS_IMAG_HI_KEY = 'tranzoom:image:stats:imag_hi'  # gmpy2.mpfr
META_FRACTAL_KEY = 'tranzoom:frame:fractal'  # str, ex "mandelbrot", one of frame.Fractal, lowercase
META_TOP_RE_KEY = 'tranzoom:frame:top_re'  # gmpy2.mpq -> converts to str as quotients
META_TOP_IM_KEY = 'tranzoom:frame:top_im'  # gmpy2.mpq
META_BOTTOM_RE_KEY = 'tranzoom:frame:bottom_re'  # gmpy2.mpq
META_BOTTOM_IM_KEY = 'tranzoom:frame:bottom_im'  # gmpy2.mpq
META_CENTER_RE_KEY = 'tranzoom:frame:center_re'  # gmpy2.mpq
META_CENTER_IM_KEY = 'tranzoom:frame:center_im'  # gmpy2.mpq
META_WIDTH_RE_KEY = 'tranzoom:frame:width_re'  # gmpy2.mpq
META_HEIGHT_IM_KEY = 'tranzoom:frame:height_im'  # gmpy2.mpq
META_PRECISION_KEY = 'tranzoom:frame:precision'  # int, in bits
META_MAGNIFICATION_ORDER_KEY = 'tranzoom:frame:magnification_order'  # float
# extra keys added to some images only
# images with exterior points (almost all!)
META_PIXEL_EXTERIOR_HISTOGRAM_KEY = 'tranzoom:image:exterior:histogram_summary'  # str
META_PIXEL_EXTERIOR_CUMULATIVE_HISTOGRAM_KEY = (
  'tranzoom:image:exterior:cumulative_histogram_summary'  # str
)
# images with interior points and a Set palette (so we have interior histograms)
META_PIXEL_INTERIOR_HISTOGRAM_KEY = 'tranzoom:image:interior:histogram_summary'  # str; can be ""!
META_PIXEL_INTERIOR_CUMULATIVE_HISTOGRAM_KEY = (
  'tranzoom:image:interior:cumulative_histogram_summary'  # str; can be ""!
)
# Julia extra keys
META_JULIA_RE_KEY = 'tranzoom:frame:julia_re'  # gmpy2.mpq, only added for Julia Set frames
META_JULIA_IM_KEY = 'tranzoom:frame:julia_im'  # gmpy2.mpq, only added for Julia Set frames
# Animation extra keys
META_ANIM_INITIAL_WIDTH_RE_KEY = 'tranzoom:animation:frame:initial_width_re'  # gmpy2.mpq
META_ANIM_INITIAL_HEIGHT_IM_KEY = 'tranzoom:animation:frame:initial_height_im'  # gmpy2.mpq
META_ANIM_MAGNITUDE_KEY = 'tranzoom:animation:zoom:magnitude'  # float
META_ANIM_MAGNITUDE_PER_STEP_KEY = 'tranzoom:animation:zoom:magnitude_per_step'  # float
META_ANIM_MAGNIFICATION_PER_STEP_KEY = 'tranzoom:animation:zoom:magnification_per_step'  # float
META_ANIM_DURATION_KEY = 'tranzoom:animation:duration'  # float
META_ANIM_FRAMES_KEY = 'tranzoom:animation:frames'  # int
META_ANIM_STEPS_KEY = 'tranzoom:animation:steps'  # int
META_ANIM_FPS_KEY = 'tranzoom:animation:fps'  # float
META_ANIM_LOOP_KEY = 'tranzoom:animation:loop'  # int; 0 means infinite loop; meaningless for MP4
# LLM extra keys
META_LLM_MODEL_KEY = 'tranzoom:llm:model'  # str (or "HUMAN"/META_LLM_MODEL_VALUE_HUMAN for human)
META_LLM_TEMPERATURE_KEY = 'tranzoom:llm:temperature'  # float
META_LLM_SEED_KEY = 'tranzoom:llm:seed'  # int (0 if not set)
META_LLM_QUERY_MEMORY_KEY = 'tranzoom:llm:query:memory'  # int; number of previous steps chat
META_LLM_QUERY_REASONING_KEY = 'tranzoom:llm:query:reasoning'  # bool; stored as "true"/"false"
META_LLM_QUERY_SETUP_KEY = 'tranzoom:llm:query:setup'  # str
META_LLM_QUERY_IMAGE_KEY = 'tranzoom:llm:query:image'  # str
META_LLM_QUERY_EXTRA_KEY = 'tranzoom:llm:query:extra'  # str
META_LLM_RESULT_JSON_KEY = 'tranzoom:llm:result:json'  # JSON with evaluation info from LLM or HUMAN
META_LLM_ZOOM_COUNT_KEY = 'tranzoom:llm:zoom:count'  # int; zoom iteration depth
# special values
META_LLM_MODEL_VALUE_HUMAN = 'HUMAN'  # used when the evaluation is done by a flesh-and-blood human

# pre-compiled constants for encoding/decoding
_PACK_IF = struct.Struct('>if')  # signed int32 + float32
_PACK_Q = struct.Struct('>Q')  # uint64

# image constants

type ImageInt32Array = array.array[int]  # type alias for the type of our pixel data array

# constants for drawing

_SQRT_TWO: float = math.sqrt(2)
_LINE_WIDTH_RATIO: int = 150  # line width will be max(1, sz//_LINE_WIDTH_RATIO) of the image width
_CIRCLE_RADIUS: int = 20
_LABEL_OFFSET: int = 5
# scale factor for converting stored Set interior integers back to |z| float magnitudes;
# interior points are stored as -(int(floor(scale * |z|)) + 1), with scale = RES / MAX_Z = RES / 2

# gmpy2.mpfr constants
_MPFR_ZERO: gmpy2.mpfr = gmpy2.mpfr('0')
_MPFR_ONE: gmpy2.mpfr = gmpy2.mpfr('1')
_MPFR_FOUR: gmpy2.mpfr = gmpy2.mpfr('4')

# gmpy2.mpq constants
_MPQ_ZERO: gmpy2.mpq = gmpy2.mpq('0')


class Error(frame.Error):
  """Base image exception."""


class Color(enum.Enum):
  """Color enum."""

  BLACK = (0, 0, 0)
  WHITE = (255, 255, 255)
  RED = (255, 0, 0)
  GREEN = (0, 255, 0)
  BLUE = (0, 0, 255)
  YELLOW = (255, 255, 0)
  CYAN = (0, 255, 255)
  MAGENTA = (255, 0, 255)


class FileType(enum.Enum):
  """File type enum."""

  PNG = 'png'  # also the file suffix!
  GIF = 'gif'
  MP4 = 'mp4'


class AnimationType(enum.Enum):
  """Animation type enum."""

  GIF = 'gif'  # also the file suffix!
  MP4 = 'mp4'


class OverlayType(enum.Enum):
  """Overlay type enum."""

  GRID = 'grid'
  CARDINAL = 'cardinal'


DEFAULT_ANIMATION_TYPE: AnimationType = AnimationType.GIF


# color constants


DEFAULT_MARK_COLOR: Color = Color.RED
DEFAULT_MARK_WIDTH: int = 1
MIN_MARK_WIDTH: int = 1
MAX_MARK_WIDTH: int = 50

# animation constants

MIN_FRAMES: int = 3  # sanity limit for number of frames in an animation
MAX_FRAMES: int = 100_000  # sanity limit for number of frames in an animation
MIN_DURATION: float = 0.1  # minimum duration of an animation in seconds, for sanity checking
MAX_DURATION: float = 45000.0  # maximum duration of an animation in seconds, for sanity checking
VIDEO_DURATION_STORE_SCALE = 40_000  # MAX_DURATION * VIDEO_DURATION_STORE_SCALE < 2**31; HASH!
MIN_FPS: float = 0.1  # minimum frames per second for an animation, for sanity checking
MAX_FPS: float = 30.0  # maximum frames per second for an animation, for sanity checking
MIN_LOOP: int = 0  # minimum number of loops for a GIF animation; 0 means infinite loop
MAX_LOOP: int = 1000  # maximum number of loops for a GIF animation, for sanity checking

MAX_ZOOM_MAGNIFICATION_10: float = 10000.0  # this is 10**10000 which is more than enough
DEFAULT_DEST_MAGNIFICATION_10: float = 1.0  # default dest magnification for zooms 10**1 = 10x zoom
DEFAULT_LOOP: int = 0  # 0 means infinite loop for GIFs
THRESHOLD_JUMPY_ZOOM_PER_FRAME: float = 1.25  # if zoom per frame is above this warn about jumpiness


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class FractalStats:
  """Defines Mandelbrot stats values, collected over the sample run."""

  # these 2 stats are always collected
  n_px: int  # total number of pixels in the image
  n_interior: int  # number of interior (Set) points in the image, pixels with escape iteration < 0

  # limits of |z| magnitudes for interior (Set) points
  max_lo: gmpy2.mpfr  # min(all max(|z|) for interior points)
  max_hi: gmpy2.mpfr  # max(all max(|z|) for interior points)
  min_lo: gmpy2.mpfr  # min(all min(|z|) for interior points)
  min_hi: gmpy2.mpfr  # max(all min(|z|) for interior points)

  # limits of angles for interior (Set) points, in [0, 1]
  ang_lo: gmpy2.mpfr  # min(all angles for interior points)
  ang_hi: gmpy2.mpfr  # max(all angles for interior points)

  # limits of the Imaginary Weight Average for interior (Set) points, in [0, 1]
  imag_lo: gmpy2.mpfr  # min(all sac values for interior points)
  imag_hi: gmpy2.mpfr  # max(all sac values for interior points)


# TODO: more stable animations
# instead of rendering each frame independently, we can have a class that knows about the
# whole intended journey and can have a special AsPixels() that normalizes once against all images


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ImageOutputConfig:
  """Groups all parameters that control how output images are named and saved on disk.

  This is a runtime-only config object — not part of the mathematical/DB representation.
  It is NOT a SerializingFractalObject: it carries no mathematical meaning and is never hashed.
  """

  path: pathlib.Path | None  # output directory; None means current working directory
  use_date: bool  # if True, include YYYYMMDDhhmmss in the file name
  use_hash: bool  # if True, include the content hash in the file name
  prefix: str  # file name prefix, e.g., "mandel" or "julia"


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class RenderParameters(frame.SerializingFractalObject):
  """Defines a transformation from math to image."""

  # ATTENTION: changing anything here changes the HASH!!
  tp: FileType = FileType.PNG
  escaped_pal: palette.Palette = palette.DEFAULT_PALETTE
  set_pal: palette.Palette | None = None  # if None, this must be a non-Set-computation
  mark_re: gmpy2.mpq = _MPQ_ZERO
  mark_im: gmpy2.mpq = _MPQ_ZERO
  mark_color: Color | None = None  # if None, no mark will be drawn
  mark_width: int = DEFAULT_MARK_WIDTH
  overlay: OverlayType | None = None  # overlay is independent of mark!

  def __post_init__(self) -> None:
    """Check parameters for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    # check type is valid
    if self.tp not in {FileType.PNG, FileType.GIF, FileType.MP4}:
      raise Error(f'Unknown file type: {self.tp}')
    # check overlay is valid: for now we only allow GRID overlay
    if self.overlay and self.overlay != OverlayType.GRID:
      raise Error(f'Unknown overlay: {self.overlay}')
    # check palettes are valid
    if self.escaped_pal not in palette.Palette:
      raise Error(f'Unknown escaped palette: {self.escaped_pal}')
    if self.set_pal is not None and self.set_pal not in palette.Palette:
      raise Error(f'Unknown set palette: {self.set_pal}')
    # check mark width is valid
    if not (MIN_MARK_WIDTH <= self.mark_width <= MAX_MARK_WIDTH):
      raise Error(
        f'Mark width must be between {MIN_MARK_WIDTH} and {MAX_MARK_WIDTH}, got {self.mark_width}'
      )
    # check mark color is valid
    if self.mark_color is None:
      # we do not allow mark_re/im to be non-zero if no mark to be added to image
      if self.mark_re != _MPQ_ZERO or self.mark_im != _MPQ_ZERO:
        raise Error(
          'Mark positions expected to be (0, 0) when no mark color is specified, '
          f'got ({self.mark_re}, {self.mark_im})'
        )
    else:
      if self.mark_color not in Color:
        raise Error(f'Unknown mark color: {self.mark_color}')
      r: int
      g: int
      b: int
      r, g, b = self.mark_color.value
      if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):  # noqa: PLR2004
        raise Error(f'Mark color RGB values must be between 0 and 255, got {self.mark_color}')

  def __str__(self) -> str:
    """Get string representation of the RenderParameters.

    Format is:
    - "{[<FILE_TYPE>: <ESCAPED_PALETTE>, <SET_PALETTE>]<MARK_IF_ANY><OVERLAY_IF_ANY>}"
    - `<FILE_TYPE>` is the file type in uppercase, like "PNG".
    - `<ESCAPED_PALETTE>` is the name of the palette used for escaped points, in
        lowercase, like "sunset".
    - `<SET_PALETTE>` is the name of the palette used for interior Set points, in lowercase,
        like "ocean", or "none" if not used.
    - `<MARK_IF_ANY>` is " + [MARK: <MARK_COLOR>/<MARK_WIDTH> @ (<MARK_RE>, <MARK_IM>)]" if a
        mark is specified, or "" if no mark is specified.
    - `<OVERLAY_IF_ANY>` is " + [OVERLAY: <OVERLAY_TYPE>]" if an overlay is specified,
        or "" if no overlay is specified.

    Returns:
      str: String representation of the RenderParameters.

    """
    mark: str = (
      ''
      if self.mark_color is None
      else (
        f' + [MARK: {self.mark_color.name.lower()}/{self.mark_width} '
        f'@ ({self.mark_re}, {self.mark_im})]'
      )
    )
    overlay: str = '' if self.overlay is None else f' + [OVERLAY: {self.overlay.name}]'
    return (
      '{'
      f'[{self.tp.name.upper()}, {self.escaped_pal.name}, '
      f'{self.set_pal.name if self.set_pal else "none"}]{mark}{overlay}'
      '}'
    )

  @property
  def json(self) -> tbase.JSONDict:
    """Get a JSON-serializable dictionary representation of the RenderParameters.

    Keys: `tp`, `escaped_pal`, `set_pal`, `mark_re`, `mark_im`, `mark_color`,
    `mark_width`, `overlay`.

    Returns:
      tbase.JSONDict: A dictionary representation of the RenderParameters.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'tp': self.tp.value,
      'escaped_pal': self.escaped_pal.value,
      'set_pal': self.set_pal.value if self.set_pal else None,
      'mark_re': str(self.mark_re),
      'mark_im': str(self.mark_im),
      # BEWARE: we store the mark color as lowercase name, not the RGB value
      'mark_color': self.mark_color.name.lower() if self.mark_color else None,
      'mark_width': self.mark_width,
      'overlay': self.overlay.value if self.overlay else None,
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> RenderParameters:
    """Create a RenderParameters from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from RenderParameters.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the RenderParameters.
          If the calculated hash does not match, an error is raised.

    Returns:
      RenderParameters: A RenderParameters object

    Raises:
      Error: on error

    """
    # create the object
    try:
      params = RenderParameters(  # object creation will check the data is valid and consistent
        tp=FileType(data['tp']),
        escaped_pal=palette.Palette(data['escaped_pal']),
        set_pal=palette.Palette(data['set_pal']) if data['set_pal'] is not None else None,
        mark_re=gmpy2.mpq(str(data['mark_re'])),
        mark_im=gmpy2.mpq(str(data['mark_im'])),
        mark_color=(  # upper -> convert by name
          Color[str(data['mark_color']).upper()] if data['mark_color'] is not None else None
        ),
        mark_width=int(str(data['mark_width'])),
        overlay=OverlayType(data['overlay']) if data['overlay'] is not None else None,
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid RenderParameters JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'RenderParameters {params.sha!r} does not match expected {check_hash!r}')
    return params


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ZoomParameters(frame.SerializingFractalObject):
  """Defines the zoom parameters for video planning and rendering."""

  # ATTENTION: changing anything here changes the HASH!!
  tp: AnimationType  # 'gif' or 'mp4'
  img: frame.ComputationParameters  # initial frame and computation parameters for all images
  render: RenderParameters  # render parameters for all images
  mag: gmpy2.mpq  # destination magnification
  n_frames: int  # number of frames in the animation
  duration: int  # round(duration in seconds * VIDEO_DURATION_STORE_SCALE): no float precision snafu
  loop: int = 0  # number of loops for GIFs; 0 means infinite loop; ignored for non-GIFs

  def __post_init__(self) -> None:
    """Check ZoomParameters for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    # check type is valid
    if self.tp not in {AnimationType.GIF, AnimationType.MP4}:
      raise Error(f'Unknown animation type: {self.tp}')
    # check magnification is valid
    if not (-MAX_ZOOM_MAGNIFICATION_10 <= self.mag <= MAX_ZOOM_MAGNIFICATION_10):
      raise Error(f'Magnification abs() must be <= {MAX_ZOOM_MAGNIFICATION_10}, got {self.mag}')
    if self.mag == _MPQ_ZERO:
      raise Error('Magnification cannot be zero')
    # check number of frames is valid
    if not (MIN_FRAMES <= self.n_frames <= MAX_FRAMES):
      raise Error(
        f'Number of frames must be between {MIN_FRAMES} and {MAX_FRAMES}, got {self.n_frames}'
      )
    # check duration is valid
    if not (MIN_DURATION <= (dur := self.duration / VIDEO_DURATION_STORE_SCALE) <= MAX_DURATION):
      raise Error(f'Duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {dur}')
    # check loop count is valid for GIFs
    if self.tp == AnimationType.GIF and not (MIN_LOOP <= self.loop <= MAX_LOOP):
      raise Error(f'Loop count for GIFs must be between {MIN_LOOP} and {MAX_LOOP}, got {self.loop}')
    if self.tp != AnimationType.GIF and self.loop != 0:
      raise Error(f'Loop count is only applicable for GIFs, got {self.loop} for {self.tp}')

  def __str__(self) -> str:
    """Get string representation of the ZoomParameters.

    Format is:
      "<[ANIMATION_TYPE]: [RENDER_PARAMETERS] -> [COMPUTATION_PARAMETERS] / "
      "([MAGNIFICATION], [N_FRAMES], [DURATION], [LOOP])>"

    Returns:
      str: String representation of the ZoomParameters.

    """
    return (
      f'<{self.tp.name.upper()}: {self.img} -> {self.render} / '
      f'({self.mag}, {self.n_frames}, {self.duration}, {self.loop})>'
    )

  @property
  def json(self) -> tbase.JSONDict:
    """Get a JSON-serializable dictionary representation of the ZoomParameters.

    Keys: `tp`, `img`, `render`, `mag`, `n_frames`, `duration`, `loop`.

    Returns:
      tbase.JSONDict: A dictionary representation of the ZoomParameters.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'tp': self.tp.value,
      'img': self.img.json,
      'render': self.render.json,
      'mag': str(self.mag),
      'n_frames': self.n_frames,
      'duration': self.duration,
      'loop': self.loop,
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> ZoomParameters:
    """Create a ZoomParameters from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from ZoomParameters.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the ZoomParameters.
          If the calculated hash does not match, an error is raised.

    Returns:
      ZoomParameters: A ZoomParameters object

    Raises:
      Error: on error

    """
    # create the object
    try:
      params = ZoomParameters(  # object creation will check the data is valid and consistent
        tp=AnimationType(data['tp']),
        img=frame.ComputationParameters.FromJson(cast('tbase.JSONDict', data['img'])),
        render=RenderParameters.FromJson(cast('tbase.JSONDict', data['render'])),
        mag=gmpy2.mpq(str(data['mag'])),
        n_frames=int(str(data['n_frames'])),
        duration=int(str(data['duration'])),
        loop=int(str(data['loop'])),
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid ZoomParameters JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'ZoomParameters {params.sha!r} does not match expected {check_hash!r}')
    return params


class Image:
  """A fractal image. Encapsulates the image operations.

  Attributes:
    escape (ImageInt32Array): An array storing the escape data for each pixel;
        this is not the color, but the raw data that will be converted to color later;
        the length of this array is equal to the total number of pixels in the image;
        the pixel at coordinates (x, y) is stored at index (y * width + x) in the array.
    stats (FractalStats | None): Optional stats about the fractal, collected during rendering;
        DO NOT COUNT on this being present unless this was a sample 16.16 render
        (see fractal._FractalAdaptiveIterations) where the stats are collected

  """

  @dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
  class Histogram:
    """Stores a histogram for a part of an image (usually set points and escaped points).

    Attributes:
      count (int): The total count of pixels in this histogram
      min_value (int): The minimum int value in this histogram
      max_value (int): The maximum int value in this histogram
      linear (list[tuple[int, int]]): A sorted list of (value, count) pairs representing the
          histogram of int values in this category, sorted by value.
      cumulative (list[tuple[int, int]]): A sorted list of (value, cumulative_count) pairs
          representing the cumulative int histogram, sorted by value.

    """

    count: int
    min_value: int
    max_value: int
    linear: list[tuple[int, int]]  # sorted!
    d_linear: dict[int, int]  # {value: count}, for O(1) lookups
    cumulative: list[tuple[int, int]]  # sorted!
    d_cumulative: dict[int, int]  # {value: cumulative_count}, for O(1) lookups

  def __init__(self, params: frame.ComputationParameters) -> None:
    """Construct image.

    Args:
      params (frame.ComputationParameters): The computation parameters for the image.

    Raises:
      Error: on error

    """
    # save objects
    self._params: frame.ComputationParameters = params
    # initialize image data array; self._escape stores the ESCAPE ITERATION data, not the color
    self.escape: ImageInt32Array = array.array(  # signed32
      'L', (0 for _ in range(self._params.width * self._params.height))
    )
    if self.escape.itemsize != 8:  # frame.N_BYTES_UINT:
      raise Error(f'unsupported platform: array of unsigned ints is not {frame.N_BYTES_UINT} bytes')
    self.stats: FractalStats | None = None  # may be set later by the fractal rendering function
    # histogram of escaped points
    self.ext_hist: Image.Histogram | None = None  # set later by calling RebuildHistograms
    # histogram of interior (Set) points; flipped, i.e., positive values
    self.int_hist: Image.Histogram | None = None  # set later by calling RebuildHistograms

  # def SetEscape(self, x: int, y: int, escaped_at: int) -> None:
  #   """Set the escape iteration for a given pixel.

  #   Args:
  #     x (int): The x coordinate of the pixel.
  #     y (int): The y coordinate of the pixel.
  #     escaped_at (int): The escape iteration to set for the pixel.

  #   Raises:
  #     Error: if the pixel coordinates are out of bounds

  #   """
  #   if not (0 <= x < self._params.width) or not (0 <= y < self._params.height):
  #     raise Error(
  #       f'Coordinates out of bounds: {x=}, {y=}, {self._params.width=}, {self._params.height=}'
  #     )
  #   self.escape[y * self._params.width + x] = escaped_at

  @property
  def params(self) -> frame.ComputationParameters:
    """Get the computation parameters associated with this image.

    Returns:
      frame.ComputationParameters: The computation parameters associated with this image.

    """
    return self._params

  # @property
  # def escape_range(self) -> tuple[int, int, int, int]:
  #   """Get the range of escape iterations and the range of the internal stored values.

  #   The internal values map to different things depending on how they were computed.

  #   Returns:
  #     tuple[int, int, int, int]: (min_escape, max_escape, min_internal, max_internal)

  #   """
  #   exterior_points: list[int] = [e for e in self.escape if e >= 0]
  #   interior_points: list[int] = [e for e in self.escape if e < 0]
  #   return (
  #     min(exterior_points) if exterior_points else 0,
  #     self._params.depth if interior_points else (max(exterior_points) if exterior_points else 0),
  #     -max(interior_points) if interior_points else 0,
  #     -min(interior_points) if interior_points else 0,
  #   )

  def RebuildHistograms(self) -> None:
    # for efficiency, try to go over only once
    exterior_points: list[int] = []
    interior_points: list[int] = []
    for enc_px in self.escape:
      px: int = Decode64ToIntFloat(enc_px)[0]
      if px >= 0:
        exterior_points.append(px)
      else:
        interior_points.append(-px)  # we flip the sign for interior points!
    # have 2 groups of pixels
    self.ext_hist = BuildCumulative(exterior_points)  # ext generator
    self.int_hist = BuildCumulative(interior_points)  # int generator

  def AsPixels(self, render: RenderParameters) -> bytes:
    """Convert the image to raw pixel bytes using histogram-equalized smooth color palette.

    Exterior points (escaped) are colored by mapping their escape iteration through a cumulative
    histogram distribution (histogram equalization) into [0, 1), which is then fed into a smooth
    cycling color gradient via (PixelPalette). This ensures the full color range is used
    regardless of zoom depth or iteration distribution.

    Interior (Set) points that never escaped are rendered as pure black by default. When
    `color_set_points=True`, they are instead colored using `set_pal` via the same histogram
    equalization approach, applied to their stored |z| magnitude (the negative of the stored
    escape value), so the full `set_pal` range is used across the Set interior.

    Args:
      render (RenderParameters): The render parameters to use for generating the PNG metadata.

    Returns:
      bytes: Raw pixel data in RGB format (3 bytes per pixel).

    Raises:
      Error: on error

    """
    # populate histograms if not done yet
    if not self.ext_hist or not self.int_hist:
      self.RebuildHistograms()  # this will populate self.ext_hist and self.int_hist
    if not self.ext_hist or not self.int_hist:
      raise Error('Failed to build histograms for image')
    # check basic consistency
    if self.ext_hist.min_value < 0 or self._params.depth < self.ext_hist.max_value:
      raise Error(
        f'Invalid/Inconsistent {self.ext_hist.min_value=} or '
        f'{self._params.depth=} < {self.ext_hist.max_value=}'
      )
    # step 3: map each pixel to an RGB color
    pixels = bytearray(self._params.width * self._params.height * 3)
    for i, enc_escaped_at in enumerate(self.escape):
      escaped_at: int = Decode64ToIntFloat(enc_escaped_at)[0]
      if escaped_at >= 0 and self.ext_hist.count > 0:
        # exterior point: histogram-equalized position in pal
        t: float = (self.ext_hist.d_cumulative[escaped_at] - 1) / self.ext_hist.count
        rgb: tuple[int, int, int] = PixelPalette(t, render.escaped_pal, palette.PALETTE_CYCLES)
      elif self._params.set_points and self.int_hist.count > 0 and escaped_at < 0:
        # interior (Set) point: histogram-equalized position in set_pal over |z| magnitudes
        t_set: float = (self.int_hist.d_cumulative[-escaped_at] - 1) / self.int_hist.count
        if render.set_pal is None:
          raise Error('set_pal must be specified in RenderParameters when set_points is True')
        rgb = PixelPalette(t_set, render.set_pal, palette.SET_PALETTE_CYCLES)
      else:
        rgb = (0, 0, 0)  # black: interior point (default) or all-interior image
      pixels[i * 3], pixels[i * 3 + 1], pixels[i * 3 + 2] = rgb
    return bytes(pixels)

  def AsPNG(self, render: RenderParameters) -> tuple[bytes, str]:
    """Convert the image to PNG bytes and return it with its internal data hash.

    Args:
      render (RenderParameters): The render parameters to use for generating the PNG metadata.

    Returns:
      tuple[bytes, str]: PNG image data and its internal data hash.

    """
    # convert the raw pixel data to a PNG using PIL
    raw_img: bytes = self.AsPixels(render)
    img_data_hash: str = hashes.Hash256(raw_img).hex()
    img: PILImage.Image = PILImage.frombytes(
      'RGB', (self._params.width, self._params.height), raw_img
    )
    # embed frame parameters as PNG tEXt metadata chunks; keys use a "tranzoom:" namespace
    png_meta = PngImagePlugin.PngInfo()
    for k, v in MakeImageMeta(self, render, img_data_hash).items():
      png_meta.add_text(k, v)
    # save to PNG bytes, hash and return
    buf = io.BytesIO()
    img.save(buf, format='PNG', pnginfo=png_meta)
    return (buf.getvalue(), img_data_hash)


def MakeImageMeta(img: Image, render: RenderParameters, data_hash: str) -> dict[str, str]:  # noqa: C901
  """Create a metadata dictionary for the image.

  Args:
    img (Image): The image for which to create metadata.
    render (RenderParameters): The render parameters used for the image.
    data_hash (str): The hash of the image data, to include in the metadata.

  Returns:
    dict[str, str]: A dictionary containing the metadata for the image, with keys as defined

  Raises:
    Error: on error

  """
  # populate histograms if not done yet
  if not img.ext_hist or not img.int_hist:
    img.RebuildHistograms()  # this will populate img.ext_hist and img.int_hist
  if not img.ext_hist or not img.int_hist:
    raise Error('Failed to build histograms for image')
  # prepare some data that will be needed
  frm: frame.Frame = img.params.frm
  center: tuple[gmpy2.mpq, gmpy2.mpq] = frm.center
  sz: tuple[gmpy2.mpq, gmpy2.mpq] = frm.size
  # first create a dict with all the ones that are always present, then add the optional ones
  img_meta: dict[str, str] = {
    # image parameters
    META_IMAGE_ANIMATION_KEY: 'none',  # this is a static image for now, not an animation
    META_IMAGE_WIDTH_KEY: str(img.params.size[0]),
    META_IMAGE_HEIGHT_KEY: str(img.params.size[1]),
    META_IMAGE_HASH_KEY: data_hash,
    META_IMAGE_COLOR_SET_KEY: str(img.params.set_points.value) if img.params.set_points else 'none',
    META_RENDER_PALETTE_KEY: render.escaped_pal.value,
    META_RENDER_SET_PALETTE_KEY: render.set_pal.value if render.set_pal else 'none',
    META_RENDER_OVERLAY_KEY: render.overlay.value if render.overlay else 'none',
    META_RENDER_MARK_RE_KEY: str(render.mark_re),
    META_RENDER_MARK_IM_KEY: str(render.mark_im),
    META_RENDER_MARK_COLOR_KEY: render.mark_color.name.lower() if render.mark_color else 'none',
    META_RENDER_MARK_WIDTH_KEY: str(render.mark_width),  # int
    # frame
    META_FRACTAL_KEY: frm.fractal.value.lower(),
    # frame as corners
    META_TOP_RE_KEY: str(frm.top_re),
    META_TOP_IM_KEY: str(frm.top_im),
    META_BOTTOM_RE_KEY: str(frm.bottom_re),
    META_BOTTOM_IM_KEY: str(frm.bottom_im),
    # frame as center + size
    META_CENTER_RE_KEY: str(center[0]),
    META_CENTER_IM_KEY: str(center[1]),
    META_WIDTH_RE_KEY: str(sz[0]),
    META_HEIGHT_IM_KEY: str(sz[1]),
    # precision and magnification
    META_PRECISION_KEY: str(img.params.precision),
    META_MAGNIFICATION_ORDER_KEY: str(frm.magnification[1]),
    # escape iteration range in the image
    META_ITER_DEPTH_MIN_KEY: str(img.ext_hist.min_value),
    META_ITER_DEPTH_MAX_KEY: str(img.ext_hist.max_value),
    META_SET_POINT_MIN_KEY: str(img.int_hist.min_value),
    META_SET_POINT_MAX_KEY: str(img.int_hist.max_value),
    META_ITER_SEARCH_DEPTH_KEY: str(img.params.depth),
    # histogram
    META_PIXEL_EXTERIOR_COUNT_KEY: str(img.ext_hist.count),
    META_PIXEL_INTERIOR_COUNT_KEY: str(img.int_hist.count),
  }
  # histograms
  if img.ext_hist.count > 0:
    img_meta[META_PIXEL_EXTERIOR_HISTOGRAM_KEY] = SummaryHistogram(img.ext_hist.linear)
    img_meta[META_PIXEL_EXTERIOR_CUMULATIVE_HISTOGRAM_KEY] = SummaryHistogram(
      img.ext_hist.cumulative
    )
  if img.params.set_points and img.int_hist.count > 0:
    img_meta[META_PIXEL_INTERIOR_HISTOGRAM_KEY] = SummaryHistogram(img.int_hist.linear)
    img_meta[META_PIXEL_INTERIOR_CUMULATIVE_HISTOGRAM_KEY] = SummaryHistogram(
      img.int_hist.cumulative
    )
  # add any stats that aren't just noise
  if img.stats:
    if img.stats.max_lo != _MPFR_FOUR or img.stats.max_hi != _MPFR_ZERO:
      img_meta[META_IMAGE_STATS_MAX_LO_KEY] = str(img.stats.max_lo)
      img_meta[META_IMAGE_STATS_MAX_HI_KEY] = str(img.stats.max_hi)
    if img.stats.min_lo != _MPFR_FOUR or img.stats.min_hi != _MPFR_ZERO:
      img_meta[META_IMAGE_STATS_MIN_LO_KEY] = str(img.stats.min_lo)
      img_meta[META_IMAGE_STATS_MIN_HI_KEY] = str(img.stats.min_hi)
    if img.stats.ang_lo != _MPFR_ONE or img.stats.ang_hi != _MPFR_ZERO:
      img_meta[META_IMAGE_STATS_ANG_LO_KEY] = str(img.stats.ang_lo)
      img_meta[META_IMAGE_STATS_ANG_HI_KEY] = str(img.stats.ang_hi)
    if img.stats.imag_lo != _MPFR_ONE or img.stats.imag_hi != _MPFR_ZERO:
      img_meta[META_IMAGE_STATS_IMAG_LO_KEY] = str(img.stats.imag_lo)
      img_meta[META_IMAGE_STATS_IMAG_HI_KEY] = str(img.stats.imag_hi)
  # Julia
  if frm.fractal == frame.Fractal.JULIA:
    img_meta[META_JULIA_RE_KEY] = str(frm.point_re)
    img_meta[META_JULIA_IM_KEY] = str(frm.point_im)
  # save to PNG bytes, hash and return
  return img_meta


def SummaryHistogram(sorted_histogram: list[tuple[int, int]]) -> str:
  """Summarize a histogram as a string, showing the first 3, last 3 values, summarizing the middle.

  Args:
    sorted_histogram (list[tuple[int, int]]): A list of (key, count) tuples representing
        the histogram, SORTED by key.

  Returns:
    str: A string representation of the histogram, showing the first 3 and last 3 values,
        with the middle values summarized as a total count.

  """
  if len(sorted_histogram) <= 7:  # noqa: PLR2004
    # small histogram, no need to summarize
    return str(sorted_histogram)
  # this is usually the case: many escape values, so summarize the middle ones
  return str(
    # make a new list with the first 3 and last 3 values, and a summary of the middle values "..."
    [
      *sorted_histogram[:3],
      ('...', sum(count for _, count in sorted_histogram[3:-3])),
      *sorted_histogram[-3:],
    ]
  )


def MakeImagePath(
  img_output_path: pathlib.Path | None,
  img_use_date: bool,
  img_use_hash: bool,
  img_path_prefix: str,
  raw_hash: str,
  *,
  tm: int | None = None,
  add_serial: int | None = None,
  suffix: str = 'png',
) -> pathlib.Path:
  """Make a file path for saving the image, based on the configuration and image hash.

  Args:
    img_output_path (pathlib.Path | None): The output directory path. If None, the current
        directory is used.
    img_use_date (bool): Whether to include the current date in the file name.
    img_use_hash (bool): Whether to include the image hash in the file name.
    img_path_prefix (str): The prefix for the file name.
    raw_hash (str): The hash of the image data.
    tm (int | None): Optional timestamp to use for the date in the file name. If None, the
        current time is used.
    add_serial (int | None): Optional serial number to include in the file name for uniqueness;
        if None, no serial number is included; if provided, it is formatted as a zero-padded
        5-digit number between the date and hash.
    suffix (str): The file extension/suffix to use, default is "png".

  Returns:
    pathlib.Path: The full path for saving the image.

  Raises:
    Error: If the img_path_prefix is invalid (contains path separators).

  """
  # save the image to a file named by its time/hash
  tm_str: str = time.strftime('%Y%m%d%H%M%S', time.gmtime(tm or timer.Now()))
  # validate that img_path_prefix is a basename (no path separators) to prevent directory traversal
  filename: str = img_path_prefix
  if pathlib.Path(filename).name != img_path_prefix:
    raise Error(f'Invalid prefix: {img_path_prefix!r} has path separators (ex: "/" or "\\")')
  # add date and hash to the file name if requested
  if img_use_date:
    filename += f'-{tm_str}'
  if add_serial is not None:
    filename += f'-{add_serial:05}'  # add a serial number
  if img_use_hash:
    # use 20 chars of the hash to avoid very long file names; 20 chars = 10 bytes = 80 bits;
    # collision is 1 in 2**40 ~ 1 in 1 trillion, which is good enough for our use case
    filename += f'-{raw_hash[:20]}'
  # add .png extension, make full path, and save the file
  filename += '.' + suffix.strip().lower()
  return (
    (pathlib.Path(filename) if img_output_path is None else img_output_path / filename)
    .expanduser()
    .resolve()
  )


def GetBasicDataFromImage(img_bytes: bytes) -> tuple[int, int, str, tbase.JSONDict]:
  """Get basic data from a PNG image, including format, size, hash, and metadata text.

  Args:
    img_bytes (bytes): The PNG image data as bytes.

  Returns:
    tuple[int, int, str, tbase.JSONDict]: (width, height, hash, metadata) where:
      - width: The width of the image in pixels.
      - height: The height of the image in pixels.
      - hash: A hash of the image data (SHA256 of RGB bytes).
      - metadata: The extracted metadata from the image.

  Raises:
    Error: If the image format is unsupported or if there are issues processing the image.

  """
  with PILImage.open(io.BytesIO(img_bytes)) as img:
    # get the internal data we need (size and hash)
    width: int = img.width
    height: int = img.height
    if width < 1 or height < 1:
      raise Error(f'Invalid image size {width}x{height}')
    raw_hash: str = hashes.Hash256(img.convert('RGB').tobytes()).hex()  # not 'RGBA'!!
    # extract metadata from PNG
    pil_info: tbase.JSONDict = img.info  # type: ignore[assignment]
    # make sure format is known and do any format-specific operations
    if (img_format := (img.format or '').upper()) == FileType.PNG.value.upper():
      pass  # nothing else to do for PNG, the metadata is already extracted in pil_info
    elif img_format == FileType.GIF.value.upper():
      # for GIFs we expect the metadata to be stored in the "comment" field as a JSON string
      if 'comment' in pil_info:
        try:
          pil_info = json.loads(cast('bytes', pil_info['comment']).decode('utf-8'))
          # if we managed to extract this, then maybe we can also get the correct hash
          if META_IMAGE_HASH_KEY in pil_info:
            raw_hash = str(pil_info[META_IMAGE_HASH_KEY])
          else:
            logging.error('DO NOT trust this GIF hash')
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
          # if comment is not valid JSON, just keep the original pil_info
          logging.error('GIF image has comment metadata but it is not valid JSON, ignoring it')  # noqa: TRY400
          logging.error('DO NOT trust this GIF hash')  # noqa: TRY400
    elif img_format == FileType.MP4.value.upper():
      raise NotImplementedError('MP4 format is not supported yet')
    else:
      raise Error(f'Unsupported image format {img.format!r}, expected PNG')
  return (width, height, raw_hash, pil_info)


def DrawCardinalInfoOverlay(img_data: bytes) -> bytes:
  """Draw an overlay on the (512x512) image with target info for moving the zoom frame.

  Overlays is:
  - white lines delimiting the quadrants of the image, intersecting at the center
  - 8 green circles around the center, indicating the 8 cardinal and ordinal directions
    to move the frame
  - each circle has a green label with its direction: "N", "NE", "E", "SE", "S", "SW", "W", "NW"

  Works on any size image, but is designed for 512x512, especially because of:
  - circle radius is fixed
  - text labels are fixed size and positioned with a fixed offset from the circle's center
  Fix these and it can work well on other sizes too...

  Args:
    img_data (bytes): The PNG image data as bytes.

  Returns:
    bytes: The modified PNG image data with the overlay drawn.

  """
  w: int
  h: int
  cx: int
  cy: int
  x: int
  y: int
  lw: int
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
    # draw the quadrant lines
    draw: ImageDraw.ImageDraw = ImageDraw.ImageDraw(img)
    w, h = img.size
    cx, cy = w // 2, h // 2
    step_sz: int = w // frame.DEFAULT_STEP_DIRECT
    lw = max(1, max(w, h) // _LINE_WIDTH_RATIO)
    draw.line((0, cy, w, cy), fill=Color.WHITE.value, width=lw)
    draw.line((cx, 0, cx, h), fill=Color.WHITE.value, width=lw)
    # draw 8 circles around the center to indicate the 8 cardinal/ordinal directions
    font: ImageFont.ImageFont = cast('ImageFont.ImageFont', ImageFont.load_default())
    for dx, dy, direction in [
      (0, -step_sz, 'N'),
      (step_sz / _SQRT_TWO, -step_sz / _SQRT_TWO, 'NE'),
      (step_sz, 0, 'E'),
      (step_sz / _SQRT_TWO, step_sz / _SQRT_TWO, 'SE'),
      (0, step_sz, 'S'),
      (-step_sz / _SQRT_TWO, step_sz / _SQRT_TWO, 'SW'),
      (-step_sz, 0, 'W'),
      (-step_sz / _SQRT_TWO, -step_sz / _SQRT_TWO, 'NW'),
    ]:
      x, y = int(cx + dx), int(cy + dy)
      draw.ellipse(
        (x - _CIRCLE_RADIUS, y - _CIRCLE_RADIUS, x + _CIRCLE_RADIUS, y + _CIRCLE_RADIUS),
        outline=Color.GREEN.value,
        width=lw,
      )
      # for each circle, also draw the label text
      draw.text(
        (x - _LABEL_OFFSET, y - _LABEL_OFFSET), direction, fill=Color.GREEN.value, font=font
      )
    # done, save remembering to add metadata that this image has an overlay
    return SaveWithMeta(img)


def DrawThirdsInfoOverlay(img_data: bytes) -> bytes:
  """Draw an overlay on an image of any size, with target info for moving the zoom frame.

  Overlays:
  - white lines delimiting the 9 sections of the image
  - large green number labels (1-9) centered in each section, left-to-right, top-to-bottom

  Args:
    img_data (bytes): The PNG image data as bytes.

  Returns:
    bytes: The modified PNG image data with the overlay drawn.

  """
  w: int
  h: int
  cx: int
  cy: int
  col: int
  row: int
  lw: int
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
    # draw the thirds lines
    draw: ImageDraw.ImageDraw = ImageDraw.ImageDraw(img)
    w, h = img.size
    cx, cy = w // 3, h // 3
    lw = max(1, max(w, h) // _LINE_WIDTH_RATIO)
    draw.line((0, cy, w, cy), fill=Color.WHITE.value, width=lw)
    draw.line((0, 2 * cy, w, 2 * cy), fill=Color.WHITE.value, width=lw)
    draw.line((cx, 0, cx, h), fill=Color.WHITE.value, width=lw)
    draw.line((2 * cx, 0, 2 * cx, h), fill=Color.WHITE.value, width=lw)
    # draw large number labels centered in each of the 9 sections, left-to-right, top-to-bottom
    label_font: ImageFont.FreeTypeFont = cast(
      'ImageFont.FreeTypeFont', ImageFont.load_default(size=int(max(cx, cy) / 3))
    )
    for row in range(3):
      for col in range(3):
        draw.text(
          (col * cx + cx // 2, row * cy + cy // 2),  # center of this section
          str(row * 3 + col + 1),  # label
          fill=Color.GREEN.value,
          font=label_font,
          anchor='mm',  # center it exactly
        )
    # done, save remembering to add metadata that this image has an overlay
    return SaveWithMeta(img)


def DrawCrossOverlay(
  img_data: bytes, x: int, y: int, *, col: Color = DEFAULT_MARK_COLOR, lw: int = DEFAULT_MARK_WIDTH
) -> bytes:
  """Draw a cross overlay on an image at the specified coordinates.

  Overlays:
  - a horizontal line spanning the image at the given y-coordinate
  - a vertical line spanning the image at the given x-coordinate

  Args:
    img_data (bytes): The PNG image data as bytes.
    x (int): The x-coordinate of the center of the cross.
    y (int): The y-coordinate of the center of the cross.
    col (Color): The color of the cross.
    lw (int): The line width of the cross.

  Returns:
    bytes: The modified PNG image data with the overlay drawn.

  Raises:
    Error: If the coordinates are out of bounds or if there are issues processing the image.

  """
  w: int
  h: int
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
    # check the coords
    draw: ImageDraw.ImageDraw = ImageDraw.ImageDraw(img)
    w, h = img.size
    if not (0 <= x < w) or not (0 <= y < h):
      raise Error(f'Invalid coordinates for cross overlay: {x=}, {y=}, image size {w}x{h}')
    # draw the cross lines
    draw.line((0, y, w, y), fill=col.value, width=lw)
    draw.line((x, 0, x, h), fill=col.value, width=lw)
    # done, save remembering to add metadata that this image has an overlay
    return SaveWithMeta(img)


def SaveWithMeta(img: PILImage.Image, *, extra_meta: dict[str, str] | None = None) -> bytes:
  """Save a PIL image to PNG bytes, including its metadata.

  Args:
    img (PILImage.Image): The PIL image to save.
    extra_meta (dict[str, str] | None): Optional additional metadata to include in the PNG.

  Returns:
    bytes: The PNG image data as bytes.

  Raises:
    Error: if there are issues saving the image or with the metadata.

  """
  # we have to re-copy the metadata from the original image
  png_meta = PngImagePlugin.PngInfo()
  for k, v in img.info.items():
    if not isinstance(k, str):
      raise Error(f'Unexpected non-string PNG metadata pair: {k!r}: {v!r}')
    png_meta.add_text(k, str(v))
  if extra_meta:
    for k, v in extra_meta.items():
      png_meta.add_text(k, v)
  # save to PNG bytes, return
  output = io.BytesIO()
  img.save(output, format='PNG', pnginfo=png_meta)
  return output.getvalue()


def AddEvaluationMetaToImage(
  img_data: bytes,
  response: tbase.JSONDict,
  model: str,
  temperature: float,
  seed: int,
  reason: bool,
  query_memory: int,
  query_setup: str,
  query_image: str,
  query_manual: str | None,
  count: int,
) -> bytes:
  """Add LLM evaluation info to the image metadata and return the modified PNG bytes.

  Args:
    img_data (bytes): The original PNG image data as bytes.
    response (tbase.JSONDict): The LLM evaluation response to add to the metadata.
    model (str): The LLM model used for evaluation; if this is "HUMAN"/META_LLM_MODEL_VALUE_HUMAN,
        then it will not add temperature, seed, reason, query_memory, query_setup, query_image, nor
        query_manual to the metadata.
    temperature (float): The temperature setting used for the LLM evaluation.
    seed (int): The random seed used for the LLM evaluation.
    reason (bool): Whether the LLM response includes reasoning steps
    query_memory (int): The memory parameter used for the LLM evaluation.
    query_setup (str): The setup query given to the LLM.
    query_image (str): The image query given to the LLM.
    query_manual (str | None): The manual query passed as extra into the query.
    count (int): The zoom step count at which this evaluation was made.

  Returns:
    bytes: The modified PNG image data as bytes, with the evaluation info added to the metadata.

  """
  # start with the metadata that all zoom images have, for now
  new_meta: dict[str, str] = {
    META_LLM_MODEL_KEY: model,  # could be "HUMAN"/META_LLM_MODEL_VALUE_HUMAN
    META_LLM_RESULT_JSON_KEY: json.dumps(response),
    META_LLM_ZOOM_COUNT_KEY: str(count),
  }
  if model != META_LLM_MODEL_VALUE_HUMAN:
    new_meta.update(
      # add the non-human metadata
      {
        META_LLM_TEMPERATURE_KEY: str(temperature),
        META_LLM_SEED_KEY: str(seed),
        META_LLM_QUERY_MEMORY_KEY: str(query_memory),
        META_LLM_QUERY_SETUP_KEY: query_setup,
        META_LLM_QUERY_IMAGE_KEY: query_image,
        META_LLM_QUERY_EXTRA_KEY: query_manual or '',
        META_LLM_QUERY_REASONING_KEY: str(reason).lower(),  # store as "true"/"false"
      }
    )
  with PILImage.open(io.BytesIO(img_data)) as img:
    return SaveWithMeta(img, extra_meta=new_meta)


def PrintITerm2(img_data: bytes) -> None:
  """Print the image to `sys.stdout` in iTerm2, using the iTerm2 inline image protocol.

  <https://iterm2.com/documentation-images.html>

  Args:
    img_data (bytes): The original PNG image data as bytes.

  """
  sys.stdout.write(
    f'\x1b]1337;File=inline=1;size={len(img_data)}:{base64.b64encode(img_data).decode("ascii")}\a\n'
  )
  sys.stdout.flush()


def PixelPalette(
  t: float,
  pal: palette.Palette,
  cycles: int,
) -> tuple[int, int, int]:
  """Get the RGB color for a histogram-equalized normalized palette position.

  Smoothly interpolates between adjacent stops in the specified palette, cycling
  `cycles` times across the [0, 1) range. Use PALETTE_CYCLES (3) for exterior palettes
  (tighter color banding) and SET_PALETTE_CYCLES (1) for the interior Set palette
  (single smooth gradient, black near the boundary).

  Args:
    t (float): Normalized position in [0, 1) derived from histogram equalization.
    pal (Palette): The palette to use.
    cycles (int): How many times to cycle through the palette across [0, 1)

  Returns:
    tuple[int, int, int]: The interpolated RGB color.

  Raises:
    Error: if the palette name is unknown or if there are issues computing the color.

  """
  # get the palette stops
  if pal not in palette.PALETTES:
    raise Error(f'Unknown palette {pal!r}, available: {list(palette.PALETTES.keys())}')
  palette_stops: tuple[tuple[int, int, int], ...] = palette.PALETTES[pal]
  # cycle through the palette the requested number of times for visual banding
  t_cycled: float = (t * cycles) % 1.0
  n: int = len(palette_stops)
  # fractional index into the palette
  idx: float = t_cycled * n
  lo: int = int(idx) % n
  hi: int = (lo + 1) % n
  frac: float = idx - int(idx)
  r0, g0, b0 = palette_stops[lo]
  r1, g1, b1 = palette_stops[hi]
  return (
    int(r0 + frac * (r1 - r0)),
    int(g0 + frac * (g1 - g0)),
    int(b0 + frac * (b1 - b0)),
  )


def BuildCumulative(values: abc.Iterable[int]) -> Image.Histogram:
  """Build a raw histogram and cumulative histogram from a pre-filtered list of integer values.

  Args:
    values (abc.Iterable[int]): The iterable of integer values to histogram.

  Returns:
    Image.Histogram: The histogram object containing the raw and cumulative histograms and
        the total count.

  """
  # build the raw histogram
  histogram: dict[int, int] = {}
  total: int = 0
  for v in values:
    histogram[v] = histogram.get(v, 0) + 1
    total += 1
  # return trivial case (that would cause issues with min() and max())
  if not histogram:
    return Image.Histogram(
      count=0, min_value=0, max_value=0, linear=[], cumulative=[], d_linear={}, d_cumulative={}
    )
  # build the cumulative histogram by iterating over the sorted keys of the raw histogram
  cum: int = 0
  s_histogram: list[tuple[int, int]] = sorted(histogram.items())
  s_cum: list[tuple[int, int]] = []
  for v, c in s_histogram:
    cum += c
    s_cum.append((v, cum))
  # build object and return
  return Image.Histogram(
    count=total,
    min_value=min(histogram),
    max_value=max(histogram),
    linear=s_histogram,
    cumulative=s_cum,
    d_linear=histogram,
    d_cumulative=dict(s_cum),
  )


def _ImageNormalizeAndValidate(img_bytes: bytes, width: int, height: int) -> PILImage.Image:
  with PILImage.open(io.BytesIO(img_bytes)) as img:
    if img.size != (width, height):
      raise Error(f'frame size {img.size} != {(width, height)}')
    if img.mode != 'RGB':
      raise Error(f'expected RGB frame, got mode {img.mode!r}')
    return img.copy()


def WriteAnimatedGIF(
  frames: list[bytes],
  path: pathlib.Path,
  width: int,
  height: int,
  n_frames: int,
  duration: float,
  *,
  meta: dict[str, str] | None = None,
  loop: int = 0,  # 0 == infinite loop
) -> None:
  """Write PIL Image frames to an animated GIF.

  Args:
    frames (list[bytes]): An iterable of PIL Image frames to include in the GIF.
    path (pathlib.Path): The file path to save the GIF.
    width (int): The width of the GIF frames.
    height (int): The height of the GIF frames.
    n_frames (int): The number of frames in the GIF: has to match exactly the number of frames
        provided.
    duration (float): The duration of the GIF, in seconds.
    loop (int): The number of times to loop the GIF (0 for infinite loop). Default is 0
        (infinite loop).
    meta (dict[str, str] | None): Optional metadata to include in the GIF; default None

  Raises:
    Error: on error

  """
  # check inputs
  if not (MIN_FRAMES <= n_frames <= MAX_FRAMES):
    raise Error(f'n_frames must be between {MIN_FRAMES} and {MAX_FRAMES}, got {n_frames}')
  if not frames or len(frames) != n_frames:
    raise Error('frames list does not match the expected number of frames')
  if not (frame.MIN_IMAGE_SIZE <= width <= frame.MAX_IMAGE_SIZE) or not (
    frame.MIN_IMAGE_SIZE <= height <= frame.MAX_IMAGE_SIZE
  ):
    raise Error(
      f'{width=} and {height=} must be between {frame.MIN_IMAGE_SIZE} and {frame.MAX_IMAGE_SIZE}'
    )
  if not (MIN_DURATION <= duration <= MAX_DURATION):
    raise Error(f'duration must be between {MIN_DURATION} and {MAX_DURATION}, got {duration}')
  if loop < 0:
    raise Error(f'loop must be >= 0, got {loop}')
  # calculate fps and check sanity of duration vs n_frames
  fps: float = n_frames / duration
  if not (MIN_FPS <= fps <= MAX_FPS):
    raise Error(f'FPS={fps:.2f} must be between {MIN_FPS:.2f} and {MAX_FPS:.2f}')
  # save the whole GIF, normalizing each frame
  img0: PILImage.Image = _ImageNormalizeAndValidate(frames[0], width, height)
  img0.save(
    # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif
    path,
    save_all=True,
    # append without repeating the first frame, which is already saved as img0
    append_images=[_ImageNormalizeAndValidate(f, width, height) for f in frames[1:]],
    duration=round(1000.0 * duration / n_frames),  # duration in milliseconds per frame
    loop=loop,
    disposal=1,  # 1 == do not dispose, overwrite; more efficient b/c we don't have any transparency
    # delta-encode unchanged pixels as transparent to reduce file size
    optimize=True,  # optimize the palette and compression for smaller file size
    # GIF comment field can store arbitrary bytes, we use it to store JSON metadata
    comment=json.dumps(meta).encode('utf-8') if meta is not None else None,
  )


def WriteVideoMP4(
  frames: abc.Iterable[bytes],
  path: pathlib.Path,
  width: int,
  height: int,
  n_frames: int,
  duration: float,
  *,
  meta: dict[str, str] | None = None,
) -> None:
  """Write PIL Image frames to an MP4 video using H.264, the most broadly compatible video format.

  Args:
    frames (abc.Iterable[bytes]): An iterable of PIL Image frames to include in the video.
    path (pathlib.Path): The file path to save the video.
    width (int): The width of the video frames.
    height (int): The height of the video frames.
    n_frames (int): The number of frames in the video: has to match exactly the number of frames
        provided.
    duration (float): The duration of the video, in seconds.
    meta (dict[str, str] | None): Optional metadata to include in the video; default None

  Raises:
    Error: on error

  """
  # check inputs
  if not (MIN_FRAMES <= n_frames <= MAX_FRAMES):
    raise Error(f'n_frames must be between 2 and {MAX_FRAMES}, got {n_frames}')
  if not (frame.MIN_IMAGE_SIZE <= width <= frame.MAX_IMAGE_SIZE) or not (
    frame.MIN_IMAGE_SIZE <= height <= frame.MAX_IMAGE_SIZE
  ):
    raise Error(
      f'{width=} and {height=} must be between {frame.MIN_IMAGE_SIZE} and {frame.MAX_IMAGE_SIZE}'
    )
  if not (MIN_DURATION <= duration <= MAX_DURATION):
    raise Error(f'duration must be between {MIN_DURATION} and {MAX_DURATION}, got {duration}')
  # calculate fps and check sanity of duration vs n_frames
  fps: float = n_frames / duration
  if not (MIN_FPS <= fps <= MAX_FPS):
    raise Error(f'FPS={fps:.2f} must be between {MIN_FPS:.2f} and {MAX_FPS:.2f}')
  # prepare metadata
  output_params: list[str] = []
  output_params.extend(['-movflags', '+faststart'])  # allows start playing before fully downloaded
  output_params.extend(['-crf', '16'])  # good quality, lower is better
  output_params.extend(['-preset', 'slow'])  # slower presets give better compression
  if meta:
    for k, v in meta.items():
      output_params.extend(['-metadata', f'{k}={v}'])
  # save the whole MP4, normalizing each frame
  frame_count = 0
  with imageio.get_writer(  # pyright: ignore[reportUnknownMemberType]
    path,
    fps=fps,
    format='ffmpeg',  # type: ignore[arg-type]
    codec='libx264',
    pixelformat='yuv420p',
    macro_block_size=1,
    output_params=output_params,
  ) as writer:
    for frm in frames:
      writer.append_data(np.asarray(_ImageNormalizeAndValidate(frm, width, height)))  # type: ignore[attr-defined]
      frame_count += 1
  # done, check that the frame count matches n_frames
  if frame_count != n_frames:
    raise Error(f'frames generator produced {frame_count} frames, expected {n_frames}')


def EncodeIntFloatTo64(i: int, f: float) -> int:
  """Encode a signed int32 and a float32 into a single uint64, by concatenating their bits.

  This is benchmarked at ~1.6ns per call, ~160ms for a 1024x1024 image to encode all pixels.
  struct.pack()/unpack() does range checks already, so we DO NOT check inputs, as that degrades
  performance by a lot. We also use pre-compiled struct formats to speed this up.

  Args:
    i (int): The signed int32 to encode.
    f (float): The float32 to encode; garbage in, garbage out: if the float is not
        valid/finite (NaN or Inf), you will get the same garbage float back on Decode64ToIntFloat().

  Returns:
    int: The encoded uint64 containing both the int and float.

  Raises:
    Error: inputs out of range or other encoding issues

  """
  try:
    return cast('int', _PACK_Q.unpack(_PACK_IF.pack(i, f))[0])
  except (struct.error, OverflowError) as err:
    raise Error(f'Error encoding {i=} and {f=} to uint64: {err}') from err


def Decode64ToIntFloat(x: int) -> tuple[int, float]:
  """Decode a uint64 containing a signed int32 and a float32 back into its components.

  This is benchmarked at ~1.1ns per call, ~120ms for a 1024x1024 image to encode all pixels.
  struct.pack()/unpack() does range checks already, so we DO NOT check inputs, as that degrades
  performance by a lot. We also use pre-compiled struct formats to speed this up.

  Args:
    x (int): The uint64 to decode, where the high 32 bits represent a signed int32 and the
        low 32 bits represent a float32.

  Returns:
    tuple[int, float]: A tuple containing the decoded signed int32 and float32.

  Raises:
    Error: inputs out of range or other encoding issues

  """
  try:
    return _PACK_IF.unpack(_PACK_Q.pack(x))
  except (struct.error, OverflowError) as e:
    raise Error(f'Error decoding uint64 to int and float: {e}') from e
