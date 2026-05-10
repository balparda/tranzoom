# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Image operations for Mandelbrot rendering."""

from __future__ import annotations

import array
import io

from gmpy2 import mpq
from PIL import Image as PILImage
from PIL import PngImagePlugin
from transcrypto.core import hashes
from transcrypto.utils import base as tbase

from tranzoom import __version__
from tranzoom.core import frame, palette

# metadata keys for PNG tEXt chunks; used to store the frame parameters and other info in the PNG
# keys use a "tranzoom:" namespace to avoid collisions with other metadata
# all are converted to str for storage in PNG metadata, but the original types are indicated below
META_VERSION_KEY = 'tranzoom:version'  # str, like "1.1.0"
META_IMAGE_WIDTH_KEY = 'tranzoom:image:width'  # int, in pixels
META_IMAGE_HEIGHT_KEY = 'tranzoom:image:height'  # int, in pixels
META_PALETTE_KEY = 'tranzoom:image:palette'  # str, like "blue-to-yellow-to-brown", one of Palette
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

# image constants

N_BYTES_UINT: int = 4  # we use array of unsigned ints to store pixel data
type ImageUInt32Array = array.array[int]  # type alias for the type of our pixel data array


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
        r, g, b = _PixelPalette(t, pal)
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
    img: PILImage.Image = PILImage.frombytes('RGB', (self._width, self._height), raw_img)
    # embed frame parameters as PNG tEXt metadata chunks; keys use a "tranzoom:" namespace
    png_meta = PngImagePlugin.PngInfo()
    # version
    png_meta.add_text(META_VERSION_KEY, __version__)
    # image parameters
    png_meta.add_text(META_IMAGE_WIDTH_KEY, str(self._width))
    png_meta.add_text(META_IMAGE_HEIGHT_KEY, str(self._height))
    png_meta.add_text(META_PALETTE_KEY, pal.value)
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
    png_meta.add_text(META_ITER_SEARCH_DEPTH_KEY, str(self._depth) if self._depth else '-1')
    # save to PNG bytes, hash and return
    buf = io.BytesIO()
    img.save(buf, format='PNG', pnginfo=png_meta)
    return (buf.getvalue(), hashes.Hash256(raw_img).hex())


def _PixelPalette(t: float, pal: palette.Palette) -> tuple[int, int, int]:
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
