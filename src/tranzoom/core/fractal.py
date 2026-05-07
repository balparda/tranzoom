# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing.

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>
"""

from __future__ import annotations

import dataclasses
import io
from collections import abc
from typing import cast

import gmpy2
import tqdm
from PIL import Image
from transcrypto.core import hashes
from transcrypto.utils import base as tbase

# basic constants
_MIN_ITER: int = 512
DEFAULT_ITER: int = 1000
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
    return int(_MIN_ITER + 256 * magnitude) if magnitude > 0.0 else _MIN_ITER

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
    return Frame(top_re=cx - dx, top_im=cy + dy, bottom_re=cx + dx, bottom_im=cy - dy)

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


def Mandelbrot(  # noqa: PLR0914
  frame: Frame, width: int, height: int, *, max_iter: int = DEFAULT_ITER, progress_bar: bool = True
) -> tuple[bytes, str]:
  """Render the frame rectangle to PNG bytes.

  Current palette:
    - black for points that do not escape
    - grayscale by escape iteration for points that do
  TODO: Later, replace the color section only.

  Args:
    frame (Frame): The frame to render.
    width (int): The width of the output image in pixels.
    height (int): The height of the output image in pixels.
    max_iter (int, optional): The maximum number of iterations to determine escape.
        Defaults to DEFAULT_ITER.
    progress_bar (bool, optional): Whether to show a progress bar. Defaults to True.

  Returns:
    tuple[bytes, str]: PNG image data and its internal data hash.

  Raises:
    Error: on error

  """
  # check parameters
  if (
    not MIN_IMAGE_SIZE <= width <= MAX_IMAGE_SIZE or not MIN_IMAGE_SIZE <= height <= MAX_IMAGE_SIZE
  ):
    raise Error(f'{width=} and {height=} must be between {MIN_IMAGE_SIZE} and {MAX_IMAGE_SIZE}')
  if max_iter < _MIN_ITER:
    raise Error(f'{max_iter=} must be >= {_MIN_ITER}')
  with frame.context:  # noqa: PLR1702
    # compute pixel size in complex plane and check frame validity
    dx: gmpy2.mpq
    dy: gmpy2.mpq
    dx, dy = frame.size
    dx, dy = dx / gmpy2.mpq(width - 1), dy / gmpy2.mpq(height - 1)
    if dx <= 0 or dy <= 0:
      raise Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
    # use a single bytearray for the whole image to avoid PIL overhead
    pixels = bytearray(width * height * 3)
    # precompute x coordinates once: this matters because mpfr construction and arithmetic
    # are relatively expensive and we can reuse the x values across rows ("inner for loop");
    # also, this is where the "X" (real) coordinates are converted mpq->mpfr
    xs: list[gmpy2.mpfr] = [gmpy2.mpfr(frame.top_re + gmpy2.mpq(i) * dx) for i in range(width)]
    out: int = 0
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
      # Image.frombytes interprets the first row written as the top row of the image, so
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
        r: int = 0  # start with black "interior" point/color
        g: int = 0
        b: int = 0
        if not in_cardioid and not in_bulb:
          # not in the main cardioid or period-2 bulb, do the full escape-time test in mpfr
          zx: gmpy2.mpfr = _MPFR_ZERO
          zy: gmpy2.mpfr = _MPFR_ZERO
          escaped_at: int = max_iter
          # escape-time loop, implemented with explicit zx/zy variables
          for n in range(max_iter):
            zx2: gmpy2.mpfr = zx * zx
            zy2: gmpy2.mpfr = zy * zy
            # avoid sqrt(abs(z)); compare squared magnitude to 2^2
            if zx2 + zy2 > _MPFR_FOUR:
              escaped_at = n
              break
            # z = z^2 + c in terms of zx/zy: zx' = zx^2 - zy^2 + cx
            zy = _MPFR_TWO * zx * zy + cy
            zx = zx2 - zy2 + cx
          # decide pixel color based on escape iteration
          if escaped_at != max_iter:
            # escaped before max_iter, so NOT an interior point
            # placeholder grayscale palette for escaped points: map escape iteration to 0-255
            v: int = 255 - int(255 * escaped_at / max_iter)
            r = g = b = v
        # put pixel values in the bytearray
        pixels[out] = r
        pixels[out + 1] = g
        pixels[out + 2] = b
        out += 3
    # done, convert the raw pixel data to a PNG using PIL
    raw_img: bytes = bytes(pixels)
    img: Image.Image = Image.frombytes('RGB', (width, height), raw_img)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return (buf.getvalue(), hashes.Hash256(raw_img).hex())
