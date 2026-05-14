# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Image operations for Mandelbrot rendering.

For info on the PNG format and metadata handling, see:
https://pillow.readthedocs.io/en/stable/PIL.html#PIL.PngImagePlugin.PngInfo
"""

from __future__ import annotations

import array
import base64
import io
import json
import math
import pathlib
import sys
import time
from typing import cast

from gmpy2 import mpq
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
META_IMAGE_WIDTH_KEY = 'tranzoom:image:width'  # int, in pixels
META_IMAGE_HEIGHT_KEY = 'tranzoom:image:height'  # int, in pixels
META_IMAGE_HASH_KEY = 'tranzoom:image:hash'  # str, like "abcdef1234567890", a SHA256
META_PALETTE_KEY = 'tranzoom:image:palette'  # str, like "sunset", one of palette.Palette
META_FRACTAL_KEY = 'tranzoom:frame:fractal'  # str, like "Mandelbrot", one of frame.Fractal
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
META_ITER_DEPTH_MIN_KEY = 'tranzoom:iter_depth:min'  # int
META_ITER_DEPTH_MAX_KEY = 'tranzoom:iter_depth:max'  # int
META_ITER_SEARCH_DEPTH_KEY = 'tranzoom:iter_depth:search'  # int, can be "-1" if unknown or not set
# extra keys added to some images only (for example, when the LLM evaluates the image)
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

# image constants

N_BYTES_UINT: int = 4  # we use array of unsigned ints to store pixel data
type ImageUInt32Array = array.array[int]  # type alias for the type of our pixel data array

# constants for drawing

_SQRT_TWO: float = math.sqrt(2)
_LINE_WIDTH: int = 3
_CIRCLE_RADIUS: int = 20
_LABEL_OFFSET: int = 5
_COLOR_WHITE: tuple[int, int, int] = (255, 255, 255)
_COLOR_GREEN: tuple[int, int, int] = (0, 255, 0)


class Error(frame.Error):
  """Base image exception."""


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
    self.escape: ImageUInt32Array = array.array('I', (0 for _ in range(width * height)))
    if self.escape.itemsize != N_BYTES_UINT:
      raise Error(f'unsupported platform: array of unsigned ints is not {N_BYTES_UINT} bytes')

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
  def escape_range(self) -> tuple[int, int]:
    """Get the range of escape iterations in the image.

    Returns:
      tuple[int, int]: A tuple containing the minimum and maximum escape iterations in the image.

    """
    return (min(self.escape), max(self.escape))

  def SetDepth(self, depth: int) -> None:
    """Set the maximum iteration depth for the image. Should be called after image is complete.

    Args:
      depth (int): The maximum iteration depth.

    Raises:
      Error: if the depth is invalid or inconsistent with the escape iterations.

    """
    _, max_escape = self.escape_range
    if depth < max_escape:
      raise Error(f'Inconsistent depth: {depth=} is < than {max_escape=}')
    self._depth = depth

  def AsPixels(self, *, pal: palette.Palette = palette.DEFAULT_PALETTE) -> bytes:
    """Convert the image to raw pixel bytes using histogram-equalized smooth color palette.

    Current palette:
    - black for interior points (never escape)
    - smooth multi-stop cycling gradient, histogram-equalized across escape iterations

    Interior points (that never escaped, i.e., escaped_at == max_iter) are rendered as
    pure black. Exterior points are colored by mapping their escape iteration through a
    cumulative histogram distribution (histogram equalization) into [0, 1), which is then
    fed into a smooth cycling color gradient via (_PixelPalette). This ensures the full
    color range is used regardless of zoom depth or iteration distribution.

    Args:
      pal (palette.Palette, optional): The color palette to use. Defaults to DEFAULT_PALETTE.

    Returns:
      bytes: Raw pixel data in RGB format (3 bytes per pixel).

    Raises:
      Error: on error

    """
    # step 1: build histogram of escape iterations for exterior pixels only
    histogram: dict[int, int] = {}
    min_escape: int
    max_escape: int
    min_escape, max_escape = self.escape_range
    depth: int = self._depth if self._depth is not None else max_escape
    if min_escape < 0 or depth < max_escape:
      raise Error(f'Invalid/Inconsistent {min_escape=} or {depth=} < {max_escape=}')
    for escaped_at in self.escape:
      if escaped_at < depth:
        histogram[escaped_at] = histogram.get(escaped_at, 0) + 1
    total_exterior: int = sum(histogram.values())
    # step 2: compute cumulative distribution function for histogram equalization;
    # cumulative[v] = number of exterior pixels with escape value <= v
    cumulative: dict[int, int] = {}
    cum: int = 0
    for v in sorted(histogram):
      cum += histogram[v]
      cumulative[v] = cum
    # step 3: map each pixel to an RGB color
    r: int
    g: int
    b: int
    pixels = bytearray(self._width * self._height * 3)
    for i, escaped_at in enumerate(self.escape):
      if escaped_at >= depth or total_exterior == 0:
        r, g, b = 0, 0, 0  # interior point: black
      else:
        # keep t in [0, 1) so the highest escape bucket does not wrap
        t: float = (cumulative[escaped_at] - 1) / total_exterior
        r, g, b = PixelPalette(t, pal)
      pixels[i * 3] = r
      pixels[i * 3 + 1] = g
      pixels[i * 3 + 2] = b
    return bytes(pixels)

  def AsPNG(self, *, pal: palette.Palette = palette.DEFAULT_PALETTE) -> tuple[bytes, str]:
    """Convert the image to PNG bytes and return it with its internal data hash.

    Args:
      pal (palette.Palette, optional): The color palette to use. Defaults to DEFAULT_PALETTE.

    Returns:
      tuple[bytes, str]: PNG image data and its internal data hash.

    """
    # convert the raw pixel data to a PNG using PIL
    raw_img: bytes = self.AsPixels(pal=pal)
    img_data_hash: str = hashes.Hash256(raw_img).hex()
    img: PILImage.Image = PILImage.frombytes('RGB', (self._width, self._height), raw_img)
    # embed frame parameters as PNG tEXt metadata chunks; keys use a "tranzoom:" namespace
    png_meta = PngImagePlugin.PngInfo()
    # version
    png_meta.add_text(META_VERSION_KEY, __version__)
    # image parameters
    png_meta.add_text(META_IMAGE_WIDTH_KEY, str(self._width))
    png_meta.add_text(META_IMAGE_HEIGHT_KEY, str(self._height))
    png_meta.add_text(META_IMAGE_HASH_KEY, img_data_hash)
    png_meta.add_text(META_PALETTE_KEY, pal.value)
    # frame type
    png_meta.add_text(META_FRACTAL_KEY, self._frame.fractal.value)
    # frame as corners
    png_meta.add_text(META_TOP_RE_KEY, str(self._frame.top_re))
    png_meta.add_text(META_TOP_IM_KEY, str(self._frame.top_im))
    png_meta.add_text(META_BOTTOM_RE_KEY, str(self._frame.bottom_re))
    png_meta.add_text(META_BOTTOM_IM_KEY, str(self._frame.bottom_im))
    # frame as center + size
    center: tuple[mpq, mpq] = self._frame.center
    sz: tuple[mpq, mpq] = self._frame.size
    png_meta.add_text(META_CENTER_RE_KEY, str(center[0]))
    png_meta.add_text(META_CENTER_IM_KEY, str(center[1]))
    png_meta.add_text(META_WIDTH_RE_KEY, str(sz[0]))
    png_meta.add_text(META_HEIGHT_IM_KEY, str(sz[1]))
    # precision and magnification
    png_meta.add_text(META_PRECISION_KEY, str(self._frame.precision))
    magnification, magnitude = self._frame.magnification
    png_meta.add_text(META_MAGNIFICATION_KEY, str(float(magnification)))  # huge if not converted!
    png_meta.add_text(META_MAGNIFICATION_ORDER_KEY, str(magnitude))
    # escape iteration range in the image
    min_escape: int
    max_escape: int
    min_escape, max_escape = self.escape_range
    png_meta.add_text(META_ITER_DEPTH_MIN_KEY, str(min_escape))
    png_meta.add_text(META_ITER_DEPTH_MAX_KEY, str(max_escape))
    png_meta.add_text(
      META_ITER_SEARCH_DEPTH_KEY, str(self._depth) if self._depth is not None else '-1'
    )
    # save to PNG bytes, hash and return
    buf = io.BytesIO()
    img.save(buf, format='PNG', pnginfo=png_meta)
    return (buf.getvalue(), img_data_hash)


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
  - line width and circle radius are fixed
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
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
    # draw the quadrant lines
    draw: ImageDraw.ImageDraw = ImageDraw.ImageDraw(img)
    w, h = img.size
    cx, cy = w // 2, h // 2
    step_sz: int = w // frame.DEFAULT_STEP_DIRECT
    draw.line((0, cy, w, cy), fill=_COLOR_WHITE, width=_LINE_WIDTH)
    draw.line((cx, 0, cx, h), fill=_COLOR_WHITE, width=_LINE_WIDTH)
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
        outline=_COLOR_GREEN,
        width=_LINE_WIDTH,
      )
      # for each circle, also draw the label text
      draw.text((x - _LABEL_OFFSET, y - _LABEL_OFFSET), direction, fill=_COLOR_GREEN, font=font)
    # done
    return SaveWithMeta(img)


def DrawThirdsInfoOverlay(img_data: bytes) -> bytes:
  """Draw an overlay on the (512x512) image with target info for moving the zoom frame.

  Overlays:
  - white lines delimiting the 9 sections of the image
  - large green number labels (1-9) centered in each section, left-to-right, top-to-bottom

  Works on any size image apart from the fixed line size. The text labels scale.

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
  # open the image
  with PILImage.open(io.BytesIO(img_data)) as img:
    # draw the thirds lines
    draw: ImageDraw.ImageDraw = ImageDraw.ImageDraw(img)
    w, h = img.size
    cx, cy = w // 3, h // 3
    draw.line((0, cy, w, cy), fill=_COLOR_WHITE, width=_LINE_WIDTH)
    draw.line((0, 2 * cy, w, 2 * cy), fill=_COLOR_WHITE, width=_LINE_WIDTH)
    draw.line((cx, 0, cx, h), fill=_COLOR_WHITE, width=_LINE_WIDTH)
    draw.line((2 * cx, 0, 2 * cx, h), fill=_COLOR_WHITE, width=_LINE_WIDTH)
    # draw large number labels centered in each of the 9 sections, left-to-right, top-to-bottom
    label_font: ImageFont.FreeTypeFont = cast(
      'ImageFont.FreeTypeFont', ImageFont.load_default(size=int(min(cx, cy) / 3))
    )
    for row in range(3):
      for col in range(3):
        draw.text(
          (col * cx + cx // 2, row * cy + cy // 2),  # center of this section
          str(row * 3 + col + 1),  # label
          fill=_COLOR_GREEN,
          font=label_font,
          anchor='mm',  # center it exactly
        )
    # done
    return SaveWithMeta(img)


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


def PixelPalette(t: float, pal: palette.Palette) -> tuple[int, int, int]:
  """Get the RGB color for a histogram-equalized normalized palette position.

  Smoothly interpolates between adjacent stops in the specified palette, cycling
  _PALETTE_CYCLES times across the [0, 1) range for visual banding.

  Args:
    t (float): Normalized position in [0, 1) derived from histogram equalization.
    pal (Palette): The palette to use.

  Returns:
    tuple[int, int, int]: The interpolated RGB color.

  Raises:
    Error: if the palette name is unknown or if there are issues computing the color.

  """
  # get the palette stops
  if pal not in palette.PALETTES:
    raise Error(f'Unknown palette {pal!r}, available: {list(palette.PALETTES.keys())}')
  palette_stops: tuple[tuple[int, int, int], ...] = palette.PALETTES[pal]
  # cycle multiple times through the palette for visual banding
  t_cycled: float = (t * palette.PALETTE_CYCLES) % 1.0
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
