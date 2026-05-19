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
import math
import pathlib
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

from tranzoom import __version__
from tranzoom.core import frame, palette

# metadata keys for PNG tEXt chunks; used to store the frame parameters and other info in the PNG
# keys use a "tranzoom:" namespace to avoid collisions with other metadata
# all are converted to str for storage in PNG metadata, but the original types are indicated below
META_VERSION_KEY = 'tranzoom:version'  # str, like "1.1.0"
META_DATETIME_KEY = 'tranzoom:datetime'  # str, format '%Y/%b/%d-%H:%M:%S-UTC'
META_IMAGE_WIDTH_KEY = 'tranzoom:image:width'  # int, in pixels
META_IMAGE_HEIGHT_KEY = 'tranzoom:image:height'  # int, in pixels
META_IMAGE_HASH_KEY = 'tranzoom:image:hash'  # str, like "abcdef1234567890", a SHA256
META_ITER_DEPTH_MIN_KEY = 'tranzoom:image:iter_depth:min'  # int
META_ITER_DEPTH_MAX_KEY = 'tranzoom:image:iter_depth:max'  # int
META_ITER_SEARCH_DEPTH_KEY = 'tranzoom:image:iter_depth:search'  # int, can be "-1" if unknown/unset
META_SET_POINT_MIN_KEY = 'tranzoom:image:set_point:min'  # int
META_SET_POINT_MAX_KEY = 'tranzoom:image:set_point:max'  # int
META_IMAGE_PALETTE_KEY = 'tranzoom:image:palette'  # str, like "sunset", one of palette.Palette
META_IMAGE_SET_PALETTE_KEY = 'tranzoom:image:set_palette'  # str, interior Set palette name
META_IMAGE_COLOR_SET_KEY = 'tranzoom:image:color_set'  # frame.SetHighlightAlgorithm or "none"
META_IMAGE_OVERLAY_KEY = 'tranzoom:image:overlay'  # bool; stored as "true"/"false"
META_PIXEL_EXTERIOR_COUNT_KEY = 'tranzoom:image:exterior:pixel_count'  # int; count escaped
META_PIXEL_INTERIOR_COUNT_KEY = 'tranzoom:image:interior:pixel_count'  # int; count set
META_PIXEL_EXTERIOR_HISTOGRAM_KEY = 'tranzoom:image:exterior:histogram_summary'  # str
META_PIXEL_INTERIOR_HISTOGRAM_KEY = 'tranzoom:image:interior:histogram_summary'  # str; can be ""!
META_PIXEL_EXTERIOR_CUMULATIVE_HISTOGRAM_KEY = (
  'tranzoom:image:exterior:cumulative_histogram_summary'  # str
)
META_PIXEL_INTERIOR_CUMULATIVE_HISTOGRAM_KEY = (
  'tranzoom:image:interior:cumulative_histogram_summary'  # str; can be ""!
)
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
META_MAGNIFICATION_KEY = 'tranzoom:frame:magnification'  # gmpy2.mpfr -> converted to float
META_MAGNIFICATION_ORDER_KEY = 'tranzoom:frame:magnification_order'  # float
# extra keys added to some images only (for example, when the LLM evaluates the image)
META_JULIA_RE_KEY = 'tranzoom:frame:julia_re'  # gmpy2.mpq, only added for Julia Set frames
META_JULIA_IM_KEY = 'tranzoom:frame:julia_im'  # gmpy2.mpq, only added for Julia Set frames
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

# TODO: animated gif or videos of zooms

# image constants

type ImageInt32Array = array.array[int]  # type alias for the type of our pixel data array

# constants for drawing

_SQRT_TWO: float = math.sqrt(2)
_LINE_WIDTH_RATIO: int = 150  # line width will be max(1, sz//_LINE_WIDTH_RATIO) of the image width
_CIRCLE_RADIUS: int = 20
_LABEL_OFFSET: int = 5
# scale factor for converting stored Set interior integers back to |z| float magnitudes;
# interior points are stored as -(int(floor(scale * |z|)) + 1), with scale = RES / MAX_Z = RES / 2
_SET_INTERIOR_SCALE: float = float(frame.MPFR_SET_INTERIOR_SCALE)


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


# color constants


DEFAULT_MARK_COLOR: Color = Color.RED
DEFAULT_MARK_WIDTH: int = 1
MIN_MARK_WIDTH: int = 1
MAX_MARK_WIDTH: int = 50


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


class Image:
  """A fractal image. Encapsulates the image operations.

  Attributes:
    escape (ImageUInt32Array): An array storing the escape iteration for each pixel;
        this is not the color, but the raw data that will be converted to color later;
        the length of this array is equal to the total number of pixels in the image.
        You are encouraged to use the SetEscape() method to set the escape iterations,
        but for hot paths you can also set the escape iterations directly in the array,
        remembering that the pixel at coordinates (x, y) is stored at index (y * width + x)
        in the array.
    stats (FractalStats | None): Optional stats about the fractal, collected during rendering;
        DO NOT COUNT on this being present unless this was a sample 16.16 render
        (see fractal._FractalAdaptiveIterations) where the stats are collected

  """

  def __init__(self, frm: frame.Frame, width: int, height: int) -> None:
    """Construct image.

    Args:
      frm (Frame): The frame to render.
      width (int): The width of the output image in pixels.
      height (int): The height of the output image in pixels.

    Raises:
      Error: on error

    """
    # check parameters
    if not (frame.MIN_IMAGE_SIZE <= width <= frame.MAX_IMAGE_SIZE) or not (
      frame.MIN_IMAGE_SIZE <= height <= frame.MAX_IMAGE_SIZE
    ):
      raise Error(
        f'{width=} and {height=} must be between {frame.MIN_IMAGE_SIZE} and {frame.MAX_IMAGE_SIZE}'
      )
    # save objects
    self._frame: frame.Frame = frm
    self._width: int = width
    self._height: int = height
    self._depth: int | None = None  # may be set later by the fractal rendering function
    # initialize image data array; self._escape stores the ESCAPE ITERATION data, not the color
    self.escape: ImageInt32Array = array.array('i', (0 for _ in range(width * height)))  # signed32
    if self.escape.itemsize != frame.N_BYTES_UINT:
      raise Error(f'unsupported platform: array of unsigned ints is not {frame.N_BYTES_UINT} bytes')
    self.stats: FractalStats | None = None  # may be set later by the fractal rendering function

  def SetEscape(self, x: int, y: int, escaped_at: int) -> None:
    """Set the escape iteration for a given pixel.

    Args:
      x (int): The x coordinate of the pixel.
      y (int): The y coordinate of the pixel.
      escaped_at (int): The escape iteration to set for the pixel.

    Raises:
      Error: if the pixel coordinates are out of bounds or if the escape iteration is invalid

    """
    if not (0 <= x < self._width) or not (0 <= y < self._height):
      raise Error(f'Pixel coordinates out of bounds: {x=}, {y=}, {self._width=}, {self._height=}')
    if escaped_at < 0:
      raise Error(f'Invalid escape iteration: {escaped_at=}')
    self.escape[y * self._width + x] = escaped_at

  @property
  def escape_range(self) -> tuple[int, int, int, int]:
    """Get the range of escape iterations and set max_|z| in the image.

    Returns:
      tuple[int, int, int, int]: (min_escape, max_escape, min_|z|, max_|z|)

    """
    exterior_points: list[int] = [e for e in self.escape if e >= 0]
    interior_points: list[int] = [e for e in self.escape if e < 0]
    return (
      min(exterior_points) if exterior_points else 0,
      self._depth
      if interior_points and self._depth
      else (max(exterior_points) if exterior_points else 0),
      -max(interior_points) if interior_points else 0,
      -min(interior_points) if interior_points else 0,
    )

  @property
  def precision(self) -> int:
    """Estimate the MPFR precision needed to render this image. See Frame.Precision() for details.

    Returns:
      int: The estimated number of bits of MPFR precision needed.

    """
    return self._frame.Precision(
      self._width, self._height, max_iter=self._depth or frame.DEFAULT_ITER
    )

  @property
  def context(self) -> gmpy2.context:
    """Get gmpy2 context with precision to distinguish adjacent pixels in smaller complex-plane dim.

    Returns:
      gmpy2.context: A context with the estimated number of bits of precision needed.

    """
    return gmpy2.local_context(gmpy2.context(), precision=self.precision)

  def SetDepth(self, depth: int) -> None:
    """Set the maximum iteration depth for the image. Should be called after image is complete.

    Args:
      depth (int): The maximum iteration depth.

    Raises:
      Error: if the depth is invalid or inconsistent with the escape iterations.

    """
    _, max_escape, _, _ = self.escape_range
    if depth < max_escape:
      raise Error(f'Inconsistent depth: {depth=} is < than {max_escape=}')
    self._depth = depth

  def AsPixels(
    self,
    *,
    pal: palette.Palette = palette.DEFAULT_PALETTE,
    set_pal: palette.Palette = palette.DEFAULT_SET_PALETTE,
    set_points: frame.SetHighlightAlgorithm | None = None,
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

    Args:
      pal (palette.Palette, optional): The color palette for exterior (escaped) pixels.
          Defaults to DEFAULT_PALETTE.
      set_pal (palette.Palette, optional): The color palette for interior Set points; only
          used when `color_set_points=True`. Defaults to DEFAULT_SET_PALETTE.
      set_points (frame.SetHighlightAlgorithm | None, optional): Which algorithm to use for coloring
          interior Set points, either None, or one of the SetHighlightAlgorithm values; default is
          None, do not color the Set points (i.e., they will be black).

    Returns:
      bytes: Raw pixel data in RGB format (3 bytes per pixel).

    Raises:
      Error: on error

    """
    # step 1: build cumulative histogram for exterior pixels (escaped, 0 <= e < depth)
    min_escape: int
    max_escape: int
    total_exterior: int
    cumulative: dict[int, int]
    min_escape, max_escape, _, _ = self.escape_range
    depth: int = self._depth if self._depth is not None else max_escape
    if min_escape < 0 or depth < max_escape:
      raise Error(f'Invalid/Inconsistent {min_escape=} or {depth=} < {max_escape=}')
    _, cumulative, total_exterior = BuildCumulative([e for e in self.escape if 0 <= e < depth])
    # step 2: optionally build cumulative histogram for interior/Set pixels (escaped_at < 0);
    # interior points store -|z| magnitude, so we flip the sign for the histogram key
    set_cumulative: dict[int, int] = {}
    total_set: int = 0
    if set_points:
      _, set_cumulative, total_set = BuildCumulative([-e for e in self.escape if e < 0])
    # step 3: map each pixel to an RGB color
    pixels = bytearray(self._width * self._height * 3)
    for i, escaped_at in enumerate(self.escape):
      if 0 <= escaped_at < depth and total_exterior > 0:
        # exterior point: histogram-equalized position in pal
        t: float = (cumulative[escaped_at] - 1) / total_exterior
        rgb: tuple[int, int, int] = PixelPalette(t, pal, palette.PALETTE_CYCLES)
      elif set_points and total_set > 0 and escaped_at < 0:
        # interior (Set) point: histogram-equalized position in set_pal over |z| magnitudes
        t_set: float = (set_cumulative[-escaped_at] - 1) / total_set
        rgb = PixelPalette(t_set, set_pal, palette.SET_PALETTE_CYCLES)
      else:
        rgb = (0, 0, 0)  # black: interior point (default) or all-interior image
      pixels[i * 3], pixels[i * 3 + 1], pixels[i * 3 + 2] = rgb
    return bytes(pixels)

  def AsPNG(  # noqa: PLR0914, PLR0915
    self,
    *,
    pal: palette.Palette = palette.DEFAULT_PALETTE,
    set_pal: palette.Palette = palette.DEFAULT_SET_PALETTE,
    set_points: frame.SetHighlightAlgorithm | None = None,
  ) -> tuple[bytes, str]:
    """Convert the image to PNG bytes and return it with its internal data hash.

    Args:
      pal (palette.Palette, optional): The color palette to use. Defaults to DEFAULT_PALETTE.
      set_pal (palette.Palette, optional): The color palette for interior Set points.
          Defaults to DEFAULT_SET_PALETTE.
      set_points (frame.SetHighlightAlgorithm | None, optional): Which algorithm to use for coloring
          interior Set points, either None, or one of the SetHighlightAlgorithm values; default is
          None, do not color the Set points (i.e., they will be black).

    Returns:
      tuple[bytes, str]: PNG image data and its internal data hash.

    Raises:
      Error: on error

    """
    # convert the raw pixel data to a PNG using PIL
    raw_img: bytes = self.AsPixels(pal=pal, set_pal=set_pal, set_points=set_points)
    img_data_hash: str = hashes.Hash256(raw_img).hex()
    img: PILImage.Image = PILImage.frombytes('RGB', (self._width, self._height), raw_img)
    # embed frame parameters as PNG tEXt metadata chunks; keys use a "tranzoom:" namespace
    png_meta = PngImagePlugin.PngInfo()
    # version / date
    png_meta.add_text(META_VERSION_KEY, __version__)
    png_meta.add_text(META_DATETIME_KEY, timer.StrNow())
    # image parameters
    png_meta.add_text(META_IMAGE_WIDTH_KEY, str(self._width))
    png_meta.add_text(META_IMAGE_HEIGHT_KEY, str(self._height))
    png_meta.add_text(META_IMAGE_HASH_KEY, img_data_hash)
    png_meta.add_text(META_IMAGE_PALETTE_KEY, pal.value)
    png_meta.add_text(META_IMAGE_SET_PALETTE_KEY, set_pal.value)
    png_meta.add_text(META_IMAGE_COLOR_SET_KEY, str(set_points.value) if set_points else 'none')
    png_meta.add_text(META_IMAGE_OVERLAY_KEY, 'false')  # if it comes from this, it has no overlay
    # frame type
    png_meta.add_text(META_FRACTAL_KEY, self._frame.fractal.value.lower())
    if self._frame.fractal == frame.Fractal.JULIA:
      if not isinstance(self._frame, frame.FrameAndPoint):
        raise Error(f'Expected FrameAndPoint for Julia Set frame, got {type(self._frame)}')
      png_meta.add_text(META_JULIA_RE_KEY, str(self._frame.point_re))
      png_meta.add_text(META_JULIA_IM_KEY, str(self._frame.point_im))
    # frame as corners
    png_meta.add_text(META_TOP_RE_KEY, str(self._frame.top_re))
    png_meta.add_text(META_TOP_IM_KEY, str(self._frame.top_im))
    png_meta.add_text(META_BOTTOM_RE_KEY, str(self._frame.bottom_re))
    png_meta.add_text(META_BOTTOM_IM_KEY, str(self._frame.bottom_im))
    # frame as center + size
    center: tuple[gmpy2.mpq, gmpy2.mpq] = self._frame.center
    sz: tuple[gmpy2.mpq, gmpy2.mpq] = self._frame.size
    png_meta.add_text(META_CENTER_RE_KEY, str(center[0]))
    png_meta.add_text(META_CENTER_IM_KEY, str(center[1]))
    png_meta.add_text(META_WIDTH_RE_KEY, str(sz[0]))
    png_meta.add_text(META_HEIGHT_IM_KEY, str(sz[1]))
    # precision and magnification
    png_meta.add_text(META_PRECISION_KEY, str(self.precision))
    magnification, magnitude = self._frame.magnification
    png_meta.add_text(META_MAGNIFICATION_KEY, str(float(magnification)))  # huge if not converted!
    png_meta.add_text(META_MAGNIFICATION_ORDER_KEY, str(magnitude))
    # escape iteration range in the image
    min_escape: int
    max_escape: int
    min_set: int
    max_set: int
    min_escape, max_escape, min_set, max_set = self.escape_range
    png_meta.add_text(META_ITER_DEPTH_MIN_KEY, str(min_escape))
    png_meta.add_text(META_ITER_DEPTH_MAX_KEY, str(max_escape))
    png_meta.add_text(META_SET_POINT_MIN_KEY, str(min_set))
    png_meta.add_text(META_SET_POINT_MAX_KEY, str(max_set))
    png_meta.add_text(
      META_ITER_SEARCH_DEPTH_KEY, str(self._depth) if self._depth is not None else '-1'
    )
    # pixel counts and histograms; exterior pixels have escape >= 0, interior (Set) have escape < 0
    depth: int = self._depth if self._depth is not None else max_escape
    hist: dict[int, int]
    cumulative: dict[int, int]
    total: int
    hist, cumulative, total = BuildCumulative([e for e in self.escape if 0 <= e < depth])
    png_meta.add_text(META_PIXEL_EXTERIOR_HISTOGRAM_KEY, SummaryHistogram(sorted(hist.items())))
    png_meta.add_text(
      META_PIXEL_EXTERIOR_CUMULATIVE_HISTOGRAM_KEY, SummaryHistogram(sorted(cumulative.items()))
    )
    png_meta.add_text(META_PIXEL_EXTERIOR_COUNT_KEY, str(total))
    if set_points:
      hist, cumulative, total = BuildCumulative([-e for e in self.escape if e < 0])
      png_meta.add_text(META_PIXEL_INTERIOR_HISTOGRAM_KEY, SummaryHistogram(sorted(hist.items())))
      png_meta.add_text(
        META_PIXEL_INTERIOR_CUMULATIVE_HISTOGRAM_KEY, SummaryHistogram(sorted(cumulative.items()))
      )
      png_meta.add_text(META_PIXEL_INTERIOR_COUNT_KEY, str(total))
    else:
      png_meta.add_text(META_PIXEL_INTERIOR_HISTOGRAM_KEY, '')
      png_meta.add_text(META_PIXEL_INTERIOR_CUMULATIVE_HISTOGRAM_KEY, '')
      png_meta.add_text(META_PIXEL_INTERIOR_COUNT_KEY, str(len([1 for e in self.escape if e < 0])))
    # save to PNG bytes, hash and return
    buf = io.BytesIO()
    img.save(buf, format='PNG', pnginfo=png_meta)
    return (buf.getvalue(), img_data_hash)


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
  filename += '.png'
  return pathlib.Path(filename) if img_output_path is None else img_output_path / filename


def GetBasicDataFromPNG(img_bytes: bytes) -> tuple[int, int, str, tbase.JSONDict]:
  """Get basic data from a PNG image, including format, size, hash, and metadata text.

  Args:
    img_bytes: The PNG image data as bytes.

  Returns:
    (width, height, hash, metadata) where:
      - width: The width of the image in pixels.
      - height: The height of the image in pixels.
      - hash: A hash of the image data (SHA256 of RGB bytes).
      - metadata: The extracted metadata from the image.

  Raises:
    Error: If the image format is unsupported or if there are issues processing the image.

  """
  with PILImage.open(io.BytesIO(img_bytes)) as img:
    # make sure format is PNG
    if (img.format or '').upper() != 'PNG':
      raise Error(f'Unsupported image format {img.format!r}, expected PNG')
    # get the internal data we need (size and hash)
    width: int = img.width
    height: int = img.height
    if width < 1 or height < 1:
      raise Error(f'Invalid image size {width}x{height}')
    raw_hash: str = hashes.Hash256(img.convert('RGB').tobytes()).hex()  # not 'RGBA'!!
    # extract metadata from PNG
    pil_info: tbase.JSONDict = img.info  # type: ignore[assignment]
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
    img_data: The PNG image data as bytes.

  Returns:
    The modified PNG image data with the overlay drawn.

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
    return SaveWithMeta(img, extra_meta={META_IMAGE_OVERLAY_KEY: 'true'})


def DrawThirdsInfoOverlay(img_data: bytes) -> bytes:
  """Draw an overlay on an image of any size, with target info for moving the zoom frame.

  Overlays:
  - white lines delimiting the 9 sections of the image
  - large green number labels (1-9) centered in each section, left-to-right, top-to-bottom

  Args:
    img_data: The PNG image data as bytes.

  Returns:
    The modified PNG image data with the overlay drawn.

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
    return SaveWithMeta(img, extra_meta={META_IMAGE_OVERLAY_KEY: 'true'})


def DrawCrossOverlay(
  img_data: bytes, x: int, y: int, *, col: Color = DEFAULT_MARK_COLOR, lw: int = DEFAULT_MARK_WIDTH
) -> bytes:
  """Draw a cross overlay on an image at the specified coordinates.

  Overlays:
  - a horizontal line spanning the image at the given y-coordinate
  - a vertical line spanning the image at the given x-coordinate

  Args:
    img_data: The PNG image data as bytes.
    x: The x-coordinate of the center of the cross.
    y: The y-coordinate of the center of the cross.
    col: The color of the cross.
    lw: The line width of the cross.

  Returns:
    The modified PNG image data with the overlay drawn.

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
    return SaveWithMeta(img, extra_meta={META_IMAGE_OVERLAY_KEY: 'true'})


def SaveWithMeta(img: PILImage.Image, *, extra_meta: dict[str, str] | None = None) -> bytes:
  """Save a PIL image to PNG bytes, including its metadata.

  Args:
    img: The PIL image to save.
    extra_meta: Optional additional metadata to include in the PNG.

  Returns:
    The PNG image data as bytes.

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
    img_data: The original PNG image data as bytes.
    response: The LLM evaluation response to add to the metadata.
    model: The LLM model used for evaluation; if this is "HUMAN"/META_LLM_MODEL_VALUE_HUMAN,
        then it will not add temperature, seed, reason, query_memory, query_setup, query_image, nor
        query_manual to the metadata.
    temperature: The temperature setting used for the LLM evaluation.
    seed: The random seed used for the LLM evaluation.
    reason: Whether the LLM response includes reasoning steps
    query_memory: The memory parameter used for the LLM evaluation.
    query_setup: The setup query given to the LLM.
    query_image: The image query given to the LLM.
    query_manual: The manual query passed as extra into the query.
    count: The zoom step count at which this evaluation was made.

  Returns:
    The modified PNG image data as bytes, with the evaluation info added to the metadata.

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
    img_data: The original PNG image data as bytes.

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


def BuildCumulative(values: list[int]) -> tuple[dict[int, int], dict[int, int], int]:
  """Build a raw histogram and cumulative histogram from a pre-filtered list of integer values.

  Args:
    values (list[int]): The list of integer values to histogram.

  Returns:
    tuple[dict[int, int], dict[int, int], int]: (histogram, cumulative, total) where
        histogram[v] = count of occurrences of value v, cumulative[v] = count of values ≤ v,
        and total = len(values).

  """
  # build the raw histogram
  histogram: dict[int, int] = {}
  for v in values:
    histogram[v] = histogram.get(v, 0) + 1
  # build the cumulative histogram by iterating over the sorted keys of the raw histogram
  total: int = len(values)
  cumulative: dict[int, int] = {}
  cum: int = 0
  for v in sorted(histogram):
    cum += histogram[v]
    cumulative[v] = cum
  return (histogram, cumulative, total)


def WriteAnimatedGIF(
  frames: abc.Iterable[PILImage.Image],
  path: pathlib.Path,
  width: int,
  height: int,
  fps: float,
  loop: int = 0,  # 0 == infinite loop
) -> None:
  """Write PIL Image frames to an animated GIF.

  Args:
    frames: An iterable of PIL Image frames to include in the GIF.
    path: The file path to save the GIF.
    width: The width of the GIF frames.
    height: The height of the GIF frames.
    fps: The frames per second for the GIF.
    loop: The number of times to loop the GIF (0 for infinite loop).


  Raises:
    Error: on error

  """
  if fps <= 0:
    raise Error('fps must be > 0')
  duration_ms: int = round(1000 / fps)
  try:
    first: PILImage.Image = next(iter(frames))
  except StopIteration:
    raise Error('frames generator produced no frames') from None

  def _Normalize(frame: PILImage.Image) -> PILImage.Image:
    if frame.size != (width, height):
      raise Error(f'frame size {frame.size} != {(width, height)}')
    return frame.convert('RGBA')

  first = _Normalize(first)
  rest: list[PILImage.Image] = [_Normalize(frame) for frame in frames]
  first.save(
    path,
    save_all=True,
    append_images=rest,
    duration=duration_ms,
    loop=loop,
    disposal=2,
  )


def WriteVideoMP4(
  frames: abc.Generator[PILImage.Image],
  path: pathlib.Path,
  width: int,
  height: int,
  fps: float,
) -> None:
  """Write PIL Image frames to an MP4 video using H.264, the most broadly compatible video format.

  Args:
    frames: A generator of PIL Image frames to include in the video.
    path: The file path to save the video.
    width: The width of the video frames.
    height: The height of the video frames.
    fps: The frames per second for the video.

  Raises:
    Error: on error

  """
  if fps <= 0:
    raise Error('fps must be > 0')
  frame_count = 0
  with imageio.get_writer(
    path,
    fps=fps,
    codec='libx264',
    pixelformat='yuv420p',
    macro_block_size=1,
  ) as writer:
    for frame in frames:
      if frame.size != (width, height):
        raise Error(f'frame size {frame.size} != {(width, height)}')
      writer.append_data(np.asarray(frame.convert('RGB')))
      frame_count += 1
  # with imageio.v3.imopen(
  #   path,
  #   'w',
  #   plugin='pyav' if False else None,
  #   extension='.mp4',
  # ) as writer:
  #   for frame in frames:
  #     if frame.size != (width, height):
  #       raise Error(f'frame size {frame.size} != {(width, height)}')
  #     writer.write(
  #       np.asarray(frame.convert('RGB')),
  #       fps=fps,
  #       codec='libx264',
  #       pixelformat='yuv420p',
  #       macro_block_size=1,
  #     )
  #     frame_count += 1
  if not frame_count:
    raise Error('frames generator produced no frames')
