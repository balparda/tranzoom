# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Image operations for Mandelbrot rendering."""

from __future__ import annotations

import array
import io

from PIL import Image as PILImage
from transcrypto.core import hashes
from transcrypto.utils import base as tbase

from tranzoom.core import frame

N_BYTES_UINT: int = 4  # we use array of unsigned ints to store pixel data
type ImageUInt32Array = array.array[int]  # type alias for the type of our pixel data array

# Smooth palette for exterior points: 16 color stops cycling through a
# blue-to-yellow-to-brown gradient (based on the classic Mandelbrot color scheme)
_SMOOTH_PALETTE: tuple[tuple[int, int, int], ...] = (
  (66, 30, 15),  # dark reddish-brown
  (25, 7, 26),  # dark violet
  (9, 1, 47),  # dark blue
  (4, 4, 73),  # deep blue
  (0, 7, 100),  # deep blue
  (12, 44, 138),  # blue
  (24, 82, 177),  # blue
  (57, 125, 209),  # light blue
  (134, 181, 229),  # very light blue
  (211, 236, 248),  # near-white blue
  (241, 233, 191),  # pale yellow
  (248, 201, 95),  # yellow
  (255, 170, 0),  # gold / orange
  (204, 128, 0),  # dark orange
  (153, 87, 0),  # brown
  (106, 52, 3),  # dark brown
)

# how many times to cycle through the palette across the histogram-equalized range;
# more cycles = tighter, more frequent color banding; 3 is a visually balanced default
_PALETTE_CYCLES: int = 3


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

  def AsPixels(self) -> bytes:
    """Convert the image to raw pixel bytes using histogram-equalized smooth color palette.

    Current palette:
    - black for interior points (never escape)
    - smooth 16-color cycling gradient, histogram-equalized across escape iterations

    Interior points (that never escaped, i.e., escaped_at == max_iter) are rendered as
    pure black. Exterior points are colored by mapping their escape iteration through a
    cumulative histogram distribution (histogram equalization) into [0, 1), which is then
    fed into a smooth cycling 16-color gradient via (_PixelPalette). This ensures the full
    color range is used regardless of zoom depth or iteration distribution.

    Returns:
      bytes: Raw pixel data in RGB format (3 bytes per pixel).

    Raises:
      Error: on error

    """
    # step 1: build histogram of escape iterations for exterior pixels only
    histogram: dict[int, int] = {}
    if min_escape := min(self.escape) < 0:
      raise Error(f'Invalid min escape iteration: {min_escape=}')
    max_iter: int = max(self.escape)
    for escaped_at in self.escape:
      if escaped_at < max_iter:
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
      if escaped_at >= max_iter or total_exterior == 0:
        r, g, b = 0, 0, 0  # interior point: black
      else:
        # keep t in [0, 1) so the highest escape bucket does not wrap
        t: float = (cumulative[escaped_at] - 1) / total_exterior
        r, g, b = _PixelPalette(t)
      pixels[i * 3] = r
      pixels[i * 3 + 1] = g
      pixels[i * 3 + 2] = b
    return bytes(pixels)

  def AsPNG(self) -> tuple[bytes, str]:
    """Convert the image to PNG bytes and return it with its internal data hash.

    Returns:
      tuple[bytes, str]: PNG image data and its internal data hash.

    """
    # convert the raw pixel data to a PNG using PIL
    raw_img: bytes = self.AsPixels()
    img: PILImage.Image = PILImage.frombytes('RGB', (self._width, self._height), raw_img)
    # save to PNG bytes, hash and return
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return (buf.getvalue(), hashes.Hash256(raw_img).hex())


def _PixelPalette(t: float) -> tuple[int, int, int]:
  """Get the RGB color for a histogram-equalized normalized palette position.

  Smoothly interpolates between adjacent stops in _SMOOTH_PALETTE, cycling
  _PALETTE_CYCLES times across the [0, 1) range for visual banding.

  Args:
    t (float): Normalized position in [0, 1) derived from histogram equalization.

  Returns:
    tuple[int, int, int]: The interpolated RGB color.

  """
  # cycle multiple times through the palette for visual banding
  t_cycled: float = (t * _PALETTE_CYCLES) % 1.0
  n: int = len(_SMOOTH_PALETTE)
  # fractional index into the palette
  idx: float = t_cycled * n
  lo: int = int(idx) % n
  hi: int = (lo + 1) % n
  frac: float = idx - int(idx)
  r0, g0, b0 = _SMOOTH_PALETTE[lo]
  r1, g1, b1 = _SMOOTH_PALETTE[hi]
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
