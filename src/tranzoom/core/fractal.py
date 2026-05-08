# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing.

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>
"""

from __future__ import annotations

import array
import dataclasses
import io
from collections import abc
from typing import cast

import gmpy2
import tqdm
from PIL import Image as PILImage
from transcrypto.core import hashes
from transcrypto.utils import base as tbase

# basic constants

_N_BYTES_UINT: int = 4  # we use array of unsigned ints to store pixel data
_MIN_ITER: int = 1000
DEFAULT_ITER: int = 1000
_MAX_ITER: int = 2 ** (_N_BYTES_UINT * 8) - 1  # 4_294_967_295, the max value in array('I'), uint32
_ITER_PER_MAGNITUDE: int = 400  # how much more iter per magnitude unit; this is a very naïve way!
type ImageUInt32Array = array.array[int]  # type alias for the type of our pixel data array

MIN_IMAGE_SIZE: int = 4
MAX_IMAGE_SIZE: int = 8192
DEFAULT_IMAGE_SIZE: int = 1024

# gmpy2.mpfr constants
_MPFR_MIN_PRECISION: int = 80  # about 25 decimal digits
_MPFR_BIG_PRECISION: int = 30_000  # ±10k decimal digits
_MPFR_MAX_PRECISION: int = 300_000  # ±100k decimal digits
_MPFR_MIN_GUARD_BITS: int = 64  # extra bits beyond the minimum needed to distinguish pixels
_MPFR_ZERO = gmpy2.mpfr('0')
_MPFR_SIXTEENTH = gmpy2.mpfr('0.0625')
_MPFR_FOURTH = gmpy2.mpfr('0.25')
_MPFR_ONE = gmpy2.mpfr('1')
_MPFR_TWO = gmpy2.mpfr('2')
_MPFR_FOUR = gmpy2.mpfr('4')

# gmpy2.mpfr ultra-precision context factory
PrecisionContext: abc.Callable[[], gmpy2.context] = lambda: gmpy2.local_context(
  gmpy2.context(), precision=_MPFR_BIG_PRECISION
)

# gmpy2.mpq constants
_MPQ_TWO = gmpy2.mpq(2)
_MPQ_MAX_IMAGE_SIZE = gmpy2.mpq(MAX_IMAGE_SIZE)

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


class Error(tbase.Error):
  """Base fractal exception."""


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class Frame:
  """Defines a rectangular region of the complex plane, with arbitrary precision. Exact."""

  top_re: gmpy2.mpq  # the top-left corner of the rectangle
  top_im: gmpy2.mpq
  bottom_re: gmpy2.mpq  # the bottom-right corner of the rectangle
  bottom_im: gmpy2.mpq

  def __post_init__(self) -> None:
    """Check rectangle has an area and top/bottom ordering.

    Raises:
      Error: if the rectangle is invalid.

    """
    if self.top_re >= self.bottom_re:
      raise Error(f'top_re ({self.top_re}) must be < bottom_re ({self.bottom_re})')
    if self.top_im <= self.bottom_im:
      raise Error(f'top_im ({self.top_im}) must be > bottom_im ({self.bottom_im})')

  @property
  def center(self) -> tuple[gmpy2.mpq, gmpy2.mpq]:
    """Get the center of the frame (re, im). Exact.

    Returns:
      tuple[gmpy2.mpq, gmpy2.mpq]: The center of the frame.

    """
    return ((self.top_re + self.bottom_re) / _MPQ_TWO, (self.top_im + self.bottom_im) / _MPQ_TWO)

  @property
  def size(self) -> tuple[gmpy2.mpq, gmpy2.mpq]:
    """Get the size of the frame (re, im). Exact.

    Returns:
      tuple[gmpy2.mpq, gmpy2.mpq]: The size of the frame.

    """
    return (self.bottom_re - self.top_re, self.top_im - self.bottom_im)

  @property
  def is_square(self) -> bool:
    """Check if the frame is square.

    Returns:
      bool: True if the frame is square, False otherwise.

    """
    dx, dy = self.size
    return dx == dy

  @property
  def scale(self) -> gmpy2.mpq:
    """Get the scale of the frame, i.e., the smaller dimension. Exact.

    Returns:
      gmpy2.mpq: The scale of the frame.

    """
    s: tuple[gmpy2.mpq, gmpy2.mpq] = self.size
    return min(s[0], s[1])

  @property
  def area(self) -> gmpy2.mpq:
    """Get the area of the frame. Exact.

    Returns:
      gmpy2.mpq: The area of the frame.

    """
    s: tuple[gmpy2.mpq, gmpy2.mpq] = self.size
    return s[0] * s[1]

  @property
  def magnification(self) -> tuple[gmpy2.mpfr, float]:
    """Get frame magnification: How much "zoom" this frame has in relation to the whole set.

    sqrt( DEFAULT_FRAME.area / self.area ) i.e., sqrt( WHOLE / this )

    Returns:
      tuple[gmpy2.mpfr, float]: (magnification, log10(magnification))

    """
    with PrecisionContext():
      magnification: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(DEFAULT_FRAME.area / self.area))
      return (magnification, float(cast('gmpy2.mpfr', gmpy2.log10(magnification))))

  @property
  def iterations(self) -> int:
    """Get a suggested number of (max) iterations for the frame. Very naïve implementation.

    Returns:
      int: The number of suggested (max) iterations for the frame.

    """
    # TODO: histogram-based iteration limit
    _, magnitude = self.magnification
    return int(_MIN_ITER + _ITER_PER_MAGNITUDE * magnitude) if magnitude > 0.0 else _MIN_ITER

  def __str__(self) -> str:
    """Get string representation of the frame.

    Returns:
      str: String representation of the frame.

    """
    cx, cy = self.center
    dx, dy = self.size
    return f'[({cx}, {cy}) @ {dx}]' if dx == dy else f'[({cx}, {cy}) @ ({dx}, {dy})]'

  @staticmethod
  def FromCoords(re1: str | float, im1: str | float, re2: str | float, im2: str | float) -> Frame:
    """Create a Frame from coordinate values. Will order the corners correctly.

    Args:
      re1 (str | float): Real part of one corner.
      im1 (str | float): Imaginary part of one corner.
      re2 (str | float): Real part of the second corner.
      im2 (str | float): Imaginary part of the second corner.

    Returns:
      Frame: A Frame object representing the rectangle defined by the two corners.

    Raises:
      Error: if the coordinates cannot be converted to mpq or if they do not define a rectangle
        with area

    """
    x1: gmpy2.mpq = gmpy2.mpq(re1)
    y1: gmpy2.mpq = gmpy2.mpq(im1)
    x2: gmpy2.mpq = gmpy2.mpq(re2)
    y2: gmpy2.mpq = gmpy2.mpq(im2)
    if x1 == x2 or y1 == y2:
      raise Error(f'coordinates must define a rectangle with area, got ({x1}, {y1}) / ({x2}, {y2})')
    return Frame(
      top_re=min(x1, x2), top_im=max(y1, y2), bottom_re=max(x1, x2), bottom_im=min(y1, y2)
    )

  @staticmethod
  def FromCenter(
    center_re: str | float,
    center_im: str | float,
    width: str | float,
    height: str | float | None = None,
  ) -> Frame:
    """Create a Frame from a center point and dimensions.

    Args:
      center_re (str | float): Real part of the center point.
      center_im (str | float): Imaginary part of the center point.
      width (str | float): Width of the frame in the real direction.
      height (str | float | None): Height of the frame in the imaginary direction. If None,
          height will be equal to width.

    Returns:
      Frame: A Frame object representing the rectangle defined by the center and dimensions.

    Raises:
      Error: if the coordinates cannot be converted to mpq or if the resulting frame is invalid

    """
    cx: gmpy2.mpq = gmpy2.mpq(center_re)
    cy: gmpy2.mpq = gmpy2.mpq(center_im)
    dx: gmpy2.mpq = gmpy2.mpq(width)
    dy: gmpy2.mpq = gmpy2.mpq(height) if height is not None else dx
    if dx <= 0 or dy <= 0:
      raise Error(f'width and height must be positive, got {dx=} and {dy=}')
    dx, dy = dx / _MPQ_TWO, dy / _MPQ_TWO
    fr = Frame(top_re=cx - dx, top_im=cy + dy, bottom_re=cx + dx, bottom_im=cy - dy)
    if fr.center != (cx, cy):
      raise Error(f'calculated frame center {fr.center} does not match input center ({cx}, {cy})')
    if fr.size != (dx * _MPQ_TWO, dy * _MPQ_TWO):
      raise Error(f'calculated frame size {fr.size} does not match input size ({dx * 2}, {dy * 2})')
    return fr

  @property
  def precision(self) -> int:
    """Pick enough precision to distinguish adjacent pixels in smaller complex-plane dimension.

    Will use MAX_IMAGE_SIZE and the frame dimensions to estimate the pixel size in the complex
    plane, and then calculate the number of bits needed to have enough precision to distinguish
    adjacent pixels, plus a safety margin.

    Returns:
      int: The estimated number of bits of precision needed.

    Raises:
      Error: if the estimated precision exceeds the maximum allowed.

    """
    # compute the size & most conservative scale - exact mpq computations
    px_scale: gmpy2.mpq = self.scale / _MPQ_MAX_IMAGE_SIZE
    # log2 converts to mpfr, so we pick a huge, almost ridiculous, precision to do this in
    with PrecisionContext():
      # need about -log2(scale) bits, plus guard
      n_precision: int = max(
        _MPFR_MIN_PRECISION, int(gmpy2.ceil(-gmpy2.log2(px_scale))) + _MPFR_MIN_GUARD_BITS
      )
    # check for precision cap and return
    if n_precision > _MPFR_MAX_PRECISION:
      raise Error(f'Frame too small: estimated {n_precision} bits; max is {_MPFR_MAX_PRECISION}')
    return n_precision

  @property
  def context(self) -> gmpy2.context:
    """Get gmpy2 context with precision to distinguish adjacent pixels in smaller complex-plane dim.

    Returns:
      gmpy2.context: A context with the estimated number of bits of precision needed.

    """
    return gmpy2.local_context(gmpy2.context(), precision=self.precision)


# Frame: the default frame is the one that shows the whole Mandelbrot set, which is centered at
# -0.75+0j and has width 2.5; the height is the same as the width by default;
# The set <https://en.wikipedia.org/wiki/Mandelbrot_set> is contained in the rectangle with corners
# -2.5-1.25j and 0.5+1.25j, which is exactly our default here
DEFAULT_FRAME_CENTER_RE: str = '-0.75'
DEFAULT_FRAME_CENTER_IM: str = '0'
DEFAULT_FRAME_SIZE: str = '2.5'
DEFAULT_FRAME: Frame = Frame.FromCenter(
  DEFAULT_FRAME_CENTER_RE, DEFAULT_FRAME_CENTER_IM, DEFAULT_FRAME_SIZE
)


class Image:
  """A fractal image. Encapsulates the image operations."""

  def __init__(self, frame: Frame, width: int, height: int, max_iter: int) -> None:
    """Construct image.

    Raises:
      Error: on error

    """
    # check parameters
    if not (MIN_IMAGE_SIZE <= width <= MAX_IMAGE_SIZE) or not (
      MIN_IMAGE_SIZE <= height <= MAX_IMAGE_SIZE
    ):
      raise Error(f'{width=} and {height=} must be between {MIN_IMAGE_SIZE} and {MAX_IMAGE_SIZE}')
    if not (_MIN_ITER <= max_iter <= _MAX_ITER):
      raise Error(f'{max_iter=} must be between {_MIN_ITER} and {_MAX_ITER}')
    # save objects
    self._frame: Frame = frame
    self._width: int = width
    self._height: int = height
    self._max_iter: int = max_iter
    # initialize image data array; self._escape stores the ESCAPE ITERATION data, not the color
    self._escape: ImageUInt32Array = array.array('I', (0 for _ in range(width * height)))
    if self._escape.itemsize != _N_BYTES_UINT:
      raise Error(f'unsupported platform: array of unsigned ints is not {_N_BYTES_UINT} bytes')

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
    if not (0 <= escaped_at <= self._max_iter):
      raise Error(f'Invalid escape iteration: {escaped_at=} / {self._max_iter=}')
    self._escape[y * self._width + x] = escaped_at

  def AsPixels(self) -> bytes:
    """Convert the image to raw pixel bytes using histogram-equalized smooth color palette.

    Current palette:
    - black for interior points (never escape)
    - smooth 16-color cycling gradient, histogram-equalized across escape iterations

    Interior points (that never escaped, i.e., escaped_at == max_iter) are rendered as
    pure black. Exterior points are colored by mapping their escape iteration through a
    cumulative histogram distribution (histogram equalization) into [0, 1), which is then
    fed into a smooth cycling 16-color gradient via _PixelPalette. This ensures the full
    color range is used regardless of zoom depth or iteration distribution.

    Returns:
      bytes: Raw pixel data in RGB format (3 bytes per pixel).

    """
    # step 1: build histogram of escape iterations for exterior pixels only
    histogram: dict[int, int] = {}
    for escaped_at in self._escape:
      if escaped_at < self._max_iter:
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
    for i, escaped_at in enumerate(self._escape):
      if escaped_at >= self._max_iter or total_exterior == 0:
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


def Mandelbrot(  # noqa: PLR0914
  frame: Frame, width: int, height: int, *, max_iter: int = DEFAULT_ITER, progress_bar: bool = True
) -> Image:
  """Render the frame rectangle to an Image.

  Args:
    frame (Frame): The frame to render.
    width (int): The width of the output image in pixels.
    height (int): The height of the output image in pixels.
    max_iter (int, optional): The maximum number of iterations to determine escape.
        Defaults to DEFAULT_ITER.
    progress_bar (bool, optional): Whether to show a progress bar. Defaults to True.

  Returns:
    Image: The rendered fractal image.

  Raises:
    Error: on error

  """
  # compute pixel size in complex plane and check frame validity; exact computation (gmpy2.mpq)
  dx: gmpy2.mpq
  dy: gmpy2.mpq
  dx, dy = frame.size
  dx, dy = dx / gmpy2.mpq(width - 1), dy / gmpy2.mpq(height - 1)
  if dx <= 0 or dy <= 0:
    raise Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
  # create image; will also check the parameters and frame validity in the Image constructor
  image: Image = Image(frame, width, height, max_iter)
  # start the mpfr context for floating-point computations with the precision needed
  with frame.context:
    # precompute x coordinates once: this matters because mpfr construction and arithmetic
    # are relatively expensive and we can reuse the x values across rows ("inner for loop");
    # also, this is where the "X" (real) coordinates are converted mpq->mpfr
    xs: list[gmpy2.mpfr] = [gmpy2.mpfr(frame.top_re + gmpy2.mpq(i) * dx) for i in range(width)]
    # iterate over pixels in row-major order, computing escape iterations in mpfr
    for py in tqdm.tqdm(
      iterable=range(height),
      desc='Img',
      unit='ln',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='green',
      disable=not progress_bar,
    ):
      # PILImage.frombytes interprets the first row written as the top row of the image, so
      # we iterate y inverted by starting at the top and going down;
      # this is the "outer for loop", no benefit in pre-computing y values;
      # also, this is where the "Y" (imaginary) coordinates are converted mpq->mpfr
      cy: gmpy2.mpfr = gmpy2.mpfr(frame.top_im - gmpy2.mpq(py) * dy)
      # iterate over columns, reusing x values and doing the escape test in mpfr for correctness
      for px in range(width):
        cx: gmpy2.mpfr = xs[px]
        # fast interior tests, all in mpfr: main cardioid and period-2 bulb.
        x_minus_quarter: gmpy2.mpfr = cx - _MPFR_FOURTH
        q: gmpy2.mpfr = x_minus_quarter * x_minus_quarter + cy * cy
        in_cardioid: bool = q * (q + x_minus_quarter) <= _MPFR_FOURTH * cy * cy
        x_plus_one: gmpy2.mpfr = cx + _MPFR_ONE
        in_bulb: bool = x_plus_one * x_plus_one + cy * cy <= _MPFR_SIXTEENTH
        if in_cardioid or in_bulb:
          # point is in the main cardioid or period-2 bulb, so it's an interior point, no escape
          image.SetEscape(px, py, max_iter)
          continue
        # not in the main cardioid or period-2 bulb, do the full escape-time test in mpfr
        zx: gmpy2.mpfr = _MPFR_ZERO
        zy: gmpy2.mpfr = _MPFR_ZERO
        escaped_at: int = 0
        # escape-time loop, implemented with explicit zx/zy variables
        for escaped_at in range(max_iter):  # noqa: B007
          zx2: gmpy2.mpfr = zx * zx
          zy2: gmpy2.mpfr = zy * zy
          # avoid sqrt(abs(z)); compare squared magnitude to 2^2
          if zx2 + zy2 > _MPFR_FOUR:
            break
          # z = z^2 + c in terms of zx/zy: zx' = zx^2 - zy^2 + cx
          zy = _MPFR_TWO * zx * zy + cy
          zx = zx2 - zy2 + cx
        else:
          escaped_at = max_iter  # if we didn't break, we reached max_iter, mark as non-escaped
        image.SetEscape(px, py, escaped_at)
  # done
  return image


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
      - hash: A hash of the image data (SHA256 of RGBA bytes).
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
