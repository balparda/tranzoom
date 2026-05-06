# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Business logic examples."""

from __future__ import annotations

import dataclasses
import io

import gmpy2
import tqdm
from PIL import Image
from transcrypto.utils import base as tbase

_MIN_ITER: int = 100
DEFAULT_ITER: int = 1000

_MPFR_SIXTEENTH = gmpy2.mpfr('0.0625')
_MPFR_FOURTH = gmpy2.mpfr('0.25')
_MPFR_ONE = gmpy2.mpfr('1')
_MPFR_TWO = gmpy2.mpfr('2')
_MPFR_FOUR = gmpy2.mpfr('4')


class Error(tbase.Error):
  """Base fractal exception."""


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class Frame:
  """Defines a rectangular region of the complex plane, with arbitrary precision."""

  top: gmpy2.mpc  # the top-left corner of the rectangle
  bottom: gmpy2.mpc  # the bottom-right corner of the rectangle

  def __post_init__(self) -> None:
    """Check rectangle has an area and top/bottom ordering.

    Raises:
      Error: if the rectangle is invalid.

    """
    if self.top.real >= self.bottom.real:
      raise Error(f'top.real ({self.top.real}) must be < bottom.real ({self.bottom.real})')
    if self.top.imag <= self.bottom.imag:
      raise Error(f'top.imag ({self.top.imag}) must be > bottom.imag ({self.bottom.imag})')

  def __str__(self) -> str:
    """Get string representation of the frame.

    Returns:
      str: String representation of the frame.

    """
    # TODO: center + size?
    return f'[({self.top.real}, {self.top.imag}), ({self.bottom.real}, {self.bottom.imag})]'

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
      Error: if the coordinates cannot be converted to mpfr or if the resulting frame is invalid

    """
    x1, y1 = gmpy2.mpfr(re1), gmpy2.mpfr(im1)
    x2, y2 = gmpy2.mpfr(re2), gmpy2.mpfr(im2)
    if x1 == x2 or y1 == y2:
      raise Error(f'coordinates must define a rectangle with area, got ({x1}, {y1}) / ({x2}, {y2})')
    return Frame(
      top=gmpy2.mpc(min(x1, x2), max(y1, y2)), bottom=gmpy2.mpc(max(x1, x2), min(y1, y2))
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
      Error: if the coordinates cannot be converted to mpfr or if the resulting frame is invalid

    """
    cx, cy = gmpy2.mpfr(center_re), gmpy2.mpfr(center_im)
    dx: gmpy2.mpfr = gmpy2.mpfr(width)
    dy: gmpy2.mpfr = gmpy2.mpfr(height) if height is not None else dx
    if dx <= 0 or dy <= 0:
      raise Error(f'width and height must be positive, got {dx=} and {dy=}')
    dx, dy = dx / _MPFR_TWO, dy / _MPFR_TWO
    return Frame(top=gmpy2.mpc(cx - dx, cy + dy), bottom=gmpy2.mpc(cx + dx, cy - dy))

  def AutoPrecisionBits(self, width: int, height: int, *, guard_bits: int = 64) -> int:
    """Pick enough precision to distinguish adjacent pixels in smaller complex-plane dimension.

    This is a practical heuristic, not a proof of numerical correctness for all escape decisions.

    Args:
      width (int): The width of the output image in pixels.
      height (int): The height of the output image in pixels.
      guard_bits (int, optional): Additional bits to add as a safety margin. Defaults to 64.

    Returns:
      int: The estimated number of bits of precision needed.

    Raises:
      Error: If width or height is less than 4, or if guard_bits is less than 64.

    """
    # check parameters
    if width < 4 or height < 4:  # noqa: PLR2004
      raise Error(f'{width=} and {height=} must be >= 4')
    if guard_bits < 64:  # noqa: PLR2004
      raise Error(f'{guard_bits=} must be >= 64')
    # use high temporary precision so the precision estimate itself does not get quantized too early
    with gmpy2.local_context(gmpy2.context(), precision=512):
      dx: gmpy2.mpfr = self.bottom.real - self.top.real
      dy: gmpy2.mpfr = self.top.imag - self.bottom.imag
      scale: gmpy2.mpfr = min(dx / gmpy2.mpfr(width), dy / gmpy2.mpfr(height))
      # need about -log2(pixel_size) bits, plus guard.
      return max(80, int(gmpy2.ceil(-gmpy2.log2(scale))) + guard_bits)

  def AutoPrecisionContext(self, width: int, height: int, *, guard_bits: int = 64) -> gmpy2.context:
    """Get gmpy2 context with precision to distinguish adjacent pixels in smaller complex-plane dim.

    Args:
      width (int): The width of the output image in pixels.
      height (int): The height of the output image in pixels.
      guard_bits (int, optional): Additional bits to add as a safety margin. Defaults to 64.

    Returns:
      gmpy2.context: A context with the estimated number of bits of precision needed.

    """
    return gmpy2.local_context(
      gmpy2.context(), precision=self.AutoPrecisionBits(width, height, guard_bits=guard_bits)
    )


def Mandelbrot(frame: Frame, width: int, height: int, *, max_iter: int = DEFAULT_ITER) -> bytes:  # noqa: PLR0914, PLR0915
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

  Returns:
    bytes: PNG image data.

  Raises:
    Error: on error

  """
  # check parameters
  if width < 4 or height < 4:  # noqa: PLR2004
    raise Error(f'{width=} and {height=} must be >= 4')
  if max_iter < _MIN_ITER:
    raise Error(f'{max_iter=} must be >= {_MIN_ITER}')
  x1: gmpy2.mpfr
  y1: gmpy2.mpfr
  x2: gmpy2.mpfr
  y2: gmpy2.mpfr
  dx: gmpy2.mpfr
  dy: gmpy2.mpfr
  zx: gmpy2.mpfr
  zy: gmpy2.mpfr
  zx2: gmpy2.mpfr
  zy2: gmpy2.mpfr
  cx: gmpy2.mpfr
  cy: gmpy2.mpfr
  v: int
  r: int
  g: int
  b: int
  with frame.AutoPrecisionContext(width, height):  # noqa: PLR1702
    # compute pixel size in complex plane and check frame validity
    x1, y1 = frame.top.real, frame.bottom.imag
    x2, y2 = frame.bottom.real, frame.top.imag
    dx = (x2 - x1) / gmpy2.mpfr(width - 1)
    dy = (y2 - y1) / gmpy2.mpfr(height - 1)
    assert dx > 0 and dy > 0, f'frame must have positive area {dx=}x{dy=}, should never happen'  # noqa: PT018, S101
    # use a single bytearray for the whole image to avoid PIL overhead
    pixels = bytearray(width * height * 3)
    # precompute x coordinates once: this matters because mpfr construction and arithmetic
    # are relatively expensive and we can reuse the x values across rows ("inner for loop")
    xs: list[gmpy2.mpfr] = [x1 + gmpy2.mpfr(i) * dx for i in range(width)]
    out: int = 0
    # iterate over pixels in row-major order, computing escape iterations in mpfr
    for py in tqdm.tqdm(
      iterable=range(height),
      desc='Img',
      unit='px',
      dynamic_ncols=True,
      smoothing=0.001,
      colour='green',
    ):
      cy = y1 + gmpy2.mpfr(py) * dy  # this is the "outer for loop", no need to pre-compute y values
      # iterate over columns, reusing x values and doing the escape test in mpfr for correctness
      for px in range(width):
        cx = xs[px]
        # fast interior tests, all in mpfr: main cardioid and period-2 bulb.
        x_minus_quarter: gmpy2.mpfr = cx - _MPFR_FOURTH
        q: gmpy2.mpfr = x_minus_quarter * x_minus_quarter + cy * cy
        in_cardioid: bool = q * (q + x_minus_quarter) <= _MPFR_FOURTH * cy * cy
        x_plus_one: gmpy2.mpfr = cx + _MPFR_ONE
        in_bulb: bool = x_plus_one * x_plus_one + cy * cy <= _MPFR_SIXTEENTH
        if in_cardioid or in_bulb:
          r = g = b = 0  # black interior point
        else:
          # not in the main cardioid or period-2 bulb, do the full escape-time test in mpfr
          zx = gmpy2.mpfr('0')
          zy = gmpy2.mpfr('0')
          escaped_at: int = max_iter
          # escape-time loop, implemented with explicit zx/zy variables
          for n in range(max_iter):
            zx2 = zx * zx
            zy2 = zy * zy
            # avoid sqrt(abs(z)); compare squared magnitude to 2^2
            if zx2 + zy2 > _MPFR_FOUR:
              escaped_at = n
              break
            # z = z^2 + c in terms of zx/zy: zx' = zx^2 - zy^2 + cx
            zy = _MPFR_TWO * zx * zy + cy
            zx = zx2 - zy2 + cx
          # decide pixel color based on escape iteration
          if escaped_at == max_iter:
            # got to max_iter without escaping, treat as interior point
            r = g = b = 0  # black interior point
          else:
            # placeholder grayscale palette for escaped points: map escape iteration to 0-255
            v = 255 - int(255 * escaped_at / max_iter)
            r = g = b = v
        # put pixel values in the bytearray
        pixels[out] = r
        pixels[out + 1] = g
        pixels[out + 2] = b
        out += 3
    # done, convert the raw pixel data to a PNG using PIL
    img: Image.Image = Image.frombytes('RGB', (width, height), bytes(pixels))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
