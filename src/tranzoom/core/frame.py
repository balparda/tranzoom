# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Frame: a rectangular region of the complex plane, with arbitrary precision. Exact."""

from __future__ import annotations

import dataclasses
from collections import abc
from typing import cast

import gmpy2
from transcrypto.utils import base as tbase

# basic constants

MIN_IMAGE_SIZE: int = 16  # BEWARE: we use this for the "auto" depth calculation, so not too small!
MAX_IMAGE_SIZE: int = 8192
DEFAULT_IMAGE_SIZE: int = 1024

# gmpy2.mpfr constants
_MPFR_MIN_PRECISION: int = 80  # about 25 decimal digits
_MPFR_BIG_PRECISION: int = 30_000  # ±10k decimal digits
_MPFR_MAX_PRECISION: int = 300_000  # ±100k decimal digits
_MPFR_MIN_GUARD_BITS: int = 64  # extra bits beyond the minimum needed to distinguish pixels

# gmpy2.mpfr ultra-precision context factory
PrecisionContext: abc.Callable[[], gmpy2.context] = lambda: gmpy2.local_context(
  gmpy2.context(), precision=_MPFR_BIG_PRECISION
)

# gmpy2.mpq constants
_MPQ_TWO = gmpy2.mpq(2)
_MPQ_MAX_IMAGE_SIZE = gmpy2.mpq(MAX_IMAGE_SIZE)

# Frame: the default frame is the one that shows the whole Mandelbrot set, which is centered at
# -0.75+0j and has width 2.5; the height is the same as the width by default;
# The set <https://en.wikipedia.org/wiki/Mandelbrot_set> is contained in the rectangle with corners
# -2.5-1.25j and 0.5+1.25j, which is exactly our default here
DEFAULT_FRAME_CENTER_RE: str = '-0.75'
DEFAULT_FRAME_CENTER_IM: str = '0'
DEFAULT_FRAME_SIZE: str = '2.5'


class Error(tbase.Error):
  """Base frame exception."""


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


DEFAULT_FRAME: Frame = Frame.FromCenter(
  DEFAULT_FRAME_CENTER_RE, DEFAULT_FRAME_CENTER_IM, DEFAULT_FRAME_SIZE
)
