# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computation image operations for Mandelbrot/Julia rendering.

For info on the PNG format and metadata handling, see:
https://pillow.readthedocs.io/en/stable/PIL.html#PIL.PngImagePlugin.PngInfo
"""

from __future__ import annotations

import array
import bisect
import dataclasses
import json
import logging
import math
import pathlib
import struct
from collections import abc

import gmpy2
from PIL import Image as PILImage
from transcrypto.core import hashes
from transcrypto.utils import base as tbase

from tranzoom import __app__ as _app
from tranzoom.core import frame, palette, pixels

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
META_RENDER_I_PIXELS_KEY: str = f'{_app}:render:i_pixels'  # int, number of interpolated pixels
META_RENDER_OVERLAY_KEY: str = f'{_app}:render:overlay'  # image.OverlayType or "none"
META_RENDER_MARK_RE_KEY: str = f'{_app}:render:mark_re'  # gmpy2.mpq
META_RENDER_MARK_IM_KEY: str = f'{_app}:render:mark_im'  # gmpy2.mpq
META_RENDER_MARK_COLOR_KEY: str = f'{_app}:render:mark_color'  # Color.name.lower() / "none"=no mark
META_RENDER_MARK_WIDTH_KEY: str = f'{_app}:render:mark_width'  # int
META_RENDER_HASH_KEY: str = f'{_app}:render:hash'  # str, like "abcdef1234567890", a SHA256
META_IMAGE_ANIMATION_KEY: str = f'{_app}:image:animation'  # AnimationType or "none" if static image
META_IMAGE_HASH_KEY: str = pixels.META_IMAGE_HASH_KEY  # str, like "abcdef1234567890", a SHA256
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
META_ZOOM_I_FPS_KEY: str = f'{_app}:zoom:frame:ifps'  # gmpy2.mpq
META_ZOOM_I_FRAMES_KEY: str = f'{_app}:zoom:frame:i_frames'  # int
META_ZOOM_ALL_FRAMES_KEY: str = f'{_app}:zoom:frame:all_frames'  # int
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
PACK_IF = struct.Struct('>if')  # signed int32 + float32
PACK_Q = struct.Struct('>Q')  # uint64

# image constants

type ImageUInt64Array = array.array[int]  # type alias for the type of our pixel data array
_HIST_SUB_BINS: int = 2048  # number of sub-bins to use for the smooth histogram keys
_ALMOST_ONE: float = math.nextafter(1.0, 0.0)


class Error(pixels.Error):
  """Base image exception."""


# gmpy2.mpfr constants
_MPFR_ZERO: gmpy2.mpfr = gmpy2.mpfr('0')
_MPFR_ONE: gmpy2.mpfr = gmpy2.mpfr('1')


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


class Image:
  """A fractal image. Encapsulates the image operations.

  Attributes:
    escape (ImageUInt64Array): An array storing the escape data for each pixel;
        this is not the color, but the raw data that will be converted to color later;
        the length of this array is equal to the total number of pixels in the image;
        the pixel at coordinates (x, y) is stored at index (y * width + x) in the array.
    stats (FractalStats | None): Optional stats about the fractal, collected during rendering;
        DO NOT COUNT on this being present unless this was a sample 16.16 render
        (see fractal.FractalAdaptiveIterations) where the stats are collected.
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

    def InterpolateExternal(self, n: int, nu: float) -> float:
      """Get the cross-frame-stable blended palette position for an exterior (escaped) pixel.

      Args:
        n (int): The escape iteration count for the pixel.
        nu (float): The fractional escape iteration for smooth coloring.

      Returns:
        float: Blended palette position in [0, 1).

      """
      clamp: abc.Callable[[float], float] = lambda t: max(0.0, min(_ALMOST_ONE, t))
      # previous, and trivial bottom case
      t_prev: float = self.prev_ext.InterpolateBucket(n, nu) if self.prev_ext.count > 0 else 0.0
      if self.alpha <= 0.0:
        return clamp(t_prev)
      # next, and trivial top case
      t_next: float = self.next_ext.InterpolateBucket(n, nu) if self.next_ext.count > 0 else 0.0
      if self.alpha >= 1.0:
        return clamp(t_next)
      # we are in the middle, so blend
      return clamp(t_prev + self.alpha * (t_next - t_prev))

    def InterpolateInternal(self, key: int, remainder: float) -> float:
      """Get the cross-frame-stable blended palette position for an interior (Set) pixel.

      Args:
        key (int): The positive interior key (the negated stored escape value: -escaped_at).
        remainder (float): The fractional part of the interior key, used for smooth coloring.

      Returns:
        float: Blended palette position in [0, 1).

      """
      clamp: abc.Callable[[float], float] = lambda t: max(0.0, min(_ALMOST_ONE, t))
      # previous, and trivial bottom case
      t_prev: float = (
        self.prev_int.InterpolateBucket(key, remainder) if self.prev_int.count > 0 else 0.0
      )
      if self.alpha <= 0.0:
        return clamp(t_prev)
      # next, and trivial top case
      t_next: float = (
        self.next_int.InterpolateBucket(key, remainder) if self.next_int.count > 0 else 0.0
      )
      if self.alpha >= 1.0:
        return clamp(t_next)
      # we are in the middle, so blend
      return clamp(t_prev + self.alpha * (t_next - t_prev))

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

  def AsPixels(
    self, render: pixels.RenderParameters, *, zoom_norm: FrameColorNorm | None = None
  ) -> bytes:
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
      render (pixels.RenderParameters): The render parameters to use for generating the PNG metadata
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
    # TODO: create a structure of numpy float32 array of shape (height, width, 3) and a metadata
    # dict[str, str] and then use it to pass around, and do overlays, and everything else to
    # stop the current madness of converting bytes->PNG->bytes->PIL->bytes->PNG->bytes->PIL->...
    # Only at the end, and only once, convert the data to PNG and add the whole metadata.
    # I think today an image has the potential of being converted 5-6x before leaving the pipeline.
    pixels = bytearray(self._params.width * self._params.height * 3)
    for i, enc_escaped_at in enumerate(self.escape):
      escaped_at, f_nu = Decode64ToIntFloat(enc_escaped_at)
      if escaped_at >= 0 and self.ext_hist.count > 0:
        # exterior point: histogram-equalized position in palette
        t_ext: float = (
          zoom_norm.InterpolateExternal(escaped_at, f_nu)
          if zoom_norm is not None
          else self.ext_hist.InterpolateBucket(escaped_at, f_nu)
        )
        rgb: tuple[int, int, int] = _PixelPalette(t_ext, render.escaped_pal)
      elif self._params.set_points and self.int_hist.count > 0 and escaped_at < 0:
        # interior (Set) point: histogram-equalized position in set_pal over |z| magnitudes
        if render.set_pal is None:
          raise Error('set_pal must be specified in RenderParameters when set_points is True')
        t_set: float = (
          zoom_norm.InterpolateInternal(-escaped_at, f_nu)  # in this case "nu" is remainder
          if zoom_norm is not None
          else self.int_hist.InterpolateBucket(-escaped_at, f_nu)  # in this case "nu" is remainder
        )
        rgb = _PixelPalette(t_set, render.set_pal)
      elif escaped_at < 0 and (not self._params.set_points or not self.int_hist.count):
        # interior point but no histogram data (e.g., all-interior image); render as black
        rgb = (0, 0, 0)
      else:
        # we should really not be getting here, but I am not bold enough to raise...
        rgb = (0, 0, 0)  # black: interior point (default) or all-interior image
        logging.error(f'Invalid {escaped_at=} at pixel {i=}; bug! report!')
      pixels[i * 3], pixels[i * 3 + 1], pixels[i * 3 + 2] = rgb
    return bytes(pixels)

  def AsPNG(
    self,
    render: pixels.RenderParameters,
    *,
    zoom_norm: FrameColorNorm | None = None,
    no_meta: bool = False,
  ) -> tuple[bytes, str]:
    """Convert the image to PNG bytes and return it with its internal data hash.

    Args:
      render (pixels.RenderParameters): The render parameters to use for generating the PNG metadata
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
    logging.debug(
      f'AsPNG: rendered {self._params.width} x {self._params.height} '
      f'{self._params.frm.fractal.value} PNG, hash {img_data_hash[:16]!r}'
    )
    return (
      pixels.PNGFromRGBImage(
        img, meta=None if no_meta else MakeImageMeta(self, render, img_data_hash)
      ),
      img_data_hash,
    )


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class FractalTaskInput:
  """Defines the input for a single Mandelbrot/Julia computation task.

  Attributes:
    params (frame.ComputationParameters): The full computation parameters for this task,
        including the frame, image dimensions, depth, and optional set points algorithm.
    progress_bar (bool): If True, this task should render a progress bar during computation.
    n_task (int): The 1-based index of this task among the total tasks.
    total_tasks (int): The total number of tasks in the computation batch.
    stats (FractalStats | None): Optional pre-collected stats from a sample run;
        if None, no sample-run stats are attached; default is None.

  """

  params: frame.ComputationParameters
  progress_bar: bool
  n_task: int
  total_tasks: int
  stats: FractalStats | None = None

  def __post_init__(self) -> None:
    """Validate parameters.

    Raises:
      Error: on error

    """
    # check task numbers
    if not (1 <= self.n_task <= self.total_tasks):
      raise Error(f'{self.n_task=} must be between 1 and {self.total_tasks}')


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class FractalTaskOutput:
  """Defines the output of a single Mandelbrot/Julia computation task.

  Attributes:
    img (Image): The completed fractal image produced by this task.
    n_task (int): The 1-based index of this task among the total tasks.
    total_tasks (int): The total number of tasks in the computation batch.

  """

  img: Image
  n_task: int
  total_tasks: int


type FractalComputation = abc.Callable[[FractalTaskInput], FractalTaskOutput]


def MakeImageMeta(img: Image, render: pixels.RenderParameters, data_hash: str) -> dict[str, str]:  # noqa: C901, PLR0912
  """Create a metadata dictionary for the image.

  Args:
    img (Image): The image for which to create metadata.
    render (pixels.RenderParameters): The render parameters used for the image.
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
    META_RENDER_I_PIXELS_KEY: str(render.i_pixels),
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
    if img.stats.min_lo is not None:
      img_meta[META_IMAGE_STATS_MIN_LO_KEY] = str(img.stats.min_lo)
    if img.stats.min_hi is not None:
      img_meta[META_IMAGE_STATS_MIN_HI_KEY] = str(img.stats.min_hi)
    if img.stats.ang_lo is not None:
      img_meta[META_IMAGE_STATS_ANG_LO_KEY] = str(img.stats.ang_lo)
    if img.stats.ang_hi is not None:
      img_meta[META_IMAGE_STATS_ANG_HI_KEY] = str(img.stats.ang_hi)
    if img.stats.imag_lo is not None:
      img_meta[META_IMAGE_STATS_IMAG_LO_KEY] = str(img.stats.imag_lo)
    if img.stats.imag_hi is not None:
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
  return pixels.PNGFromRGBImage(pixels.RGBImageFromPNG(img_data), meta=new_meta)


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
    return PACK_IF.unpack(PACK_Q.pack(x))
  except (struct.error, OverflowError) as e:
    raise Error(f'Error decoding uint64 to int and float: {e}') from e
