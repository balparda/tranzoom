# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Image operations for Mandelbrot rendering.

For info on the PNG format and metadata handling, see:
https://pillow.readthedocs.io/en/stable/PIL.html#PIL.PngImagePlugin.PngInfo
"""

from __future__ import annotations

import array
import base64
import bisect
import dataclasses
import enum
import io
import json
import logging
import math
import pathlib
import struct
import subprocess  # noqa: S404
import sys
import tempfile
import time
from collections import abc
from typing import cast

import gmpy2
import imageio
import imageio_ffmpeg  # type: ignore
import numpy as np
from PIL import ExifTags, ImageDraw, ImageFont, PngImagePlugin
from PIL import Image as PILImage
from transcrypto.core import hashes
from transcrypto.utils import base as tbase
from transcrypto.utils import timer

from tranzoom import __app__ as _app
from tranzoom.core import frame, palette

# metadata keys for PNG tEXt chunks; used to store the frame parameters and other info in the PNG;
# don't add "version", or "date", or other metadata that can change without changing the
# actual image/mathematical data;
# keys use a "tranZoom:" (_app) namespace to avoid collisions with other metadata
# all are converted to str for storage in PNG metadata, but the original types are indicated below
META_FRACTAL_KEY: str = f'{_app}:frame:fractal'  # str, ex "mandelbrot", one of frame.Fractal
META_TOP_RE_KEY: str = f'{_app}:frame:top_re'  # gmpy2.mpq -> converts to str as quotients
META_TOP_IM_KEY: str = f'{_app}:frame:top_im'  # gmpy2.mpq
META_BOTTOM_RE_KEY: str = f'{_app}:frame:bottom_re'  # gmpy2.mpq
META_BOTTOM_IM_KEY: str = f'{_app}:frame:bottom_im'  # gmpy2.mpq
META_CENTER_RE_KEY: str = f'{_app}:frame:center_re'  # gmpy2.mpq
META_CENTER_IM_KEY: str = f'{_app}:frame:center_im'  # gmpy2.mpq
META_WIDTH_RE_KEY: str = f'{_app}:frame:width_re'  # gmpy2.mpq
META_HEIGHT_IM_KEY: str = f'{_app}:frame:height_im'  # gmpy2.mpq
META_PRECISION_KEY: str = f'{_app}:frame:precision'  # int, in bits
META_MAGNIFICATION_ORDER_KEY: str = f'{_app}:frame:magnification_order'  # float
META_FRAME_HASH_KEY: str = f'{_app}:frame:hash'  # str, like "abcdef1234567890", a SHA256
META_COMPUTATION_WIDTH_KEY: str = f'{_app}:computation:width'  # int, in pixels
META_COMPUTATION_HEIGHT_KEY: str = f'{_app}:computation:height'  # int, in pixels
META_COMPUTATION_SEARCH_DEPTH_KEY: str = f'{_app}:computation:depth'  # int
META_COMPUTATION_COLOR_SET_KEY: str = f'{_app}:computation:color_set'  # SetHighlightAlgo./"none"
META_COMPUTATION_HASH_KEY: str = f'{_app}:computation:hash'  # str, like "abcdef1234567890" a SHA256
META_RENDER_PALETTE_KEY: str = f'{_app}:render:palette'  # str, ex "sunset", one of palette.Palette
META_RENDER_SET_PALETTE_KEY: str = f'{_app}:render:set_palette'  # str, interior Set palette name
META_RENDER_OVERLAY_KEY: str = f'{_app}:render:overlay'  # image.OverlayType or "none"
META_RENDER_MARK_RE_KEY: str = f'{_app}:render:mark_re'  # gmpy2.mpq
META_RENDER_MARK_IM_KEY: str = f'{_app}:render:mark_im'  # gmpy2.mpq
META_RENDER_MARK_COLOR_KEY: str = f'{_app}:render:mark_color'  # Color.name.lower() / "none"=no mark
META_RENDER_MARK_WIDTH_KEY: str = f'{_app}:render:mark_width'  # int
META_RENDER_HASH_KEY: str = f'{_app}:render:hash'  # str, like "abcdef1234567890", a SHA256
META_IMAGE_ANIMATION_KEY: str = f'{_app}:image:animation'  # AnimationType or "none" if static image
META_IMAGE_HASH_KEY: str = f'{_app}:image:hash'  # str, like "abcdef1234567890", a SHA256
META_IMAGE_EXT_COUNT_KEY: str = f'{_app}:image:exterior:count'  # int; count escaped
META_IMAGE_EXT_N_MIN_KEY: str = f'{_app}:image:exterior:n:min'  # int; min iter
META_IMAGE_EXT_N_MAX_KEY: str = f'{_app}:image:exterior:n:max'  # int; max iter
META_IMAGE_EXT_NU_MIN_KEY: str = f'{_app}:image:exterior:nu:min'  # float
META_IMAGE_EXT_NU_MAX_KEY: str = f'{_app}:image:exterior:nu:max'  # float
META_IMAGE_EXT_BUCKET_MIN_KEY: str = f'{_app}:image:exterior:bucket:min'  # int
META_IMAGE_EXT_BUCKET_MAX_KEY: str = f'{_app}:image:exterior:bucket:max'  # int
META_IMAGE_SET_COUNT_KEY: str = f'{_app}:image:set:count'  # int; count interior
META_IMAGE_SET_N_MIN_KEY: str = f'{_app}:image:set:n:min'  # int; min iter
META_IMAGE_SET_N_MAX_KEY: str = f'{_app}:image:set:n:max'  # int; max iter
META_IMAGE_SET_NU_MIN_KEY: str = f'{_app}:image:set:nu:min'  # float
META_IMAGE_SET_NU_MAX_KEY: str = f'{_app}:image:set:nu:max'  # float
META_IMAGE_SET_BUCKET_MIN_KEY: str = f'{_app}:image:set:bucket:min'  # int
META_IMAGE_SET_BUCKET_MAX_KEY: str = f'{_app}:image:set:bucket:max'  # int
META_IMAGE_STATS_MAX_LO_KEY: str = f'{_app}:image:stats:max_lo'  # gmpy2.mpfr
META_IMAGE_STATS_MAX_HI_KEY: str = f'{_app}:image:stats:max_hi'  # gmpy2.mpfr
META_IMAGE_STATS_MIN_LO_KEY: str = f'{_app}:image:stats:min_lo'  # gmpy2.mpfr
META_IMAGE_STATS_MIN_HI_KEY: str = f'{_app}:image:stats:min_hi'  # gmpy2.mpfr
META_IMAGE_STATS_ANG_LO_KEY: str = f'{_app}:image:stats:ang_lo'  # gmpy2.mpfr
META_IMAGE_STATS_ANG_HI_KEY: str = f'{_app}:image:stats:ang_hi'  # gmpy2.mpfr
META_IMAGE_STATS_IMAG_LO_KEY: str = f'{_app}:image:stats:imag_lo'  # gmpy2.mpfr
META_IMAGE_STATS_IMAG_HI_KEY: str = f'{_app}:image:stats:imag_hi'  # gmpy2.mpfr
# extra keys added to some images only
# images with exterior points (almost all!)
META_IMAGE_EXT_HISTOGRAM_LINEAR_KEY: str = f'{_app}:image:exterior:hist:linear'  # str
META_IMAGE_EXT_HISTOGRAM_LINEAR_CUM_KEY: str = f'{_app}:image:exterior:hist:linear:cumulative'
META_IMAGE_EXT_HISTOGRAM_BUCKET_KEY: str = f'{_app}:image:exterior:hist:bucket'  # str
META_IMAGE_EXT_HISTOGRAM_BUCKET_CUM_KEY: str = f'{_app}:image:exterior:hist:bucket:cumulative'
# images with interior points and a Set palette (so we have interior histograms)
META_IMAGE_SET_HISTOGRAM_LINEAR_KEY: str = f'{_app}:image:set:hist:linear'  # str
META_IMAGE_SET_HISTOGRAM_LINEAR_CUM_KEY: str = f'{_app}:image:set:hist:linear:cumulative'  # str
META_IMAGE_SET_HISTOGRAM_BUCKET_KEY: str = f'{_app}:image:set:hist:bucket'  # str
META_IMAGE_SET_HISTOGRAM_BUCKET_CUM_KEY: str = f'{_app}:image:set:hist:bucket:cumulative'  # str
# Julia extra keys
META_JULIA_RE_KEY: str = f'{_app}:frame:julia_re'  # gmpy2.mpq, only added for Julia Set frames
META_JULIA_IM_KEY: str = f'{_app}:frame:julia_im'  # gmpy2.mpq, only added for Julia Set frames
# Zoom extra keys
META_ZOOM_TYPE_KEY: str = f'{_app}:zoom:type'  # one of AnimationType (ex: 'gif')
META_ZOOM_INITIAL_WIDTH_RE_KEY: str = f'{_app}:zoom:frame:initial:width_re'  # gmpy2.mpq
META_ZOOM_INITIAL_HEIGHT_IM_KEY: str = f'{_app}:zoom:frame:initial:height_im'  # gmpy2.mpq
META_ZOOM_MAGNITUDE_KEY: str = f'{_app}:zoom:frame:magnitude'  # gmpy2.mpq
META_ZOOM_FRAMES_KEY: str = f'{_app}:zoom:frame:frames'  # int
META_ZOOM_SECONDS_KEY: str = f'{_app}:zoom:frame:seconds'  # gmpy2.mpq
META_ZOOM_LOOP_KEY: str = f'{_app}:zoom:frame:loop'  # int; 0 means inf loop; meaningless for MP4
META_ZOOM_STEPS_KEY: str = f'{_app}:zoom:frame:steps'  # int
META_ZOOM_FPS_KEY: str = f'{_app}:zoom:frame:fps'  # gmpy2.mpq
META_ZOOM_MAGNITUDE_PER_STEP_KEY: str = f'{_app}:zoom:frame:magnitude_per_step'  # gmpy2.mpq
META_ZOOM_MAGNIFICATION_PER_STEP_KEY: str = f'{_app}:zoom:frame:magnification_per_step'  # gmpy2.mpq
META_ZOOM_MARKER_INDEX_LIST_KEY: str = f'{_app}:zoom:marker:index'  # list[int]
META_ZOOM_DEPTH_FRAMES_LIST_KEY: str = f'{_app}:zoom:depth:frames'  # list[tuple[int, int, int]]]
META_ZOOM_HASH_KEY: str = f'{_app}:zoom:hash'  # str, like "abcdef1234567890", a SHA256
# LLM extra keys
META_LLM_MODEL_KEY: str = f'{_app}:llm:model'  # str (META_LLM_MODEL_VALUE_HUMAN or "HUMAN")
META_LLM_TEMPERATURE_KEY: str = f'{_app}:llm:temperature'  # float
META_LLM_SEED_KEY: str = f'{_app}:llm:seed'  # int (0 if not set)
META_LLM_QUERY_MEMORY_KEY: str = f'{_app}:llm:query:memory'  # int; number of previous steps chat
META_LLM_QUERY_REASONING_KEY: str = f'{_app}:llm:query:reasoning'  # bool; stored as "true"/"false"
META_LLM_QUERY_SETUP_KEY: str = f'{_app}:llm:query:setup'  # str
META_LLM_QUERY_IMAGE_KEY: str = f'{_app}:llm:query:image'  # str
META_LLM_QUERY_EXTRA_KEY: str = f'{_app}:llm:query:extra'  # str
META_LLM_RESULT_JSON_KEY: str = f'{_app}:llm:result:json'  # JSON with evaluation inf from LLM/HUMAN
META_LLM_ZOOM_COUNT_KEY: str = f'{_app}:llm:zoom:count'  # int; zoom iteration depth
# special values
META_LLM_MODEL_VALUE_HUMAN: str = 'HUMAN'  # used if evaluation is done by flesh-and-blood human

# these hashes are relatively safe to leave in a private image (`tranz config clean` command),
# they would have to be brute-forced, and for any non-trivial Frame/zoom will be nigh impossible
META_SAFE_HASHES: set[str] = {
  META_FRAME_HASH_KEY,  # this depends on coordinates, hard for any non-trivial Frame
  META_COMPUTATION_HASH_KEY,  # this depends on coordinates, hard for any non-trivial Frame
  META_ZOOM_HASH_KEY,  # this depends on coordinates, hard for any non-trivial Frame
  META_RENDER_HASH_KEY,  # this is easy to brute-force, but it's only the render parameters, useless
  META_IMAGE_HASH_KEY,  # this is a data-driven hash (depends on rendered bytes) and is 100% safe
}

# pre-compiled constants for encoding/decoding
_PACK_IF = struct.Struct('>if')  # signed int32 + float32
_PACK_Q = struct.Struct('>Q')  # uint64

# image constants

type ImageUInt64Array = array.array[int]  # type alias for the type of our pixel data array
_HIST_SUB_BINS: int = 2048  # number of sub-bins to use for the smooth histogram keys

# constants for drawing

_ALMOST_ONE: float = math.nextafter(1.0, 0.0)
_SQRT_TWO: float = math.sqrt(2)
_LINE_WIDTH_RATIO: int = 150  # line width will be max(1, sz//_LINE_WIDTH_RATIO) of the image width
_CIRCLE_RADIUS: int = 20
_LABEL_OFFSET: int = 5
# scale factor for converting stored Set interior integers back to |z| float magnitudes;
# interior points are stored as -(int(floor(scale * |z|)) + 1), with scale = RES / MAX_Z = RES / 2


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
JPEG_QUALITY: int = 95  # quality for JPEG output; ignored for PNG which is lossless

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

MAX_ZOOM_MAGNITUDE_10: float = 10000.0  # this is 10**10000 which is more than enough
DEFAULT_DEST_MAGNITUDE_10: str = '1'  # default dest magnification for zooms 10**1 = 10x zoom
DEFAULT_LOOP: int = 0  # 0 means infinite loop for GIFs
THRESHOLD_JUMPY_ZOOM_PER_FRAME: float = 1.25  # if zoom per frame is above this warn about jumpiness
MAX_TOLERATED_FRAME_MAG_ERROR: float = 0.0002  # 0.02% - max error Frame vs. reduced mpq Frame
MAX_TOLERATED_TOTAL_MAG_ERROR: float = 0.001  # 0.1% - max total cumulative error of total zoom
MAGNITUDE_PER_FRAME_MARKER: gmpy2.mpq = gmpy2.mpq('13/14')  # ~8.5x zoom/marker (10**(13/14)=8.483)
MAGNITUDE_PER_DEPTH_MARKER: gmpy2.mpq = gmpy2.mpq('3/10')  # ~2x zoom/frame (10**(3/10)=1.995)
MAX_TOLERATED_MARKER_MAG_ERROR: float = 0.15  # 15% max error for marker frames


# gmpy2.mpfr constants
_MPFR_ZERO: gmpy2.mpfr = gmpy2.mpfr('0')
_MPFR_ONE: gmpy2.mpfr = gmpy2.mpfr('1')
_MPFR_FOUR: gmpy2.mpfr = gmpy2.mpfr('4')

# gmpy2.mpq constants
_MPQ_ZERO: gmpy2.mpq = gmpy2.mpq('0')
_MPQ_VIDEO_DURATION_STORE_SCALE: gmpy2.mpq = gmpy2.mpq(str(VIDEO_DURATION_STORE_SCALE))


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class FractalStats(frame.SerializingFractalObject):
  """Defines Mandelbrot stats values, collected over the sample run.

  Attributes:
    n_px (int): Total number of pixels in the image.
    n_interior (int): Number of interior (Set) points in the image; pixels with escape
        iteration < 0.
    max_lo (gmpy2.mpfr): min(all max(|z|)) for interior points; lower bound of the max |z|
        magnitudes.
    max_hi (gmpy2.mpfr): max(all max(|z|)) for interior points; upper bound of the max |z|
        magnitudes.
    min_lo (gmpy2.mpfr): min(all min(|z|)) for interior points; lower bound of the min |z|
        magnitudes.
    min_hi (gmpy2.mpfr): max(all min(|z|)) for interior points; upper bound of the min |z|
        magnitudes.
    ang_lo (gmpy2.mpfr): Minimum angle for interior (Set) points, in [0, 1].
    ang_hi (gmpy2.mpfr): Maximum angle for interior (Set) points, in [0, 1].
    imag_lo (gmpy2.mpfr): Minimum imaginary weight average for interior (Set) points, in [0, 1].
    imag_hi (gmpy2.mpfr): Maximum imaginary weight average for interior (Set) points, in [0, 1].

  """

  # these 2 stats are always collected
  n_px: int  # total number of pixels in the image
  n_interior: int  # number of interior (Set) points in the image, pixels with escape iteration < 0

  # limits of |z| magnitudes for interior (Set) points
  max_lo: gmpy2.mpfr | None  # min(all max(|z|) for interior points)
  max_hi: gmpy2.mpfr | None  # max(all max(|z|) for interior points)
  min_lo: gmpy2.mpfr | None  # min(all min(|z|) for interior points)
  min_hi: gmpy2.mpfr | None  # max(all min(|z|) for interior points)

  # limits of angles for interior (Set) points, in [0, 1]
  ang_lo: gmpy2.mpfr | None  # min(all angles for interior points)
  ang_hi: gmpy2.mpfr | None  # max(all angles for interior points)

  # limits of the Imaginary Weight Average for interior (Set) points, in [0, 1]
  imag_lo: gmpy2.mpfr | None  # min(all sac values for interior points)
  imag_hi: gmpy2.mpfr | None  # max(all sac values for interior points)

  def __post_init__(self) -> None:  # noqa: C901
    """Check FractalStats validity.

    Raises:
      Error: if the object is invalid.

    """
    # check n_px and n_interior are valid
    if not (frame.MIN_IMAGE_PX <= self.n_px <= frame.MAX_IMAGE_PX):
      raise Error(
        f'Invalid {self.n_px=}, must be between {frame.MIN_IMAGE_PX} and {frame.MAX_IMAGE_PX}'
      )
    if not (0 <= self.n_interior <= self.n_px):
      raise Error(f'Invalid {self.n_interior=}, must be between 0 and {self.n_px}')
    # check max/min_lo/hi are valid: they must be both None or both not None
    if (self.max_lo is None) != (self.max_hi is None):
      raise Error(
        f'max_lo and max_hi must both be None or both be not None: {self.max_lo=}, {self.max_hi=}'
      )
    if (
      self.max_lo is not None
      and self.max_hi is not None
      and not (_MPFR_ZERO <= self.max_lo <= self.max_hi)
    ):
      raise Error(f'Invalid {self.max_lo=} and {self.max_hi=}, must satisfy 0 <= max_lo <= max_hi')
    if (self.min_lo is None) != (self.min_hi is None):
      raise Error(
        f'min_lo and min_hi must both be None or both be not None: {self.min_lo=}, {self.min_hi=}'
      )
    if (
      self.min_lo is not None
      and self.min_hi is not None
      and not (_MPFR_ZERO <= self.min_lo <= self.min_hi)
    ):
      raise Error(f'Invalid {self.min_lo=} and {self.min_hi=}, must satisfy 0 <= min_lo <= min_hi')
    # check ang_lo/hi are valid: they must be both None or both not None
    if (self.ang_lo is None) != (self.ang_hi is None):
      raise Error(
        f'ang_lo and ang_hi must both be None or both be not None: {self.ang_lo=}, {self.ang_hi=}'
      )
    if (
      self.ang_lo is not None
      and self.ang_hi is not None
      and not (_MPFR_ZERO <= self.ang_lo <= self.ang_hi <= _MPFR_ONE)
    ):
      raise Error(
        f'Invalid {self.ang_lo=} and {self.ang_hi=}, must satisfy 0 <= ang_lo <= ang_hi <= 1'
      )
    # check imag_lo/hi are valid: they must be both None or both not None
    if (self.imag_lo is None) != (self.imag_hi is None):
      raise Error(
        f'imag_lo and imag_hi must both be None or both be not None:'
        f' {self.imag_lo=}, {self.imag_hi=}'
      )
    if (
      self.imag_lo is not None
      and self.imag_hi is not None
      and not (_MPFR_ZERO <= self.imag_lo <= self.imag_hi <= _MPFR_ONE)
    ):
      raise Error(
        f'Invalid {self.imag_lo=} and {self.imag_hi=}, must satisfy 0 <= imag_lo <= imag_hi <= 1'
      )

  def __str__(self) -> str:
    """Get string representation of the FractalStats.

    Returns:
      str: String representation of the FractalStats.

    """
    return (
      f'FractalStats(n_px={self.n_px}, n_interior={self.n_interior}, '
      f'max_lo={self.max_lo}, max_hi={self.max_hi}, min_lo={self.min_lo}, min_hi={self.min_hi}, '
      f'ang_lo={self.ang_lo}, ang_hi={self.ang_hi}, imag_lo={self.imag_lo}, imag_hi={self.imag_hi})'
    )

  @property
  def json(self) -> tbase.JSONDict:
    """Get a JSON-serializable dictionary representation of the FractalStats.

    Keys:

    Returns:
      tbase.JSONDict: A dictionary representation of the FractalStats.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'n_px': self.n_px,
      'n_interior': self.n_interior,
      'max_lo': str(self.max_lo) if self.max_lo is not None else None,
      'max_hi': str(self.max_hi) if self.max_hi is not None else None,
      'min_lo': str(self.min_lo) if self.min_lo is not None else None,
      'min_hi': str(self.min_hi) if self.min_hi is not None else None,
      'ang_lo': str(self.ang_lo) if self.ang_lo is not None else None,
      'ang_hi': str(self.ang_hi) if self.ang_hi is not None else None,
      'imag_lo': str(self.imag_lo) if self.imag_lo is not None else None,
      'imag_hi': str(self.imag_hi) if self.imag_hi is not None else None,
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> FractalStats:
    """Create a FractalStats object from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from Frame.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the frame. If the
          calculated hash does not match, an error is raised.

    Returns:
      FractalStats: A FractalStats object

    Raises:
      Error: on error

    """
    # create the object
    try:
      params = FractalStats(  # object creation will check the data is valid and consistent
        n_px=int(str(data['n_px'])),
        n_interior=int(str(data['n_interior'])),
        max_lo=gmpy2.mpfr(str(data['max_lo'])) if data['max_lo'] is not None else None,
        max_hi=gmpy2.mpfr(str(data['max_hi'])) if data['max_hi'] is not None else None,
        min_lo=gmpy2.mpfr(str(data['min_lo'])) if data['min_lo'] is not None else None,
        min_hi=gmpy2.mpfr(str(data['min_hi'])) if data['min_hi'] is not None else None,
        ang_lo=gmpy2.mpfr(str(data['ang_lo'])) if data['ang_lo'] is not None else None,
        ang_hi=gmpy2.mpfr(str(data['ang_hi'])) if data['ang_hi'] is not None else None,
        imag_lo=gmpy2.mpfr(str(data['imag_lo'])) if data['imag_lo'] is not None else None,
        imag_hi=gmpy2.mpfr(str(data['imag_hi'])) if data['imag_hi'] is not None else None,
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid FractalStats JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'FractalStats {params.sha!r} does not match expected {check_hash!r}')
    return params


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ImageOutputConfig:
  """Groups all parameters that control how output images are named and saved on disk.

  This is a runtime-only config object — not part of the mathematical/DB representation.
  It is NOT a SerializingFractalObject: it carries no mathematical meaning and is never hashed.

  Attributes:
    path (pathlib.Path | None): Output directory; None means the current working directory.
    use_date (bool): If True, a YYYYMMDDhhmmss timestamp is included in the file name.
    use_hash (bool): If True, the content hash is included in the file name.
    prefix (str): File name prefix, e.g., 'mandel' or 'julia'.

  """

  path: pathlib.Path | None  # output directory; None means current working directory
  use_date: bool  # if True, include YYYYMMDDhhmmss in the file name
  use_hash: bool  # if True, include the content hash in the file name
  prefix: str  # file name prefix, e.g., "mandel" or "julia"


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class RenderParameters(frame.SerializingFractalObject):
  """Defines a transformation from math to image.

  ATTENTION: changing any attribute changes the object SHA-256 hash.

  Attributes:
    tp (FileType): Output file type; default is FileType.PNG.
    escaped_pal (palette.Palette): Color palette for escaped (exterior) points;
        default is palette.DEFAULT_PALETTE.
    set_pal (palette.Palette | None): Color palette for interior Set points; None means no
        Set palette (requires a non-Set computation); default is None.
    mark_re (gmpy2.mpq): Real part of the optional crosshair mark coordinate;
        default is 0; unused when mark_color is None.
    mark_im (gmpy2.mpq): Imaginary part of the optional crosshair mark coordinate;
        default is 0; unused when mark_color is None.
    mark_color (Color | None): Color of the crosshair mark overlay; None means no mark is
        drawn; default is None.
    mark_width (int): Crosshair mark line width in pixels; default is DEFAULT_MARK_WIDTH.
    overlay (OverlayType | None): Optional numbered sector grid overlay; None means no
        overlay; default is None.

  """

  # ATTENTION: changing anything here changes the HASH!!
  tp: FileType = FileType.PNG
  escaped_pal: palette.Palette = palette.DEFAULT_PALETTE
  set_pal: palette.Palette | None = None  # if None, this must be a non-Set-computation
  mark_re: gmpy2.mpq = _MPQ_ZERO
  mark_im: gmpy2.mpq = _MPQ_ZERO
  mark_color: Color | None = None  # if None, no mark will be drawn
  mark_width: int = DEFAULT_MARK_WIDTH
  overlay: OverlayType | None = None  # overlay is independent of mark!
  prev_marker: frame.Frame | None = None  # for zoom
  next_marker: frame.Frame | None = None  # for zoom

  def __post_init__(self) -> None:  # noqa: C901, PLR0912
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
    # check prev/next markers are valid if provided
    if not self.prev_marker and self.next_marker:
      raise Error('next_marker provided without prev_marker')
    if self.prev_marker and not self.next_marker:
      raise Error('prev_marker provided without next_marker')
    if (
      self.prev_marker
      and self.next_marker
      and (self.prev_marker.fractal != self.next_marker.fractal)
    ):
      raise Error('prev/next_marker fractal types do not match')

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
    markers: str = (
      ''
      if self.prev_marker is None or self.next_marker is None
      else f' + [P:{self.prev_marker.sha[:10]}, N:{self.next_marker.sha[:10]}]'
    )
    return (
      '{'
      f'[{self.tp.name.upper()}, {self.escaped_pal.name}, '
      f'{self.set_pal.name if self.set_pal else "none"}]{mark}{overlay}{markers}'
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
      'prev_marker': self.prev_marker.json if self.prev_marker else None,
      'next_marker': self.next_marker.json if self.next_marker else None,
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
        prev_marker=frame.Frame.FromJson(cast('tbase.JSONDict', data['prev_marker']))
        if data['prev_marker']
        else None,
        next_marker=frame.Frame.FromJson(cast('tbase.JSONDict', data['next_marker']))
        if data['next_marker']
        else None,
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid RenderParameters JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'RenderParameters {params.sha!r} does not match expected {check_hash!r}')
    return params


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ZoomParameters(frame.SerializingFractalObject):
  """Defines the zoom parameters for video planning and rendering.

  ATTENTION: changing any attribute changes the object SHA-256 hash.

  Attributes:
    tp (AnimationType): The animation output type ('gif' or 'mp4').
    img (frame.ComputationParameters): The initial frame computation parameters; the same
        parameters are used for all frames in the animation.
    render (RenderParameters): The render parameters applied to all frames in the animation.
    mag (gmpy2.mpq): The destination magnification (as a log10 magnitude order).
    n_frames (int): The total number of frames in the animation.
    duration (int): The animation duration stored as
        round(seconds * VIDEO_DURATION_STORE_SCALE), to avoid float precision issues.
    loop (int): Number of loops for GIF animations; 0 means infinite loop;
        ignored for non-GIF types; default is 0.

  """

  # ATTENTION: changing anything here changes the HASH!!
  tp: AnimationType  # 'gif' or 'mp4'
  img: frame.ComputationParameters  # INITIAL frame; one computation parameters for all images
  render: RenderParameters  # one render parameters for all images
  mag: gmpy2.mpq  # destination magnitude
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
    # check magnitude is valid
    if not (-MAX_ZOOM_MAGNITUDE_10 <= self.mag <= MAX_ZOOM_MAGNITUDE_10):
      raise Error(f'Magnitude abs() must be <= {MAX_ZOOM_MAGNITUDE_10}, got {self.mag}')
    if self.mag == _MPQ_ZERO:
      raise Error('Magnitude cannot be zero')
    # check number of frames is valid
    if not (MIN_FRAMES <= self.n_frames <= MAX_FRAMES) or self.n_steps <= 1:
      raise Error(
        f'Number of frames must be between {MIN_FRAMES} and {MAX_FRAMES}, got {self.n_frames}'
      )
    # check duration is valid
    if not (MIN_DURATION <= self.n_seconds <= MAX_DURATION):
      raise Error(
        f'Duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {self.n_seconds}'
      )
    # check fps is valid: we already validated n_frames and duration that are used to compute fps
    if not (MIN_FPS <= self.fps <= MAX_FPS):
      raise Error(f'Frames per second must be between {MIN_FPS} and {MAX_FPS}, got {self.fps}')
    # check loop count is valid for GIFs
    if self.tp == AnimationType.GIF and not (MIN_LOOP <= self.loop <= MAX_LOOP):
      raise Error(f'Loop count for GIFs must be between {MIN_LOOP} and {MAX_LOOP}, got {self.loop}')
    if self.tp != AnimationType.GIF and self.loop != 0:
      raise Error(f'Loop count is only applicable for GIFs, got {self.loop} for {self.tp}')

  def __str__(self) -> str:
    """Get string representation of the ZoomParameters.

    Format is:
      "<[ANIMATION_TYPE]: [RENDER_PARAMETERS] -> [COMPUTATION_PARAMETERS] / "
      "(mag:[MAGNIFICATION], n:[N_FRAMES], d:[DURATION(sec)], fps:[FPS], l:[LOOP])>"

    Returns:
      str: String representation of the ZoomParameters.

    """
    return (
      f'<{self.tp.name.upper()}: {self.img} -> {self.render} / '
      f'(mag:{self.mag}, n:{self.n_frames}, d:{self.n_seconds}, fps:{self.fps}, l:{self.loop})>'
    )

  @property
  def n_steps(self) -> int:
    """Zoom steps (always one less than the number of frames). Exact.

    Returns:
      int: The number of zoom steps.

    """
    return self.n_frames - 1  # steps is one less than frames

  @property
  def n_seconds(self) -> gmpy2.mpq:
    """Get duration, in seconds. Exactly consistent, but within ~1/VIDEO_DURATION_STORE_SCALE.

    Returns:
      gmpy2.mpq: The video duration in seconds.

    """
    return gmpy2.mpq(self.duration) / _MPQ_VIDEO_DURATION_STORE_SCALE

  @property
  def fps(self) -> gmpy2.mpq:
    """Get the frames per second for this animation, calculated from n_frames and duration. Exact.

    Returns:
      gmpy2.mpq: The frames per second for this animation.

    """
    return gmpy2.mpq(self.n_frames) / self.n_seconds

  @property
  def mag_per_step(self) -> gmpy2.mpq:
    """Get the magnification per step for this animation. Exact.

    Returns:
      gmpy2.mpq: The magnification per step for this animation.

    """
    return self.mag / gmpy2.mpq(self.n_steps)

  @property
  def scalar_magnification(self) -> gmpy2.mpfr:
    """Get the scalar magnification for the whole zoom. Ultra-precision, but not exact.

    Returns:
      gmpy2.mpfr: The scalar magnification for the whole zoom.

    """
    with frame.PrecisionContext():
      return gmpy2.exp10(self.mag)

  @property
  def scalar_magnification_per_step(self) -> gmpy2.mpq:
    """Get the scalar magnification per step for this animation. Good precision, but not exact.

    Returns:
      gmpy2.mpq: The scalar magnification per step for this animation.

    """
    m: gmpy2.mpfr = gmpy2.exp10(self.mag_per_step)  # mpq -> mpfr -> mpq unavoidable, unfortunately
    return gmpy2.mpq(m)

  @property
  def data_sz_bytes(self) -> int:
    """Estimate the total RAM in bytes needed to hold all animation frames simultaneously.

    All n_frames Image objects are held with histograms (needed for FrameColorNorm during
    animation rendering), sharing the same escape_sz and hist_sz (width, height, and depth
    are constant), so those components scale linearly.  Only the FractalStats component
    grows with precision, which increases by ~ceil(mag * log2(10)) bits from the initial
    to the final frame as the zoom deepens.

    To avoid underestimating, the stats component uses the average precision over the
    animation, linearly interpolated between precision_initial and precision_final:
      stats_sz_delta = 8 * (mpfr_sz_avg - mpfr_sz_initial)  extra bytes per frame

    Uses img.mem_sz_bytes (with histograms) because frames need histograms for coloring.
    For the per-frame on-disk size (no histograms), see img.disk_sz_bytes.

    Formula:
      n_frames * img.mem_sz_bytes  +  n_frames * stats_sz_delta

    Returns:
      int: Estimated bytes to hold all n_frames Image objects simultaneously in RAM.

    """
    # all frames share the same escape_sz and hist_sz (same width/height/depth every frame);
    # only the FractalStats size (stats_sz) depends on precision, which grows as the zoom
    # deepens: precision grows ~ceil(mag * log2(10)) bits from initial to final frame;
    # the stats_sz contribution is tiny vs escape+hist but we properly interpolate
    # using the average precision over the animation
    precision_initial: int = self.img.precision
    # log2(10) ~= 3.32193; ceil(mag * log2(10)) gives extra bits needed for final frame
    precision_delta: int = math.ceil(float(self.mag) * math.log2(10))
    # clamp to valid range: 140 = _MPFR_MIN_PRECISION, 300_000 = _MPFR_MAX_PRECISION
    precision_final: int = max(140, min(precision_initial + precision_delta, 300_000))
    precision_avg: int = (precision_initial + precision_final) // 2
    # stats_sz = 2*28B (Python ints) + 8 gmpy2.mpfr fields; mpfr at p bits: 56B + ceil(p/64)*8B
    mpfr_sz_initial: int = 56 + ((precision_initial + 63) // 64) * 8
    mpfr_sz_avg: int = 56 + ((precision_avg + 63) // 64) * 8
    stats_sz_delta: int = 8 * (mpfr_sz_avg - mpfr_sz_initial)  # per-frame gain vs initial
    return self.n_frames * self.img.mem_sz_bytes + self.n_frames * stats_sz_delta

  @property
  def comp_memory_sz_bytes(self) -> int:
    """Estimate the peak RAM in bytes needed to render the full zoom animation.

    Combines all-frames-in-memory storage (data_sz_bytes, with histograms) with the
    parallel render overhead at the deepest (highest-precision) frame -- the worst case
    for mpfr object sizes.  Peak precision is max(precision_initial, precision_final),
    accounting for both forward and reverse zooms.

    Each of the up to 16 parallel processes (frame.MAX_CONCURRENCE) holds at peak
    during computation (no histograms yet -- histograms are rebuilt after computation):
    - One Image per process (escape array + stats = img.disk_sz_bytes).
    - ~25 scalar gmpy2.mpfr working variables.
    - One gmpy2.mpfr per image column (the xs pre-computation array).

    Formula:
      data_sz_bytes  +  max_concurrence * (img.disk_sz_bytes + (width + 25) * mpfr_sz_peak)

    Returns:
      int: Estimated peak bytes in RAM at the most memory-intensive point of the render.

    """
    # precision grows from initial to final frame as the zoom deepens (or decreases for neg mag);
    # log2(10) ~= 3.32193; ceil(mag * log2(10)) gives extra bits needed for the final frame
    precision_initial: int = self.img.precision
    precision_delta: int = math.ceil(float(self.mag) * math.log2(10))
    # clamp to valid range: 140 = _MPFR_MIN_PRECISION, 300_000 = _MPFR_MAX_PRECISION
    precision_final: int = max(140, min(precision_initial + precision_delta, 300_000))
    precision_peak: int = max(precision_initial, precision_final)  # worst case: deepest init./final
    # peak computation occurs at the deepest (highest-precision) frame; each of the
    # max_concurrence parallel processes holds one Image with escape array + stats but NO
    # histograms (histograms are rebuilt after parallel computation completes) = disk_sz_bytes;
    # mpfr field at p bits: 56B struct overhead + ceil(p/64)*8B mantissa limbs;
    # n_working_mpfr ~25 scalar vars + one column pre-computation (width mpfr values)
    n_working_mpfr: int = 25  # same as in frame.ComputationParameters.comp_memory_sz_bytes
    mpfr_sz_peak: int = 56 + ((precision_peak + 63) // 64) * 8
    per_proc_mpfr_sz_peak: int = (self.img.width + n_working_mpfr) * mpfr_sz_peak
    # peak = all frames in RAM (with histograms) + single-frame computation cost (no histograms)
    return self.data_sz_bytes + frame.MAX_CONCURRENCE * (
      self.img.disk_sz_bytes + per_proc_mpfr_sz_peak
    )

  def animation_sz_bytes(self) -> tuple[int, int]:
    """Estimate the on-disk size in bytes of the output GIF and MP4 animation files.

    Both formats benefit enormously from the high temporal coherence of fractal zoom
    animations -- each frame is a slightly zoomed version of the previous -- which
    inter-frame prediction (H.264) and delta-transparency encoding (GIF) exploit well.

    Empirical per-format estimates (bytes per pixel per frame):
      GIF  (PIL optimize=True, 256-color palette, LZW):  n_frames * n_px / 8   (~8:1)
      MP4  (H.264 CRF=16, preset=slow):                  n_frames * n_px / 20  (~20:1)

    Metadata cost is ONE JSON block per output file (not per frame), written as a GIF
    comment extension or MP4 container tag; the dominant variable cost is the initial
    frame's 8 mpq coordinate strings (~precision_initial * log10(2) digits each):
      meta_sz = 5000 + 8 * 2 * (precision_initial * 3 // 10 + 1)  bytes

    Returns:
      tuple[int, int]: Estimated file sizes as (gif_bytes, mp4_bytes).

    """
    n_px: int = self.img.width * self.img.height
    # GIF: each frame stored as 256-color palette (8-bit) + LZW compression; PIL saves with
    # optimize=True and delta-encodes unchanged pixels as transparent (disposal=1); for fractal
    # frames the smooth gradient interiors map well to 256-color palettes and LZW achieves
    # moderate compression; empirically ~0.125 bytes/pixel/frame on average (8:1 vs uncompressed)
    gif_sz: int = self.n_frames * n_px // 8
    # MP4: H.264 (libx264) at CRF=16 (high quality, ~2x the bits of CRF=23), preset=slow
    # (WriteVideoMP4 parameters); fractal zooms have high temporal coherence (each frame is a
    # slightly zoomed version of the previous) which H.264 inter-frame prediction exploits very
    # well; empirically ~0.05 bytes/pixel/frame on average (20:1 vs uncompressed RGB)
    mp4_sz: int = self.n_frames * n_px // 20
    # metadata: ONE JSON block per file (NOT per frame) written as the GIF comment extension
    # or the MP4 container comment tag (json.dumps(meta) in WriteAnimatedGIF/WriteVideoMP4);
    # contains all zoom/computation/render/frame parameters; see png_sz_bytes formula;
    # dominant variable cost: INITIAL FRAME coordinate strings (8 mpq values each stored as
    # "p/q" with ~precision_initial * log10(2) decimal digits per numerator and denominator);
    # 8 coords * 2 ints * (precision_initial * 3 // 10 + 1) bytes for coordinate strings
    precision_initial: int = self.img.precision
    meta_sz: int = 5000 + 8 * 2 * (precision_initial * 3 // 10 + 1)
    return (gif_sz + meta_sz, mp4_sz + meta_sz)

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

  def Frames(  # noqa: PLR0914
    self,
  ) -> tuple[list[frame.Frame], list[tuple[int, frame.Frame]], list[tuple[int, frame.Frame]]]:
    """Get the Frames. Could be a property, but is a method to remind this is an expensive-ish call.

    Returns:
      tuple[list[frame.Frame], list[tuple[int, frame.Frame]], list[tuple[int, frame.Frame]]]:
          The (frames, marker_frames, depth_frames) for this animation,
          where marker_frames & depth_frames are a strict subset of frames and are lists
          of sorted (index, frame) pairs for frames that were picked

    Raises:
      Error: if the frames cannot be generated within the tolerated error threshold.

    """
    dx: gmpy2.mpq
    dy: gmpy2.mpq
    rdx: gmpy2.mpq
    rdy: gmpy2.mpq
    mpq_mag: gmpy2.mpq = self.scalar_magnification_per_step
    reduced_frm: frame.Frame
    all_frames: list[frame.Frame] = [self.img.frm]  # start with initial frame, keep as-is
    # reproduce the zoom run with full precision
    frm: frame.Frame = self.img.frm
    max_denominator: int
    max_error_dim: gmpy2.mpq = _MPQ_ZERO
    with timer.Timer('frame generation'):
      # float magnification tracking: avoids 30k-bit precision mpfr computation in every loop step;
      # frm.magnification[1] is only used to compute max_denominator for limit_denominator, so
      # a float approximation is precise enough (error is << MAX_TOLERATED_FRAME_MAG_ERROR)
      mag_log10: float = self.img.frm.magnification[1]  # log10 magnification of the initial frame
      mag_step: float = float(self.mag_per_step)  # log10 magnification increment per step
      cur_mag_log10: float  # current step's approximate log10 magnification, updated each iteration
      for i in range(self.n_steps):
        # compute the current expected log10 magnification analytically (cheap float operation)
        cur_mag_log10 = mag_log10 + (i + 1) * mag_step
        # keep frm full precision and iterate
        frm = frame.Frame.FromCenter(
          frm.fractal,
          *frm.center,
          frm.size[0] / mpq_mag,  # these mpq will get HUGE: the reason we keep them in check below
          height=frm.size[1] / mpq_mag,  # these mpq will get HUGE
          point_re=frm.point_re,
          point_im=frm.point_im,
        )
        if i and not i % 10:
          # we have to keep the mpq in check; use precomputed float mag (avoids 30k-bit mpfr call)
          max_denominator = 10_000_000 * (10 ** math.ceil(cur_mag_log10 + 1e-9))
          dx, dy = frm.size  # cache to avoid calling the property twice
          frm = frame.Frame.FromCenter(
            frm.fractal,
            *frm.center,
            dx.limit_denominator(max_denominator=max_denominator),  # type: ignore[attr-defined]
            height=dy.limit_denominator(max_denominator=max_denominator),  # type: ignore[attr-defined]
            point_re=frm.point_re,
            point_im=frm.point_im,
          )
        # make a less aggressive version of the zoom; 1e-9: if the true value is exactly an integer
        # (ex: 5) float accumulation in mag_log10 + (i+1) * mag_step can produce 4.9999999999999982
        # instead, causing math.ceil to return 4 rather than 5, making max_denominator 10x too
        # small, so 1e-9 before ceil means "within a billionth of an integer rounds up to it"
        max_denominator = 10_000 * (10 ** math.ceil(cur_mag_log10 + 1e-9))
        dx, dy = frm.size  # cache once: used for limit_denominator below and error check below
        reduced_frm = frame.Frame.FromCenter(
          frm.fractal,
          *frm.center,
          dx.limit_denominator(max_denominator=max_denominator),  # type: ignore[attr-defined]
          height=dy.limit_denominator(max_denominator=max_denominator),  # type: ignore[attr-defined]
          point_re=frm.point_re,
          point_im=frm.point_im,
        )
        all_frames.append(reduced_frm)
        # test error (dx, dy already cached above)
        rdx, rdy = reduced_frm.size
        error_x: gmpy2.mpq = abs(dx - rdx) / dx
        error_y: gmpy2.mpq = abs(dy - rdy) / dy
        if error_x > MAX_TOLERATED_FRAME_MAG_ERROR or error_y > MAX_TOLERATED_FRAME_MAG_ERROR:
          raise Error(
            f'Frame {i + 2} has size {frm.size} but reduced frame has size {reduced_frm.size}, '
            f'which is {float(gmpy2.mpq(100) * error_x):.6f}% different in width '
            f'and {float(gmpy2.mpq(100) * error_y):.6f}% '
            'different in height, which is above the tolerated error threshold. This is a bug!'
          )
        max_error_dim = max(max_error_dim, error_x, error_y)
    # done adding frames, final check: directly compute the actual magnification achieved
    # to make sure the accumulated error is within the tolerated threshold
    actual_mag: gmpy2.mpfr = cast(
      'gmpy2.mpfr', gmpy2.log10(gmpy2.sqrt(all_frames[-1].mag2 / all_frames[0].mag2))
    )
    if (mag_error := abs(actual_mag - self.mag) / self.mag) > MAX_TOLERATED_TOTAL_MAG_ERROR:
      raise Error(
        'the actual magnification achieved by zooming in the frame is '
        f'{float(actual_mag):.6f}, which is {100.0 * float(mag_error):e}% different '
        f'from the intended {self.mag} ({float(self.mag):.6f}). This means the gmpy2.mpq needs '
        'more precision for conversion. This is a bug!'
      )
    logging.info(
      f'Generated {len(all_frames)} REGULAR Frames for the zoom, '
      f'max frame error {100.0 * float(max_error_dim):e}%, '
      f'final magnification error {100.0 * float(mag_error):e}% '
      f'(actual {float(actual_mag):.6f} vs intended {float(self.mag):.6f})'
    )
    # we finished the frame generation, now we pick them special ones
    return (
      all_frames,
      self._FramesSubset(all_frames, MAGNITUDE_PER_FRAME_MARKER, 'marker'),
      self._FramesSubset(all_frames, MAGNITUDE_PER_DEPTH_MARKER, 'depth'),
    )

  def _FramesSubset(
    self,
    all_frames: list[frame.Frame],
    mag_per_step: gmpy2.mpq,
    name: str,
  ) -> list[tuple[int, frame.Frame]]:
    """Get a subset of frames based on the given magnification step.

    Args:
      all_frames (list[frame.Frame]): The list of all frames generated for the zoom.
      mag_per_step (gmpy2.mpq): The magnification step per frame.
      name (str): The name of the subset, used for logging.

    Returns:
      list[tuple[int, frame.Frame]]: A list of (index, frame) pairs for frames that were picked.

    Raises:
      Error: if the frames cannot be generated within the tolerated error threshold.

    """
    # float magnification tracking: avoids 30k-bit precision mpfr computation in every loop step;
    # frm.magnification[1] is only used to compute max_denominator for limit_denominator, so
    # a float approximation is precise enough (error is << MAX_TOLERATED_FRAME_MAG_ERROR)
    mag_log10: float = self.img.frm.magnification[1]  # log10 magnification of the initial frame
    mag_step: float = float(self.mag_per_step)  # log10 magnification increment per step
    # we don't care about the number of frames, we care about a fixed zoom magnitude
    n_marker_steps: int = int(cast('gmpy2.mpz', max(math.floor(self.mag / mag_per_step), 1)))
    if n_marker_steps <= 1 or self.n_frames < 5:  # noqa: PLR2004
      # if we only have 2 or fewer markers (1 step), just use the first and last frames as
      # markers; same thing for few frames: [1st, X, Y, Z, last] is the smallest degenerate
      # case where it is worth having a "marker", frame Y, and return [1st, Y, last]
      logging.info(f'Frames subset {name!r} is trivial, will use [first, last]')
      return [(0, all_frames[0]), (len(all_frames) - 1, all_frames[-1])]
    # we will need more markers; start from the first and find the "ideal" stops
    with timer.Timer(f'{name} generation'):
      marker_mag: gmpy2.mpq = self.mag / gmpy2.mpq(n_marker_steps)
      marker_mag = gmpy2.mpq(
        gmpy2.exp10(marker_mag)
      )  # mpq -> mpfr -> mpq unavoidable, unfortunately
      # precompute analytical frame magnifications for O(log n) bisect-based marker search;
      # float precision is sufficient since MAX_TOLERATED_MARKER_MAG_ERROR tolerance is 6%
      all_mag_log10: list[float] = [mag_log10 + j * mag_step for j in range(len(all_frames))]
      ideal_marker_mag_log10: float = mag_log10  # tracks the ideal marker magnification
      # log10(exp10(x)) = x exactly, so use the underlying value rather than gmpy2.log10(marker_mag)
      marker_mag_step_log10: float = float(self.mag) / float(n_marker_steps)
      frm: frame.Frame = all_frames[0]  # start with initial frame, keep as-is
      marker_frames: list[tuple[int, frame.Frame]] = [(0, frm)]  # start with the first frame
      last_idx: int = 0
      idx: int
      delta_log10: float
      max_min_mag_float: float = 0.0
      for i in range(n_marker_steps):
        # advance ideal marker magnification analytically (no growing-denominator mpq computation)
        ideal_marker_mag_log10 += marker_mag_step_log10
        # find the actual frame closest to the ideal magnification using O(log n) bisect search
        insert_pos: int = bisect.bisect_left(all_mag_log10, ideal_marker_mag_log10, last_idx)
        if insert_pos >= len(all_frames):
          idx = len(all_frames) - 1
        elif insert_pos == last_idx or abs(
          all_mag_log10[insert_pos] - ideal_marker_mag_log10
        ) <= abs(
          all_mag_log10[insert_pos - 1] - ideal_marker_mag_log10
        ):  # short-circuit: when insert_pos == last_idx, insert_pos-1 is not evaluated
          idx = insert_pos
        else:
          idx = insert_pos - 1
        # track maximum relative error in mag2 space: |f.mag2 - ideal.mag2| / ideal.mag2
        # float equivalent: |10^(2*(f_log10 - ideal_log10)) - 1| (same formula, just in log space)
        delta_log10 = all_mag_log10[idx] - ideal_marker_mag_log10
        max_min_mag_float = max(max_min_mag_float, abs(10.0 ** (2.0 * delta_log10) - 1.0))
        # test that the frames are in the expected order and we are not going backwards
        new_marker: frame.Frame = all_frames[idx]
        if idx == last_idx:
          raise Error(
            f'Frames sub-set {name!r} / {i + 1} is closer to last marker index {last_idx}. Bug!'
          )
        # make sure we don't have duplicates; add it
        if (idx, new_marker) in marker_frames:
          raise Error(f'Duplicate frame found in {name!r} subset; bug! report. Frame: {new_marker}')
        marker_frames.append((idx, new_marker))
        last_idx = idx
    # done; check we arrived at the last frame and error is acceptable; if so, all is good
    if marker_frames[-1] != (len(all_frames) - 1, all_frames[-1]):
      raise Error(
        f'Last frame in {name!r} subset is not the same as the last frame; bug! report. '
        f'Last frame in subset: {marker_frames[-1]}, last frame: {all_frames[-1]}'
      )
    if any(1 for j, f in marker_frames if all_frames[j] != f):
      raise Error(f'Inconsistent hashes in {name!r} sub-set do not match frames list; Report bug!')
    if max_min_mag_float > MAX_TOLERATED_MARKER_MAG_ERROR:
      raise Error(
        f'Frames sub-set {name!r} are not close enough to the ideal frames; bug! report. '
        f'Maximum deviation in mag2 is {100.0 * max_min_mag_float:.6f}%, which is a bug! report'
      )
    logging.info(
      f'Generated {len(marker_frames) - 2} non-trivial {name!r} Frames for the zoom, '
      f'max frame deviation from ideal {100.0 * float(max_min_mag_float):.6f}%'
    )
    return marker_frames


class Image:
  """A fractal image. Encapsulates the image operations.

  Attributes:
    escape (ImageUInt64Array): An array storing the escape data for each pixel;
        this is not the color, but the raw data that will be converted to color later;
        the length of this array is equal to the total number of pixels in the image;
        the pixel at coordinates (x, y) is stored at index (y * width + x) in the array.
    stats (FractalStats | None): Optional stats about the fractal, collected during rendering;
        DO NOT COUNT on this being present unless this was a sample 16.16 render
        (see fractal._FractalAdaptiveIterations) where the stats are collected.
    ext_hist (Image.Histogram | None): Histogram for exterior (escaped) pixels; None until
        RebuildHistograms() is called.
    int_hist (Image.Histogram | None): Histogram for interior (Set) pixels, with values
        stored as positive integers; None until RebuildHistograms() is called.

  """

  @dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
  class Histogram:
    """Stores a histogram for a part of an image (usually set points and escaped points).

    Attributes:
      count (int): The total count of pixels in this histogram.
      min_value (int): The minimum integer escape value in this histogram.
      max_value (int): The maximum integer escape value in this histogram.
      bucket_min (int): The minimum smoothed bucket key in this histogram.
      bucket_max (int): The maximum smoothed bucket key in this histogram.
      min_nu (float): The minimum fractional escape part (nu) seen across all pixels.
      max_nu (float): The maximum fractional escape part (nu) seen across all pixels.
      d_cumulative (dict[int, int]): {value: cumulative_count} for O(1) lookup.
      d_bucket_linear (dict[int, int]): {bucket_key: count} for O(1) lookup.
      bucket_cumulative (list[tuple[int, int]]): Sorted list of (bucket_key, cumulative_count)
          pairs; the smoothed cumulative bucket histogram.

    Properties (computed on-the-fly):
      linear (list[tuple[int, int]]): Sorted list of (value, count) pairs; the raw histogram.
      d_linear (dict[int, int]): {value: count} for O(1) lookup in the raw histogram.
      cumulative (list[tuple[int, int]]): Sorted list of (value, cumulative_count) pairs;
          the cumulative raw histogram.
      bucket_linear (list[tuple[int, int]]): Sorted list of (bucket_key, count) pairs;
          the smoothed bucket histogram.
      d_bucket_cumulative (dict[int, int]): {bucket_key: cumulative_count} for O(1) lookup.

    """

    count: int
    min_value: int
    max_value: int
    bucket_min: int
    bucket_max: int
    min_nu: float
    max_nu: float
    d_cumulative: dict[int, int]  # {value: cumulative_count}, for O(1) lookups
    d_bucket_linear: dict[int, int]  # {bucket_key: count}, for O(1) lookups
    bucket_cumulative: list[tuple[int, int]]  # sorted!

    @property
    def linear(self) -> list[tuple[int, int]]:
      """Sorted list of (value, count) pairs; the raw histogram. Computed on-the-fly.

      Returns:
        list[tuple[int, int]]: A sorted list of (value, count) pairs representing the raw histogram.

      """
      result: list[tuple[int, int]] = []
      prev: int = 0
      for k, v in sorted(self.d_cumulative.items()):
        result.append((k, v - prev))
        prev = v
      return result

    @property
    def d_linear(self) -> dict[int, int]:
      """{value: count} for O(1) lookup in the raw histogram. Computed on-the-fly.

      Returns:
        dict[int, int]: A dictionary mapping escape values to their counts in the raw histogram.

      """
      return dict(self.linear)

    @property
    def cumulative(self) -> list[tuple[int, int]]:
      """Sorted list of (value, cumulative_count) pairs. Computed on-the-fly.

      Returns:
        list[tuple[int, int]]: A sorted list of (value, cumulative_count) pairs representing
            the cumulative raw histogram.

      """
      return sorted(self.d_cumulative.items())

    @property
    def bucket_linear(self) -> list[tuple[int, int]]:
      """Sorted list of (bucket_key, count) pairs; the smoothed bucket histogram.

      Returns:
        list[tuple[int, int]]: A sorted list of (bucket_key, count) pairs representing
            the smoothed bucket histogram.

      """
      return sorted(self.d_bucket_linear.items())

    @property
    def d_bucket_cumulative(self) -> dict[int, int]:
      """{bucket_key: cumulative_count} for O(1) lookup. Computed on-the-fly.

      Returns:
        dict[int, int]: A dictionary mapping bucket keys to cumulative counts.

      """
      return dict(self.bucket_cumulative)

    @property
    def self_sz(self) -> int:
      """Get the size of the object in bytes, including nested objects.

      Not guaranteed to be exact, but should be a good estimate for our purposes.
      Not a super cheap call, don't overuse it.

      Returns:
        int: The size of the object in bytes.

      """
      return frame.DeepSize(self)

    def BucketCumulativeBefore(self, key: int) -> float:
      """Get the cumulative count before the given key, using binary search.

      Args:
        key (int): The key to find the cumulative count before.

      Returns:
        float: The cumulative count before the given key.

      """
      idx: int = bisect.bisect_left(self.bucket_cumulative, (key, -math.inf)) - 1
      return 0.0 if idx < 0 else self.bucket_cumulative[idx][1]

    def InterpolateBucket(self, n: int, nu: float) -> float:
      """Interpolate the cumulative count for a given (n, nu) using the bucket histograms.

      Args:
        n (int): The escape iteration count (or interior iteration count) for the pixel.
        nu (float): The fractional part of the escape iteration, used for smooth coloring.

      Returns:
        float: The interpolated cumulative count for the given (n, nu), normalized to [0, 1].

      """
      # the image is ALSO banding with this version
      n, nu = _SmoothHistKey(n, nu)
      if n < self.bucket_min:
        return 0.0
      if n > self.bucket_max:
        return _ALMOST_ONE
      c_before: float = self.BucketCumulativeBefore(n)
      bucket: int = self.d_bucket_linear.get(n, 0)
      t: float = (c_before + nu * bucket) / self.count
      if t < 0.0:
        return 0.0
      if t >= 1.0:
        return _ALMOST_ONE
      return t

  @dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
  class FrameColorNorm:
    """Interpolated color normalization for a single animation frame between two marker frames.

    Smoothly blends between the two surrounding marker frames' histogram normalizations so that
    the same raw escape-iteration value maps to a consistent (and smoothly transitioning) palette
    position across the entire animation journey. This eliminates the wild per-frame color shifts
    that arise when each frame independently histogram-equalizes its own escape iteration data.

    At a marker frame, alpha is exactly 0.0 (frame IS the lower/prev marker) or 1.0 (frame IS the
    upper/next marker), so the coloring is identical to the marker's own per-frame normalization.
    Between marker frames, alpha is linearly interpolated for a smooth cross-fade.

    See ZoomColorNorm for construction and usage.

    Attributes:
      prev_ext (Image.Histogram): Exterior (escaped) histogram of the preceding marker frame.
      next_ext (Image.Histogram): Exterior (escaped) histogram of the following marker frame.
      prev_int (Image.Histogram): Interior (Set) histogram of the preceding marker frame.
      next_int (Image.Histogram): Interior (Set) histogram of the following marker frame.
      alpha (float): Blend weight in [0.0, 1.0]; 0.0 means use prev only, 1.0 means use next
          only; linearly interpolated between adjacent marker frames.

    """

    prev_ext: Image.Histogram  # exterior histogram of the preceding marker frame
    next_ext: Image.Histogram  # exterior histogram of the following marker frame
    prev_int: Image.Histogram  # interior histogram of the preceding marker frame
    next_int: Image.Histogram  # interior histogram of the following marker frame
    alpha: float  # blend weight in [0.0, 1.0]: 0.0 = use prev only, 1.0 = use next only

    def InterpolateExt(self, n: int, nu: float) -> float:
      """Get the cross-frame-stable blended palette position for an exterior (escaped) pixel.

      Args:
        n (int): The escape iteration count for the pixel.
        nu (float): The fractional escape iteration for smooth coloring.

      Returns:
        float: Blended palette position in [0, 1).

      """
      if self.alpha <= 0.0:
        return self.prev_ext.InterpolateBucket(n, nu)
      if self.alpha >= 1.0:
        return self.next_ext.InterpolateBucket(n, nu)
      t_prev: float = self.prev_ext.InterpolateBucket(n, nu)
      t_next: float = self.next_ext.InterpolateBucket(n, nu)
      return t_prev + self.alpha * (t_next - t_prev)

    def InterpolateInt(self, key: int) -> float:
      """Get the cross-frame-stable blended palette position for an interior (Set) pixel.

      Args:
        key (int): The positive interior key (the negated stored escape value: -escaped_at).

      Returns:
        float: Blended palette position in [0, 1).

      """
      t_prev: float = (
        (self.prev_int.d_cumulative.get(key, 0) - 1) / self.prev_int.count
        if self.prev_int.count > 0
        else 0.0
      )
      if self.alpha <= 0.0:
        return max(0.0, min(_ALMOST_ONE, t_prev))
      t_next: float = (
        (self.next_int.d_cumulative.get(key, 0) - 1) / self.next_int.count
        if self.next_int.count > 0
        else 0.0
      )
      if self.alpha >= 1.0:
        return max(0.0, min(_ALMOST_ONE, t_next))
      return max(0.0, min(_ALMOST_ONE, t_prev + self.alpha * (t_next - t_prev)))

  @dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
  class ZoomColorNorm:
    """Anchors color normalization for all frames in a zoom animation using marker frames.

    Marker frames are computed first at deterministic, evenly-spaced zoom-magnitude intervals
    (one marker every MAGNITUDE_PER_FRAME_MARKER decades of zoom). For any non-marker frame
    between two adjacent markers, this class interpolates linearly between the two markers'
    histogram normalizations. The result: the same raw escape-iteration value maps to a
    consistent (and smoothly cross-fading) palette position throughout the entire animation,
    eliminating the wild per-frame color shifts that arise from independent histogram equalization.

    Typical usage in zoomcommand.Auto() (abbreviated):
      1. Compute all marker frames, collecting {frame_idx: Image} in all_marker_imgs.
      2. Build: zoom_norm = ZoomColorNorm.FromMarkers(all_marker_imgs)
      3. Re-render every frame: img.AsPNG(render, zoom_norm=zoom_norm.ForFrame(frame_idx))

    Attributes:
      markers (list[tuple[int, Image.Histogram, Image.Histogram]]): Sorted list of
          (frame_idx, ext_hist, int_hist) tuples for each marker frame.

    """

    # sorted list of (frame_idx, ext_hist, int_hist)
    markers: list[tuple[int, Image.Histogram, Image.Histogram]]

    def __post_init__(self) -> None:
      """Check parameters for validity.

      Raises:
        Error: if any parameter is invalid.

      """
      if len(self.markers) < 2:  # noqa: PLR2004
        raise Error(f'ZoomColorNorm requires at least 2 markers, got {len(self.markers)}')
      for j in range(1, len(self.markers)):
        if self.markers[j][0] <= self.markers[j - 1][0]:
          raise Error(
            f'ZoomColorNorm markers must be strictly sorted by frame index; '
            f'got indices [{self.markers[j - 1][0]}, {self.markers[j][0]}]'
          )

    @staticmethod
    def FromSortedMarkers(marker_imgs: abc.Iterable[tuple[int, Image]]) -> Image.ZoomColorNorm:
      """Build a ZoomColorNorm from an iterable of (frame_idx, Image) tuples for the marker frames.

      Args:
        marker_imgs (abc.Iterable[tuple[int, Image]]): The marker images keyed by frame index.
            Every Image must have valid escape data; histograms will be built here if not
            yet present; we require these come in sorted order by frame index for a single pass

      Returns:
        ZoomColorNorm: The constructed ZoomColorNorm.

      Raises:
        Error: if fewer than 2 markers are provided or histograms cannot be built.

      """
      # build the marker list; iterating once so mypy can narrow ext_hist / int_hist to non-None
      marker_list: list[tuple[int, Image.Histogram, Image.Histogram]] = []
      idx: int
      img: Image
      for idx, img in marker_imgs:
        if not img.ext_hist or not img.int_hist:
          img.RebuildHistograms()
        if not img.ext_hist or not img.int_hist:
          raise Error(f'Failed to build histograms for marker frame {idx}')
        marker_list.append((idx, img.ext_hist, img.int_hist))
      return Image.ZoomColorNorm(markers=marker_list)

    def ForFrame(self, frame_idx: int) -> tuple[int, int, Image.FrameColorNorm]:
      """Get the interpolated color normalization for a given frame index.

      Finds the two surrounding marker frames and computes the linear blend weight alpha based
      on the frame's position within the marker interval. At a marker frame exactly, alpha is
      0.0 (frame IS the lower/prev marker) or 1.0 (frame IS the upper/next marker).

      Args:
        frame_idx (int): The frame index to get color normalization for.

      Returns:
        tuple[int, int, Image.FrameColorNorm]: tuple of:
          - The index of the previous marker frame.
          - The index of the next marker frame.
          - The interpolated color normalization for the given frame.

      """
      marker_indexes: list[int] = [m[0] for m in self.markers]
      # find the position of frame_idx in the sorted marker index list
      pos: int = bisect.bisect_right(marker_indexes, frame_idx) - 1
      # clamp to valid interval (only possible if frame_idx is outside the marker range, a bug)
      pos = max(0, min(pos, len(self.markers) - 2))
      prev_idx: int
      prev_ext: Image.Histogram
      prev_int: Image.Histogram
      next_idx: int
      next_ext: Image.Histogram
      next_int: Image.Histogram
      prev_idx, prev_ext, prev_int = self.markers[pos]
      next_idx, next_ext, next_int = self.markers[pos + 1]
      alpha: float = 0.0 if next_idx == prev_idx else (frame_idx - prev_idx) / (next_idx - prev_idx)
      return (
        prev_idx,
        next_idx,
        Image.FrameColorNorm(
          prev_ext=prev_ext,
          next_ext=next_ext,
          prev_int=prev_int,
          next_int=next_int,
          alpha=alpha,
        ),
      )

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
    self.escape: ImageUInt64Array = array.array(  # unsigned int64
      # 'L' = unsigned long: 8 bytes on Linux/macOS 64-bit, but 4 bytes on Windows 64-bit!
      # using 'Q' (always 8 bytes, guaranteed by the C standard to be uint64_t) is
      # cleaner and more portable than 'L' and works on all platforms; we double-check the size
      'Q',
      (0 for _ in range(self._params.width * self._params.height)),
    )
    if self.escape.itemsize != frame.N_BYTES_UINT:
      raise Error(f'unsupported platform: array of unsigned ints is not {frame.N_BYTES_UINT} bytes')
    self.stats: FractalStats | None = None  # may be set later by the fractal rendering function
    # histogram of escaped points
    self.ext_hist: Image.Histogram | None = None  # set later by calling RebuildHistograms
    # histogram of interior (Set) points; flipped, i.e., positive values
    self.int_hist: Image.Histogram | None = None  # set later by calling RebuildHistograms

  @property
  def params(self) -> frame.ComputationParameters:
    """Get the computation parameters associated with this image.

    Returns:
      frame.ComputationParameters: The computation parameters associated with this image.

    """
    return self._params

  @property
  def self_sz(self) -> int:
    """Get the size of the object in bytes, including nested objects.

    Not guaranteed to be exact, but should be a good estimate for our purposes.
    Not a super cheap call, don't overuse it.

    Returns:
      int: The size of the object in bytes.

    """
    return frame.DeepSize(self)

  def RebuildHistograms(self) -> None:
    """Rebuild the histograms for the image based on the current escape data.

    This method processes the escape data of the image and constructs histograms
    for both exterior (escaped) and interior (set) points. The histograms are
    used for color mapping during rendering.

    """
    # for efficiency, try to go over only once
    exterior_points: list[tuple[int, float]] = []
    interior_points: list[tuple[int, float]] = []
    n: int
    f: float
    for enc_px in self.escape:
      n, f = Decode64ToIntFloat(enc_px)
      if n >= 0:
        exterior_points.append((n, f))
      else:
        interior_points.append((-n, f))  # we flip the sign for interior points!
    # have 2 groups of pixels
    self.ext_hist = _BuildCumulative(exterior_points)  # ext generator
    self.int_hist = _BuildCumulative(interior_points)  # int generator

  def AsPixels(self, render: RenderParameters, *, zoom_norm: FrameColorNorm | None = None) -> bytes:
    """Convert the image to raw pixel bytes using histogram-equalized smooth color palette.

    Exterior points (escaped) are colored by mapping their escape iteration through a cumulative
    histogram distribution (histogram equalization) into [0, 1), which is then fed into a smooth
    cycling color gradient via (PixelPalette). This ensures the full color range is used
    regardless of zoom depth or iteration distribution.

    Interior (Set) points that never escaped are rendered as pure black by default. When
    `color_set_points=True`, they are instead colored using `set_pal` via the same histogram
    equalization approach, applied to their stored |z| magnitude (the negative of the stored
    escape value), so the full `set_pal` range is used across the Set interior.

    When `zoom_norm` is provided (animation rendering), the histogram-equalized position is
    computed by blending between the two surrounding marker frames' histograms instead of using
    this frame's own histogram. This keeps colors stable across the entire animation journey.

    Args:
      render (RenderParameters): The render parameters to use for generating the PNG metadata.
      zoom_norm (FrameColorNorm | None): Optional cross-frame color normalization for animation
          rendering. If None (default), each frame's own histogram is used (per-frame equalized).

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
    if (
      self.ext_hist.min_value < 0
      or (self._params.depth + frame.SMOOTH_EXTRA_ITERS) < self.ext_hist.max_value
    ):
      raise Error(
        f'Invalid/Inconsistent {self.ext_hist.min_value=} or '
        f'{self._params.depth=}+{frame.SMOOTH_EXTRA_ITERS} < {self.ext_hist.max_value=}'
      )
    # map each pixel to an RGB color; zoom_norm (if given) blends between adjacent marker
    # histograms for cross-frame consistency instead of using this frame's own histogram
    escaped_at: int
    f_nu: float
    pixels = bytearray(self._params.width * self._params.height * 3)
    for i, enc_escaped_at in enumerate(self.escape):
      escaped_at, f_nu = Decode64ToIntFloat(enc_escaped_at)
      if escaped_at >= 0 and self.ext_hist.count > 0:
        # exterior point: histogram-equalized position in palette
        t_ext: float = (
          zoom_norm.InterpolateExt(escaped_at, f_nu)
          if zoom_norm is not None
          else self.ext_hist.InterpolateBucket(escaped_at, f_nu)
        )
        rgb: tuple[int, int, int] = _PixelPalette(t_ext, render.escaped_pal)
      elif self._params.set_points and self.int_hist.count > 0 and escaped_at < 0:
        # interior (Set) point: histogram-equalized position in set_pal over |z| magnitudes
        if render.set_pal is None:
          raise Error('set_pal must be specified in RenderParameters when set_points is True')
        t_set: float = (
          zoom_norm.InterpolateInt(-escaped_at)
          if zoom_norm is not None
          else (self.int_hist.d_cumulative[-escaped_at] - 1) / self.int_hist.count
        )
        rgb = _PixelPalette(t_set, render.set_pal)
      else:
        rgb = (0, 0, 0)  # black: interior point (default) or all-interior image
      pixels[i * 3], pixels[i * 3 + 1], pixels[i * 3 + 2] = rgb
    return bytes(pixels)

  def AsPNG(
    self,
    render: RenderParameters,
    *,
    zoom_norm: FrameColorNorm | None = None,
    no_meta: bool = False,
  ) -> tuple[bytes, str]:
    """Convert the image to PNG bytes and return it with its internal data hash.

    Args:
      render (RenderParameters): The render parameters to use for generating the PNG metadata.
      zoom_norm (FrameColorNorm | None): Optional cross-frame color normalization; passed
          through to AsPixels(). Use for animation frames to keep colors stable across zoom.
      no_meta (bool): If True, do not include metadata in the PNG; mainly for video frames where
          metadata is not needed and adds overhead. Default is False (include metadata).

    Returns:
      tuple[bytes, str]: PNG image data and its internal data hash.

    """
    # convert the raw pixel data to a PNG using PIL
    raw_img: bytes = self.AsPixels(render, zoom_norm=zoom_norm)
    img_data_hash: str = hashes.Hash256(raw_img).hex()
    img: PILImage.Image = PILImage.frombytes(
      'RGB', (self._params.width, self._params.height), raw_img
    )
    # embed frame parameters as PNG tEXt metadata chunks; keys use a "tranZoom:" (_app) namespace
    png_meta: PngImagePlugin.PngInfo | None = None
    if not no_meta:
      png_meta = PngImagePlugin.PngInfo()
      for k, v in MakeImageMeta(self, render, img_data_hash).items():
        png_meta.add_text(k, v)
    # save to PNG bytes, hash and return
    buf = io.BytesIO()
    img.save(buf, format='PNG', pnginfo=png_meta)
    logging.debug(
      f'AsPNG: rendered {self._params.width} x {self._params.height} '
      f'{self._params.frm.fractal.value} PNG, hash {img_data_hash[:16]!r}'
    )
    return (buf.getvalue(), img_data_hash)


def MakeImageMeta(img: Image, render: RenderParameters, data_hash: str) -> dict[str, str]:  # noqa: C901, PLR0912
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
    META_COMPUTATION_WIDTH_KEY: str(img.params.size[0]),
    META_COMPUTATION_HEIGHT_KEY: str(img.params.size[1]),
    META_IMAGE_HASH_KEY: data_hash,
    META_COMPUTATION_COLOR_SET_KEY: str(img.params.set_points.value)
    if img.params.set_points
    else 'none',
    META_COMPUTATION_HASH_KEY: img.params.sha,
    META_RENDER_PALETTE_KEY: render.escaped_pal.value,
    META_RENDER_SET_PALETTE_KEY: render.set_pal.value if render.set_pal else 'none',
    META_RENDER_OVERLAY_KEY: render.overlay.value if render.overlay else 'none',
    META_RENDER_MARK_RE_KEY: str(render.mark_re),
    META_RENDER_MARK_IM_KEY: str(render.mark_im),
    META_RENDER_MARK_COLOR_KEY: render.mark_color.name.lower() if render.mark_color else 'none',
    META_RENDER_MARK_WIDTH_KEY: str(render.mark_width),  # int
    META_RENDER_HASH_KEY: render.sha,
    # frame
    META_FRACTAL_KEY: frm.fractal.value,
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
    META_FRAME_HASH_KEY: frm.sha,
    # escape iteration in the image
    META_COMPUTATION_SEARCH_DEPTH_KEY: str(img.params.depth),
    # histogram / min-max counts
    META_IMAGE_EXT_COUNT_KEY: str(img.ext_hist.count),
    META_IMAGE_EXT_N_MIN_KEY: str(img.ext_hist.min_value),
    META_IMAGE_EXT_N_MAX_KEY: str(img.ext_hist.max_value),
    META_IMAGE_EXT_NU_MIN_KEY: str(img.ext_hist.min_nu),
    META_IMAGE_EXT_NU_MAX_KEY: str(img.ext_hist.max_nu),
    META_IMAGE_EXT_BUCKET_MIN_KEY: str(img.ext_hist.bucket_min),
    META_IMAGE_EXT_BUCKET_MAX_KEY: str(img.ext_hist.bucket_max),
    META_IMAGE_SET_COUNT_KEY: str(img.int_hist.count),
    META_IMAGE_SET_N_MIN_KEY: str(img.int_hist.min_value),
    META_IMAGE_SET_N_MAX_KEY: str(img.int_hist.max_value),
    META_IMAGE_SET_NU_MIN_KEY: str(img.int_hist.min_nu),
    META_IMAGE_SET_NU_MAX_KEY: str(img.int_hist.max_nu),
    META_IMAGE_SET_BUCKET_MIN_KEY: str(img.int_hist.bucket_min),
    META_IMAGE_SET_BUCKET_MAX_KEY: str(img.int_hist.bucket_max),
  }
  # histograms
  if img.ext_hist.count > 0:
    img_meta[META_IMAGE_EXT_HISTOGRAM_LINEAR_KEY] = SummaryHistogram(img.ext_hist.linear)
    img_meta[META_IMAGE_EXT_HISTOGRAM_LINEAR_CUM_KEY] = SummaryHistogram(img.ext_hist.cumulative)
    img_meta[META_IMAGE_EXT_HISTOGRAM_BUCKET_KEY] = SummaryHistogram(img.ext_hist.bucket_linear)
    img_meta[META_IMAGE_EXT_HISTOGRAM_BUCKET_CUM_KEY] = SummaryHistogram(
      img.ext_hist.bucket_cumulative
    )
  if img.params.set_points and img.int_hist.count > 0:
    img_meta[META_IMAGE_SET_HISTOGRAM_LINEAR_KEY] = SummaryHistogram(img.int_hist.linear)
    img_meta[META_IMAGE_SET_HISTOGRAM_LINEAR_CUM_KEY] = SummaryHistogram(img.int_hist.cumulative)
    img_meta[META_IMAGE_SET_HISTOGRAM_BUCKET_KEY] = SummaryHistogram(img.int_hist.bucket_linear)
    img_meta[META_IMAGE_SET_HISTOGRAM_BUCKET_CUM_KEY] = SummaryHistogram(
      img.int_hist.bucket_cumulative
    )
  # add any stats that aren't just noise
  if img.stats:
    if img.stats.max_lo is not None:
      img_meta[META_IMAGE_STATS_MAX_LO_KEY] = str(img.stats.max_lo)
    if img.stats.max_hi is not None:
      img_meta[META_IMAGE_STATS_MAX_HI_KEY] = str(img.stats.max_hi)
    if img.stats.min_lo:
      img_meta[META_IMAGE_STATS_MIN_LO_KEY] = str(img.stats.min_lo)
    if img.stats.min_hi:
      img_meta[META_IMAGE_STATS_MIN_HI_KEY] = str(img.stats.min_hi)
    if img.stats.ang_lo:
      img_meta[META_IMAGE_STATS_ANG_LO_KEY] = str(img.stats.ang_lo)
    if img.stats.ang_hi:
      img_meta[META_IMAGE_STATS_ANG_HI_KEY] = str(img.stats.ang_hi)
    if img.stats.imag_lo:
      img_meta[META_IMAGE_STATS_IMAG_LO_KEY] = str(img.stats.imag_lo)
    if img.stats.imag_hi:
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

  def _SmallHistogram() -> list[tuple[int | str, int]]:
    if len(sorted_histogram) <= 7:  # noqa: PLR2004
      # small histogram, no need to summarize
      return sorted_histogram  # type: ignore[return-value]
    # this is usually the case: many escape values, so summarize the middle ones
    # make a new list with the first 3 and last 3 values, and a summary of the middle values "..."
    return [
      *sorted_histogram[:3],
      ('...', sum(count for _, count in sorted_histogram[3:-3])),
      *sorted_histogram[-3:],
    ]

  return '{' + (', '.join(f'{n}: {f}' for n, f in _SmallHistogram())) + '}'


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


def GetBasicDataFromImage(img_bytes: bytes) -> tuple[int, int, str, tbase.JSONDict]:  # noqa: C901, PLR0912, PLR0915
  """Get basic data from an image (PNG, GIF, or MP4), including format, size, hash, and metadata.

  Args:
    img_bytes (bytes): The image data as bytes (PNG, GIF, or MP4).

  Returns:
    tuple[int, int, str, tbase.JSONDict]: (width, height, hash, metadata) where:
      - width: The width of the image in pixels.
      - height: The height of the image in pixels.
      - hash: A hash of the image data (SHA256 of RGB bytes).
      - metadata: The extracted metadata from the image.

  Raises:
    Error: If the image format is unsupported or if there are issues processing the image.

  """
  # MP4: has an 'ftyp' ISO base media box at bytes 4-8; PILImage.open() raises on MP4, so we
  # must detect and handle it before reaching PIL
  raw_hash: str
  width: int
  height: int
  if len(img_bytes) >= 8 and img_bytes[4:8] == b'ftyp':  # noqa: PLR2004
    with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
      tmp.write(img_bytes)
      tmp.flush()
      tmp_path = pathlib.Path(tmp.name)
      # get width/height via imageio (reliable); get_meta_data() does NOT expose container tags
      reader = imageio.get_reader(  # pyright: ignore[reportUnknownMemberType]
        tmp_path,
        format='ffmpeg',  # type: ignore[arg-type]
      )
      width, height = cast('tuple[int, int]', reader.get_meta_data().get('size', (0, 0)))  # type: ignore[union-attr]
      reader.close()
      # read container tags (including our JSON comment) via ffmpeg -f ffmetadata;
      # this is the only way to access format.tags since imageio doesn't expose them
      proc = subprocess.run(  # noqa: S603
        [
          imageio_ffmpeg.get_ffmpeg_exe(),
          '-v',
          'quiet',
          '-i',
          str(tmp_path),
          '-f',
          'ffmetadata',
          'pipe:1',
        ],
        capture_output=True,
        text=True,
        check=False,
      )
    if width < 1 or height < 1:
      raise Error(f'Invalid MP4 frame size {width} x {height}')
    if proc.returncode != 0:
      raise Error(f'ffmpeg failed reading MP4 metadata: {proc.stderr.strip()!r}')
    # parse ffmetadata format: key=value lines; comments start with ';', sections with '['
    mp4_tags: dict[str, str] = {}
    tag_k: str
    tag_v: str
    for line in proc.stdout.splitlines():
      if line.startswith((';', '[')) or '=' not in line:
        continue
      tag_k, tag_v = line.split('=', 1)
      mp4_tags[tag_k] = tag_v
    # metadata was stored by WriteVideoMP4 as a single JSON string in the 'comment' field
    # (mirrors how GIF stores metadata in its comment field)
    mp4_meta: tbase.JSONDict = {}
    raw_hash = ''
    if 'comment' in mp4_tags:
      try:
        mp4_meta = json.loads(mp4_tags['comment'])
        if META_IMAGE_HASH_KEY in mp4_meta:
          raw_hash = str(mp4_meta[META_IMAGE_HASH_KEY])
        else:
          logging.error('DO NOT trust this MP4 hash')
      except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        logging.error('MP4 comment metadata not valid JSON, ignoring; DO NOT trust this MP4 hash')  # noqa: TRY400
    if not raw_hash:
      logging.error(
        'MP4 missing %r in metadata; falling back to file hash (DO NOT trust)', META_IMAGE_HASH_KEY
      )
      raw_hash = hashes.Hash256(img_bytes).hex()
    return (width, height, raw_hash, mp4_meta)
  with PILImage.open(io.BytesIO(img_bytes)) as img:
    # get the internal data we need (size and hash)
    width = img.width
    height = img.height
    if width < 1 or height < 1:
      raise Error(f'Invalid image size {width} x {height}')
    raw_hash = hashes.Hash256(img.convert('RGB').tobytes()).hex()  # not 'RGBA'!!
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
      raise Error('MP4 format reached PIL unexpectedly; file bytes may not be a valid MP4')
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
    col (Color): The color of the cross; default is DEFAULT_MARK_COLOR.
    lw (int): The line width of the cross in pixels; default is DEFAULT_MARK_WIDTH.

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
      raise Error(f'Invalid coordinates for cross overlay: {x=}, {y=}, image size {w=} x {h=}')
    # draw the cross lines
    draw.line((0, y, w, y), fill=col.value, width=lw)
    draw.line((x, 0, x, h), fill=col.value, width=lw)
    # done, save remembering to add metadata that this image has an overlay
    return SaveWithMeta(img)


def SaveWithMeta(img: PILImage.Image, *, extra_meta: dict[str, str] | None = None) -> bytes:
  """Save a PIL image to PNG bytes, including its metadata.

  Args:
    img (PILImage.Image): The PIL image to save.
    extra_meta (dict[str, str] | None): Optional additional metadata to include in the PNG;
        default is None.

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


def CleanSavePNG(img_data: bytes, *, extra_meta: dict[str, str] | None = None) -> bytes:
  """Save a PNG bytes to a clean copy PNG bytes, including only metadata given in `meta`, if any.

  Args:
    img_data (bytes): The original PNG image data as bytes.
    extra_meta (dict[str, str] | None): Optional metadata to include in the PNG.

  Returns:
    bytes: The PNG image data as bytes.

  """
  with PILImage.open(io.BytesIO(img_data)) as img:
    # keep only meta that was explicitly given
    png_meta = PngImagePlugin.PngInfo()
    if extra_meta:
      for k, v in extra_meta.items():
        png_meta.add_text(k, v)
    # save to PNG bytes, return
    output = io.BytesIO()
    img.save(output, format='PNG', pnginfo=png_meta)
    return output.getvalue()


def CleanSaveJPG(img_data: bytes, *, extra_meta: dict[str, str] | None = None) -> bytes:
  """Save a PNG bytes to a clean copy JPG bytes, including only metadata given in `meta`, if any.

  Args:
    img_data (bytes): The original PNG image data as bytes.
    extra_meta (dict[str, str] | None): Optional metadata to include in the JPG.

  Returns:
    bytes: The JPG image data as bytes.

  """
  exif: PILImage.Exif | None = None
  with PILImage.open(io.BytesIO(img_data)) as img:
    if extra_meta:
      # store metadata as compact JSON in EXIF ImageDescription (tag 0x010E)
      exif = PILImage.Exif()
      # list of tags in: https://github.com/python-pillow/Pillow/blob/main/src/PIL/ExifTags.py
      exif[ExifTags.Base.ImageDescription] = json.dumps(extra_meta, separators=(',', ':'))
    output = io.BytesIO()
    img.save(
      output,
      format='JPEG',
      quality=JPEG_QUALITY,
      optimize=True,
      exif=exif.tobytes() if exif else None,
    )
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


def _PixelPalette(
  t: float,
  pal: palette.Palette,
  *,
  cycles: int = 1,
) -> tuple[int, int, int]:
  """Get the RGB color for a histogram-equalized normalized palette position.

  Smoothly interpolates between adjacent stops in the specified palette, cycling
  `cycles` times across the [0, 1) range. Use PALETTE_CYCLES (3) for exterior palettes
  (tighter color banding) and SET_PALETTE_CYCLES (1) for the interior Set palette
  (single smooth gradient, black near the boundary).

  Args:
    t (float): Normalized position in [0, 1) derived from histogram equalization.
    pal (Palette): The palette to use.
    cycles (int): How many times to cycle through the palette across [0, 1); default is 1.

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
  t_cycled: float = t if cycles == 1 else (t * cycles) % 1.0
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


def _BuildCumulative(values: abc.Iterable[tuple[int, float]]) -> Image.Histogram:
  """Build a raw histogram and cumulative histogram from a pre-filtered list of integer values.

  This is a smooth float histogram.

  Args:
    values (abc.Iterable[tuple[int, float]]): The iterable of escaped values (n, nu) to histogram.

  Returns:
    Image.Histogram: The histogram object containing the raw and cumulative histograms and
        the total count.

  """
  # build the raw histogram
  histogram: dict[int, int] = {}
  bucket_histogram: dict[int, int] = {}
  total: int = 0
  min_nu: float = 1000.0
  max_nu: float = -1000.0
  k: int
  for esc, nu in values:
    histogram[esc] = histogram.get(esc, 0) + 1
    k = _SmoothHistKey(esc, nu)[0]
    bucket_histogram[k] = bucket_histogram.get(k, 0) + 1
    total += 1
    min_nu = min(min_nu, nu)
    max_nu = max(max_nu, nu)
  # return trivial case (that would cause issues with min() and max())
  if not histogram:
    return Image.Histogram(
      count=0,
      min_value=0,
      max_value=0,
      bucket_min=0,
      bucket_max=0,
      min_nu=0.0,
      max_nu=0.0,
      d_cumulative={},
      d_bucket_linear={},
      bucket_cumulative=[],
    )
  # build the cumulative histogram by iterating over the sorted keys of the raw histogram
  cum: int = 0
  s_histogram: list[tuple[int, int]] = sorted(histogram.items())
  s_cum: list[tuple[int, int]] = []
  v: int
  for k, v in s_histogram:
    cum += v
    s_cum.append((k, cum))
  cum = 0
  s_bucket_histogram: list[tuple[int, int]] = sorted(bucket_histogram.items())
  s_bucket_cum: list[tuple[int, int]] = []
  for k, v in s_bucket_histogram:
    cum += v
    s_bucket_cum.append((k, cum))
  # build object and return
  return Image.Histogram(
    count=total,
    min_value=min(histogram),
    max_value=max(histogram),
    bucket_min=min(bucket_histogram),
    bucket_max=max(bucket_histogram),
    min_nu=min_nu,
    max_nu=max_nu,
    d_cumulative=dict(s_cum),
    d_bucket_linear=bucket_histogram,
    bucket_cumulative=s_bucket_cum,
  )


def _SmoothHistKey(n: int, nu: float) -> tuple[int, float]:
  """Get a smoothed histogram key for an escaped value (n, nu).

  Args:
    n (int): The integer escape value.
    nu (float): The fractional part of the escape value.

  Returns:
    tuple[int, float]: A tuple containing the smoothed histogram key (int) and the
        fractional part (float) for interpolation

  """
  x: float = (n + nu) * _HIST_SUB_BINS
  k: int = math.floor(x)
  return (k, x - k)


def _ImageNormalizeAndValidate(img_bytes: bytes, width: int, height: int) -> PILImage.Image:
  """Normalize the image bytes to a PIL Image in RGB mode, and validate its size.

  Args:
    img_bytes (bytes): The image data as bytes.
    width (int): The expected width of the image.
    height (int): The expected height of the image.

  Returns:
    PILImage.Image: The normalized PIL Image in RGB mode.

  Raises:
    Error: on error

  """
  with PILImage.open(io.BytesIO(img_bytes)) as img:
    if img.size != (width, height):
      raise Error(f'frame size {img.size} != {(width, height)}')
    if img.mode != 'RGB':
      raise Error(f'expected RGB frame, got mode {img.mode!r}')
    return img.copy()


def WriteAnimatedGIF(
  frames: abc.Iterable[bytes],
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
    frames (abc.Iterable[bytes]): An iterable (or generator) of PIL Image frames to include in
        the GIF. Frames are consumed lazily one at a time, so they do not need to all fit in
        memory at once.
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
  # pull the first frame from the iterator; remaining frames are consumed lazily via a generator
  frames_iter: abc.Iterator[bytes] = iter(frames)
  try:
    first_frame: bytes = next(frames_iter)
  except StopIteration:
    raise Error('frames iterable is empty')  # noqa: B904
  frame_count: list[int] = [1]  # mutable container so the nested generator can mutate it

  def _RemainingFrames() -> abc.Iterator[PILImage.Image]:
    for frm in frames_iter:
      frame_count[0] += 1
      yield _ImageNormalizeAndValidate(frm, width, height)

  # save the whole GIF, normalizing each frame; PIL will iterate _RemainingFrames() lazily to save
  img0: PILImage.Image = _ImageNormalizeAndValidate(first_frame, width, height)
  img0.save(
    # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif
    path,
    save_all=True,
    # append without repeating the first frame, which is already saved as img0
    append_images=_RemainingFrames(),
    duration=round(1000.0 * duration / n_frames),  # duration in milliseconds per frame
    loop=loop,
    disposal=1,  # 1 == do not dispose, overwrite; more efficient b/c we don't have any transparency
    # delta-encode unchanged pixels as transparent to reduce file size
    optimize=True,  # optimize the palette and compression for smaller file size
    # GIF comment field can store arbitrary bytes, we use it to store JSON metadata
    comment=json.dumps(meta).encode('utf-8') if meta is not None else None,
  )
  # done, check that the frame count matches n_frames
  if frame_count[0] != n_frames:
    raise Error(f'frames generator produced {frame_count[0]} frames, expected {n_frames}')


def ReWriteAnimatedGIFMeta(
  old_path: pathlib.Path,
  new_path: pathlib.Path,
  meta: dict[str, str] | None,
  loop: int = 0,  # 0 == infinite loop
) -> None:
  """Read old_path GIF and re-write to new_path with the same frames and new metadata.

  We more-or-less assume the file was written with WriteAnimatedGIF().

  Args:
    old_path (pathlib.Path): The file path of the original GIF to read.
    new_path (pathlib.Path): The file path to save the modified GIF.
    meta (dict[str, str] | None): Optional metadata to include in the new GIF; default None
    loop (int): The number of times to loop the GIF (0 for infinite loop). Default is 0 which
        means infinite loop.

  Raises:
    Error: on error

  """
  # open the original GIF; keep it open so the lazy generator can seek through remaining frames
  with PILImage.open(old_path) as img:
    n_frames: int = getattr(img, 'n_frames', 1)
    if n_frames < 1:
      raise Error(f'GIF file has no frames: {old_path}')
    # read the first frame; duration is assumed uniform since WriteAnimatedGIF() uses a single value
    img.seek(0)
    first_frame: PILImage.Image = img.copy()
    frame_duration: int = int(img.info.get('duration', 100))  # ms per frame, assumed uniform

    def _RemainingFrames() -> abc.Iterator[PILImage.Image]:
      # yield frame copies one at a time so we never hold more than one extra frame in memory
      for i in range(1, n_frames):
        img.seek(i)
        yield img.copy()

    # re-save streaming frames lazily; PIL processes each frame before the generator advances
    first_frame.save(
      # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif
      new_path,
      save_all=True,
      append_images=_RemainingFrames(),
      duration=frame_duration,  # uniform per-frame duration in milliseconds
      loop=loop,
      disposal=1,  # 1 == do not dispose, overwrite
      optimize=True,
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
    frames (abc.Iterable[bytes]): An iterable (or generator) of PIL Image frames to include in
        the video. Frames are consumed lazily one at a time, so they do not need to all fit in
        memory at once.
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
    # store all metadata as a single JSON string in the 'comment' field so it can be read back;
    # ffmpeg -metadata key=value stores to format.tags which imageio doesn't expose on read
    output_params.extend(['-metadata', f'comment={json.dumps(meta)}'])
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


def ReWriteVideoMP4Meta(
  old_path: pathlib.Path, new_path: pathlib.Path, meta: dict[str, str] | None
) -> None:
  """Read old_path MP4 and re-write to new_path with the same frames and new metadata.

  We more-or-less assume the file was written with WriteVideoMP4().

  Args:
    old_path (pathlib.Path): The file path of the original MP4 to read.
    new_path (pathlib.Path): The file path to save the modified MP4.
    meta (dict[str, str] | None): Optional metadata to include in the new MP4; default None

  """
  # open the original MP4 and read the fps from its metadata
  reader = imageio.get_reader(old_path, format='ffmpeg')  # type: ignore[arg-type]
  fps: float = float(reader.get_meta_data().get('fps', 25.0))
  # prepare metadata output params, same settings as WriteVideoMP4
  output_params: list[str] = []
  output_params.extend(['-movflags', '+faststart'])  # allows start playing before fully downloaded
  output_params.extend(['-crf', '16'])  # good quality, lower is better
  output_params.extend(['-preset', 'slow'])  # slower presets give better compression
  if meta:
    # store all metadata as a single JSON string in the 'comment' field (mirrors WriteVideoMP4)
    output_params.extend(['-metadata', f'comment={json.dumps(meta)}'])
  # stream frames from reader directly into writer (no full in-memory buffering)
  with imageio.get_writer(  # pyright: ignore[reportUnknownMemberType]
    new_path,
    fps=fps,
    format='ffmpeg',  # type: ignore[arg-type]
    codec='libx264',
    pixelformat='yuv420p',
    macro_block_size=1,
    output_params=output_params,
  ) as writer:
    for frm in reader:  # type: ignore[attr-defined]
      writer.append_data(frm)  # type: ignore[attr-defined]
  reader.close()


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
