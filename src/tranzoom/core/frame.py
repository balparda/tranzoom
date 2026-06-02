# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Frame: a rectangular region of the complex plane, with arbitrary precision. Exact."""

from __future__ import annotations

import abc as abstract_abc
import dataclasses
import enum
import json
import math
import os
import statistics
import sys
from collections import abc
from typing import Any, cast, final

import gmpy2
from transcrypto.core import hashes
from transcrypto.utils import base as tbase

# basic constants

type ExactInputType = str | float | gmpy2.mpq

MIN_IMAGE_SIZE: int = 24  # BEWARE: we use this for the "auto" depth calculation, so not too small!
MAX_IMAGE_SIZE: int = 16 * 1024  # huge image, 16k x 16k, 256Mpx, tens or hundreds of Mb per image
DEFAULT_IMAGE_SIZE: int = 1024  # good all-around default, 1Mpx, ~1Mb per image (compressed)
DEFAULT_ZOOM_SIZE: int = 512  # smaller default for zoom, since it can be more expensive
MIN_IMAGE_PX: int = MIN_IMAGE_SIZE**2
MAX_IMAGE_PX: int = MAX_IMAGE_SIZE**2

BIT_31: int = 0x80000000
BIT_32: int = 0x100000000
BIT_64: int = 2**64
MAX_UINT32: int = 0xFFFFFFFF

# iteration constants

N_BYTES_UINT: int = 8  # we use array of uint64 to store pixel data / array.array('Q') / unsigned 64
MIN_ITER: int = 1000  # minimum, but also a mark that we want to automatically calculate the depth
HIGH_ITERS: list[int] = [100_000, 1_000_000, 10_000_000]  # these are very high iteration counts
SET_INTERIOR_RESOLUTION: int = 100_000_000  # interior points max val [0..SET_INTERIOR_RESOLUTION]
MAX_ITER: int = BIT_31 - 1  # ± 2_147_483_647, max for signed array('i'), sint32
SMOOTH_EXTRA_ITERS: int = 5  # iterations AFTER |z| > 2 to compute: eliminates color banding errors

# file/memory size thresholds for warnings about large files or memory usage
THRESHOLD_LARGE_PNG_BYTES: int = 50 * 1024 * 1024  # warn if single-frame PNG/JPG exceeds 50 MB
THRESHOLD_LARGE_FRAME_MEMORY_BYTES: int = 20 * 1024 * 1024 * 1024  # warn if render RAM > 20 GB
THRESHOLD_LARGE_ANIMATION_BYTES: int = 2 * 1024 * 1024 * 1024  # warn if video file estimate > 2 GB
THRESHOLD_LARGE_ZOOM_MEMORY_BYTES: int = 32 * 1024 * 1024 * 1024  # warn if zoom render RAM > 32 GB

# multiprocessing
AVAILABLE_CPU: int = int(getattr(os, 'process_cpu_count', os.cpu_count)() or 1)
MAX_CONCURRENCE: int = 12  # for the main rendering step, we limit the concurrency

# gmpy2.mpfr constants
_MPFR_MIN_PRECISION: int = 140  # about 42 decimal digits
_MPFR_BIG_PRECISION: int = 30_000  # ±10k decimal digits
_MPFR_MAX_PRECISION: int = 300_000  # ±100k decimal digits
_MPFR_MIN_GUARD_BITS: int = 88  # extra bits beyond the minimum needed to distinguish pixels
MPFR_MAX_SET_Z: gmpy2.mpfr = gmpy2.mpfr('2')
MPFR_SET_INTERIOR_RESOLUTION: gmpy2.mpfr = gmpy2.mpfr(SET_INTERIOR_RESOLUTION)
MPFR_SET_INTERIOR_SCALE: gmpy2.mpfr = MPFR_SET_INTERIOR_RESOLUTION / MPFR_MAX_SET_Z

# gmpy2.mpfr ultra-precision context factory
PrecisionContext: abc.Callable[[], gmpy2.context] = lambda: gmpy2.local_context(
  gmpy2.context(), precision=_MPFR_BIG_PRECISION
)

# gmpy2.mpq constants
_MPQ_ZERO: gmpy2.mpq = gmpy2.mpq('0')
_MPQ_ONE: gmpy2.mpq = gmpy2.mpq('1')
_MPQ_SQRT_TWO_NOT_EXACT: gmpy2.mpq = gmpy2.mpq('99/70')  # good enough for our purposes
_MPQ_TWO: gmpy2.mpq = gmpy2.mpq('2')
# constant to divide frame size when zooming one step
DEFAULT_MPQ_ZOOM: gmpy2.mpq = gmpy2.mpq('2')  # 2x
# fraction of frame size to move when moving in a cardinal direction
DEFAULT_STEP_DIRECT: int = 3
DEFAULT_MPQ_STEP_DIRECT: gmpy2.mpq = gmpy2.mpq(f'1/{DEFAULT_STEP_DIRECT}')
DEFAULT_MPQ_STEP_DIAGONAL: gmpy2.mpq = DEFAULT_MPQ_STEP_DIRECT / _MPQ_SQRT_TWO_NOT_EXACT

# Frame: the default frame is the one that shows the whole Mandelbrot set, which is centered at
# -0.75+0j and has width 2.5; the height is the same as the width by default;
# The set <https://en.wikipedia.org/wiki/Mandelbrot_set> is contained in the rectangle with corners
# -2.5-1.25j and 0.5+1.25j, which is exactly our default here
DEFAULT_FRAME_CENTER_RE: str = '-0.75'
DEFAULT_FRAME_CENTER_IM: str = '0'
DEFAULT_FRAME_SIZE: str = '2.5'
DEFAULT_JULIA_RE: str = '0.27334'
DEFAULT_JULIA_IM: str = '0.00742'
DEFAULT_JULIA_CENTER_RE: str = '0'
DEFAULT_JULIA_CENTER_IM: str = '0'
DEFAULT_JULIA_WIDTH: str = '1.8'
DEFAULT_JULIA_HEIGHT: str = '2.2'


# TODO: image to store: on set/non-escaped the actual final value of the tracked constant;
#     and if we store the mpfr on a dict for example, we will have space for more info in the array


class Error(tbase.Error):
  """Base frame exception."""


class Fractal(enum.Enum):
  """Fractal enum."""

  MANDELBROT = 'mandelbrot'
  JULIA = 'julia'


DEFAULT_FRACTAL: Fractal = Fractal.MANDELBROT


class SetHighlightAlgorithm(enum.Enum):
  """Set highlight algorithm enum."""

  MIN = 'min'
  MAX = 'max'
  ANGLE = 'angle'
  IMAGINARY = 'imaginary'


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class SerializingFractalObject(abstract_abc.ABC):
  """Base class for useful fractal objects that can be serialized to JSON with a hash."""

  @abstract_abc.abstractmethod
  def __post_init__(self) -> None:
    """Check object validity.

    Raises:
      Error: if the object is invalid.

    """

  @abstract_abc.abstractmethod
  def __str__(self) -> str:
    """Get string representation of the object.

    Returns:
      str: String representation of the object.

    """

  @staticmethod
  @abstract_abc.abstractmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> SerializingFractalObject:
    """Create a SerializingFractalObject from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from Frame.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the frame. If the
          calculated hash does not match, an error is raised.

    Returns:
      SerializingFractalObject: A SerializingFractalObject object

    Raises:
      Error: on error

    """

  @property
  @abstract_abc.abstractmethod
  def json(self) -> tbase.JSONDict:
    """Get a JSON-serializable dictionary representation of the object.

    Returns:
      tbase.JSONDict: A dictionary representation of the object.

    """

  @final  # this affects the HASH, let's avoid trouble...
  @property
  def binary(self) -> bytes:
    """Get a stable binary representation of the object, for hashing and storage.

    Returns:
      bytes: The stable binary (UTF-8 encoded canonical JSON) representation of the object.

    """
    return json.dumps(self.json, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode(
      'utf-8'
    )

  @final  # this affects the HASH, let's avoid trouble...
  @property
  def sha(self) -> str:
    """SHA-256 hash of the object.

    Returns:
      str: The SHA-256 hash of the object, as a hex string.

    """
    return hashes.Hash256(self.binary).hex()

  @final
  @property
  def self_sz(self) -> int:
    """Get the size of the object in bytes, including nested objects.

    Not guaranteed to be exact, but should be a good estimate for our purposes.
    Not a super cheap call, don't overuse it.

    Returns:
      int: The size of the object in bytes.

    """
    return DeepSize(self)


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class Frame(SerializingFractalObject):
  """Defines a rectangular region of the complex plane, with arbitrary precision. Exact.

  ATTENTION: changing any attribute changes the object SHA-256 hash.

  An optional point coordinate is included. This is used for Julia, and ignored for Mandelbrot.
  This point is not required to be inside the rectangle; it is just an additional coordinate
  that can be used for various purposes, such as marking a specific location in the image or
  providing additional data like for the Julia fractal.

  Attributes:
    fractal (Fractal): The type of fractal this frame belongs to.
    top_re (gmpy2.mpq): Real part of the top-left corner of the rectangle.
    top_im (gmpy2.mpq): Imaginary part of the top-left corner of the rectangle.
    bottom_re (gmpy2.mpq): Real part of the bottom-right corner of the rectangle.
    bottom_im (gmpy2.mpq): Imaginary part of the bottom-right corner of the rectangle.
    point_re (gmpy2.mpq): Real part of the optional point coordinate; default is 0;
        used for Julia (the orbit point), ignored for Mandelbrot.
    point_im (gmpy2.mpq): Imaginary part of the optional point coordinate; default is 0;
        used for Julia (the orbit point), ignored for Mandelbrot.

  """

  # ATTENTION: changing anything here changes the HASH!!
  fractal: Fractal
  top_re: gmpy2.mpq  # the top-left corner of the rectangle
  top_im: gmpy2.mpq
  bottom_re: gmpy2.mpq  # the bottom-right corner of the rectangle
  bottom_im: gmpy2.mpq
  point_re: gmpy2.mpq = _MPQ_ZERO  # for Julia, the point whose orbit we track
  point_im: gmpy2.mpq = _MPQ_ZERO

  def __post_init__(self) -> None:
    """Check rectangle has an area and top/bottom ordering.

    Raises:
      Error: if the rectangle is invalid.

    """
    # check fractal
    if self.fractal not in {Fractal.MANDELBROT, Fractal.JULIA}:
      raise Error(f'Unknown fractal type: {self.fractal}')
    # check rectangle is valid and in the expected order
    if self.top_re >= self.bottom_re:
      raise Error(f'top_re ({self.top_re}) must be < bottom_re ({self.bottom_re})')
    if self.top_im <= self.bottom_im:
      raise Error(f'top_im ({self.top_im}) must be > bottom_im ({self.bottom_im})')
    # disallow non-zero points for Mandelbrot as a safety for now, no use for them
    if self.fractal == Fractal.MANDELBROT and (
      self.point_re != _MPQ_ZERO or self.point_im != _MPQ_ZERO
    ):
      raise Error('Mandelbrot frames should not have a non-zero point coordinate')

  def __str__(self) -> str:
    """Get string representation of the Frame.

    Format is:
      - "[MANDELBROT: (c_re, c_im) ± (dx_re, dy_im)]" without the point for Mandelbrot; or
      - "[JULIA: (c_re, c_im) ± (dx_re, dy_im) @ (p_re, p_im)]" for Julia; and note
      - "(c_re, c_im)" is the center of the frame; and
      - "(dx_re, dy_im)" is the size of the frame; and
      - "(p_re, p_im)" is the point for Julia, if any; and
      - if `dx_re` and `dy_im` are the same, we can simplify to "± dx" instead of "± (dx, dy)".

    Returns:
      str: String representation of the Frame.

    Raises:
      Error: if the fractal type is unknown (should not happen b/c checked in __post_init__).

    """
    cx: gmpy2.mpq
    cy: gmpy2.mpq
    dx: gmpy2.mpq
    dy: gmpy2.mpq
    cx, cy = self.center
    dx, dy = self.size
    deltas: str = f'± {dx}' if dx == dy else f'± ({dx}, {dy})'
    fractal_str: str = self.fractal.value.upper()
    if self.fractal == Fractal.MANDELBROT:
      return f'[{fractal_str}: ({cx}, {cy}) {deltas}]'
    if self.fractal == Fractal.JULIA:
      return f'[{fractal_str}: ({cx}, {cy}) {deltas} @ ({self.point_re}, {self.point_im})]'
    raise Error(f'Unknown fractal type: {self.fractal}')

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
    dx: gmpy2.mpq
    dy: gmpy2.mpq
    dx, dy = self.size
    return dx == dy

  @property
  def scale(self) -> gmpy2.mpq:
    """Get the scale of the frame, i.e., the smaller dimension. Exact.

    Returns:
      gmpy2.mpq: The scale of the frame.

    """
    return min(*self.size)

  @property
  def area(self) -> gmpy2.mpq:
    """Get the area of the frame. Exact.

    Returns:
      gmpy2.mpq: The area of the frame.

    """
    s: tuple[gmpy2.mpq, gmpy2.mpq] = self.size
    return s[0] * s[1]

  @property
  def mag2(self) -> gmpy2.mpq:
    """Magnification squared; OR area ratio. Has not gone through sqrt(): Exact.

    DEFAULT_FRAMES[self.fractal].area / self.area i.e., WHOLE / this

    You can use this to compute total magnification: sqrt( obj1.mag2 / obj2.mag2 )

    Returns:
      gmpy2.mpq: The magnification squared; OR The area ratio

    """
    return DEFAULT_FRAMES[self.fractal].area / self.area

  @property
  def magnification(self) -> tuple[gmpy2.mpfr, float]:
    """Get frame magnification: How much "zoom" this frame has in relation to the whole set.

    sqrt( DEFAULT_FRAMES[self.fractal].area / self.area ) i.e., sqrt( WHOLE / this )

    Returns:
      tuple[gmpy2.mpfr, float]: (magnification, log10(magnification))

    """
    with PrecisionContext():
      magnification: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(self.mag2))
      return (magnification, float(cast('gmpy2.mpfr', gmpy2.log10(magnification))))

  @property
  def coordinates_magnitude(self) -> gmpy2.mpq:
    """Get the magnitude of the frame's coordinates, i.e., the max distance from the origin.

    Returns:
      gmpy2.mpq: The magnitude of the frame's coordinates.

    """
    return max(
      abs(self.top_re),
      abs(self.bottom_re),
      abs(self.top_im),
      abs(self.bottom_im),
      _MPQ_ONE,
    )

  @property
  def json(self) -> tbase.JSONDict:
    """Get a JSON-serializable dictionary representation of the frame.

    Keys: `fractal`, `top_re`, `top_im`, `bottom_re`, `bottom_im`, `point_re`, `point_im`, all str.

    Returns:
      tbase.JSONDict: A dictionary representation of the frame.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'fractal': self.fractal.value,
      'top_re': str(self.top_re),
      'top_im': str(self.top_im),
      'bottom_re': str(self.bottom_re),
      'bottom_im': str(self.bottom_im),
      'point_re': str(self.point_re),
      'point_im': str(self.point_im),
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> Frame:
    """Create a Frame from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from Frame.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the frame. If the
          calculated hash does not match, an error is raised.

    Returns:
      Frame: A Frame object

    Raises:
      Error: on error

    """
    # create the object
    try:
      frm = Frame(  # object creation will check the data is valid and consistent, and raise if not
        fractal=Fractal(data['fractal']),
        top_re=gmpy2.mpq(str(data['top_re'])),
        top_im=gmpy2.mpq(str(data['top_im'])),
        bottom_re=gmpy2.mpq(str(data['bottom_re'])),
        bottom_im=gmpy2.mpq(str(data['bottom_im'])),
        point_re=gmpy2.mpq(str(data['point_re'])),
        point_im=gmpy2.mpq(str(data['point_im'])),
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid Frame JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and frm.sha != check_hash:
      raise Error(f'Frame {frm.sha!r} does not match expected {check_hash!r}')
    return frm

  @staticmethod
  def FromCoords(
    fractal: Fractal,
    re1: ExactInputType,
    im1: ExactInputType,
    re2: ExactInputType,
    im2: ExactInputType,
  ) -> Frame:
    """Create a Frame from coordinate values. Will order the corners correctly.

    Args:
      fractal (Fractal): The type of fractal.
      re1 (ExactInputType): Real part of one corner.
      im1 (ExactInputType): Imaginary part of one corner.
      re2 (ExactInputType): Real part of the second corner.
      im2 (ExactInputType): Imaginary part of the second corner.

    Returns:
      Frame: A Frame object representing the rectangle defined by the two corners.

    Raises:
      Error: if the coordinates cannot be converted to mpq or if they do not define a rectangle
        with area

    """
    x1: gmpy2.mpq = re1 if isinstance(re1, gmpy2.mpq) else gmpy2.mpq(re1)
    y1: gmpy2.mpq = im1 if isinstance(im1, gmpy2.mpq) else gmpy2.mpq(im1)
    x2: gmpy2.mpq = re2 if isinstance(re2, gmpy2.mpq) else gmpy2.mpq(re2)
    y2: gmpy2.mpq = im2 if isinstance(im2, gmpy2.mpq) else gmpy2.mpq(im2)
    if x1 == x2 or y1 == y2:
      raise Error(f'coordinates must define a rectangle with area, got ({x1}, {y1}) / ({x2}, {y2})')
    return Frame(
      fractal=fractal,
      top_re=min(x1, x2),
      top_im=max(y1, y2),
      bottom_re=max(x1, x2),
      bottom_im=min(y1, y2),
    )

  @staticmethod
  def FromCenter(
    fractal: Fractal,
    center_re: ExactInputType,
    center_im: ExactInputType,
    width: ExactInputType,
    *,
    height: ExactInputType | None = None,
    point_re: ExactInputType | None = None,
    point_im: ExactInputType | None = None,
  ) -> Frame:
    """Create a Frame from a center point and dimensions.

    Args:
      fractal (Fractal): The type of fractal.
      center_re (ExactInputType): Real part of the center point.
      center_im (ExactInputType): Imaginary part of the center point.
      width (ExactInputType): Width of the frame in the real direction.
      height (ExactInputType | None): Height of the frame in the imaginary direction. If None,
          height will be equal to width.
      point_re (ExactInputType | None): For Julia, the real part of the point whose orbit we track.
      point_im (ExactInputType | None): For Julia, the imaginary part of the point whose orbit
          we track.

    Returns:
      Frame: A Frame object representing the rectangle defined by the center and dimensions.

    Raises:
      Error: if the coordinates cannot be converted to mpq or if the resulting frame is invalid

    """
    cx: gmpy2.mpq = center_re if isinstance(center_re, gmpy2.mpq) else gmpy2.mpq(center_re)
    cy: gmpy2.mpq = center_im if isinstance(center_im, gmpy2.mpq) else gmpy2.mpq(center_im)
    dx: gmpy2.mpq = width if isinstance(width, gmpy2.mpq) else gmpy2.mpq(width)
    dy: gmpy2.mpq = (
      (height if isinstance(height, gmpy2.mpq) else gmpy2.mpq(height)) if height is not None else dx
    )
    if (point_re is not None and point_im is None) or (point_re is None and point_im is not None):
      raise Error('point_re and point_im must both be provided or both be None')
    re: gmpy2.mpq = (
      (point_re if isinstance(point_re, gmpy2.mpq) else gmpy2.mpq(point_re))
      if point_re is not None
      else _MPQ_ZERO
    )
    im: gmpy2.mpq = (
      (point_im if isinstance(point_im, gmpy2.mpq) else gmpy2.mpq(point_im))
      if point_im is not None
      else _MPQ_ZERO
    )
    if dx <= 0 or dy <= 0:
      raise Error(f'width and height must be positive, got {dx=} and {dy=}')
    dx, dy = dx / _MPQ_TWO, dy / _MPQ_TWO
    fr = Frame(
      fractal=fractal,
      top_re=cx - dx,
      top_im=cy + dy,
      bottom_re=cx + dx,
      bottom_im=cy - dy,
      point_re=re,
      point_im=im,
    )
    if fr.center != (cx, cy):
      raise Error(f'calculated frame center {fr.center} does not match input center ({cx}, {cy})')
    if fr.size != (dx * _MPQ_TWO, dy * _MPQ_TWO):
      raise Error(f'calculated frame size {fr.size} does not match input size ({dx * 2}, {dy * 2})')
    return fr

  def PixelDimensionsFromSize(self, pixel_size: int) -> tuple[int, int]:
    """Calculate pixel dimensions for a image pixel size given its max dimension side.

    Args:
      pixel_size (int): The desired maximum dimension in pixels.

    Returns:
      tuple[int, int]: The calculated image (width, height) in pixels.

    Raises:
      Error: if the input pixel size is outside the allowed range.

    """
    # check px size is valid
    if not (MIN_IMAGE_SIZE <= pixel_size <= MAX_IMAGE_SIZE):
      raise Error(f'{pixel_size=} must be between {MIN_IMAGE_SIZE} and {MAX_IMAGE_SIZE}')
    # get the size of the frame in complex-plane units
    dx: gmpy2.mpq
    dy: gmpy2.mpq
    dx, dy = self.size
    # trivial case, a square
    if dx == dy:
      return (pixel_size, pixel_size)
    # rectangle case
    sz: gmpy2.mpq = gmpy2.mpq(pixel_size)
    if dx > dy:
      return (pixel_size, min(int(gmpy2.ceil(sz * dy / dx)), pixel_size))
    return (min(int(gmpy2.ceil(sz * dx / dy)), pixel_size), pixel_size)


# the standard/default frames for each fractal

DEFAULT_MANDELBROT_FRAME: Frame = Frame.FromCenter(
  Fractal.MANDELBROT, DEFAULT_FRAME_CENTER_RE, DEFAULT_FRAME_CENTER_IM, DEFAULT_FRAME_SIZE
)

DEFAULT_JULIA_FRAME: Frame = Frame.FromCenter(
  Fractal.JULIA,
  DEFAULT_JULIA_CENTER_RE,
  DEFAULT_JULIA_CENTER_IM,
  DEFAULT_JULIA_WIDTH,
  height=DEFAULT_JULIA_HEIGHT,
  point_re=DEFAULT_JULIA_RE,
  point_im=DEFAULT_JULIA_IM,
)


DEFAULT_FRAMES: dict[Fractal, Frame] = {
  Fractal.MANDELBROT: DEFAULT_MANDELBROT_FRAME,
  Fractal.JULIA: DEFAULT_JULIA_FRAME,
}


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ComputationParameters(SerializingFractalObject):
  """Arguments that determine a fractal computation completely (computation, not rendering).

  ATTENTION: changing any attribute changes the object SHA-256 hash.

  Attributes:
    frm (Frame): The rectangular region of the complex plane to compute.
    width (int): The image width in pixels.
    height (int): The image height in pixels.
    depth (int): The maximum number of Mandelbrot/Julia iterations to compute; default is
        MIN_ITER, which triggers automatic depth calculation at render time.
    set_points (SetHighlightAlgorithm | None): Optional interior Set highlight algorithm;
        if not None, interior (non-escaped) points are additionally tracked; default is None.

  """

  # ATTENTION: changing anything here changes the HASH!!
  frm: Frame
  width: int
  height: int
  depth: int = MIN_ITER
  set_points: SetHighlightAlgorithm | None = None

  def __post_init__(self) -> None:
    """Check parameters for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    # check width and height are valid
    if not (MIN_IMAGE_SIZE <= self.width <= MAX_IMAGE_SIZE) or not (
      MIN_IMAGE_SIZE <= self.height <= MAX_IMAGE_SIZE
    ):
      raise Error(
        f'{self.width=} and {self.height=} must be between {MIN_IMAGE_SIZE} and {MAX_IMAGE_SIZE}'
      )
    # check depth is valid
    if not (MIN_ITER <= self.depth <= MAX_ITER):
      raise Error(f'{self.depth=} must be between {MIN_ITER} and {MAX_ITER}')
    # check SetHighlightAlgorithm is supported
    if self.set_points and self.set_points not in {
      SetHighlightAlgorithm.MIN,
      SetHighlightAlgorithm.MAX,
      SetHighlightAlgorithm.ANGLE,
      SetHighlightAlgorithm.IMAGINARY,
    }:
      raise Error(f'Unsupported set highlight algorithm: {self.set_points}')

  def __str__(self) -> str:
    """Get string representation of the ComputationParameters.

    Format is:
      - "{[MANDELBROT: (c_re, c_im) ± (dx_re, dy_im)] : [w, h, d]}" WITHOUT set points; or
      - "{[MANDELBROT: (c_re, c_im) ± (dx_re, dy_im)] : [w, h, d] : <sp>}" WITH set point; or
      - "{[JULIA: (c_re, c_im) ± (dx_re, dy_im) @ (p_re, p_im)] : [w, h, d]}" WITHOUT set points; or
      - "{[JULIA: (c_re, c_im) ± (dx_re, dy_im) @ (p_re, p_im)] : [w, h, d] : <sp>}" WITH sp; and
      - "(c_re, c_im)" is the center of the frame; and
      - "(dx_re, dy_im)" is the size of the frame; and
      - "(p_re, p_im)" is the point for Julia, if any; and
      - if `dx_re` and `dy_im` are the same, we can simplify to "± dx" instead of "± (dx, dy)"; and
      - `w`/`h` are the width/height in pixels; and
      - `d` is the depth/iteration count, or "AUTO" if it is set to MIN_ITER; and
      - `<sp>` is the set highlight algorithm, lowercase, if any.

    Returns:
      str: String representation of the ComputationParameters.

    """
    return (
      '{'
      f'{self.frm} : '
      f'[{self.width}, {self.height}, {self.depth if self.depth > MIN_ITER else "AUTO"}]'
      + ('' if self.set_points is None else f' : {self.set_points.value.lower()}')
      + '}'
    )

  @property
  def size(self) -> tuple[int, int]:
    """Get the size of the image as (width, height).

    Returns:
      tuple[int, int]: The size of the image.

    """
    return (self.width, self.height)

  @property
  def disk_sz_bytes(self) -> int:
    """Estimate the size in bytes of one image.Image object as serialized to disk.

    Images are saved without histograms (ext_hist and int_hist are None at save time;
    they are rebuilt on demand via RebuildHistograms()).  Only two components are stored:

    1. Escape array (exact): width * height uint64 values at N_BYTES_UINT bytes each.
    2. One FractalStats object: 2 Python ints + 8 gmpy2.mpfr fields; mpfr at p bits
       costs 56 B (struct overhead) + ceil(p/64) * 8 B (mantissa limbs).

    For the in-RAM size with histograms (e.g., during animation rendering), use mem_sz_bytes.

    Returns:
      int: Estimated bytes occupied by a single serialized Image on disk (no histograms).

    """
    n_px: int = self.width * self.height
    # (1) escape array: exact -- width*height uint64 values at N_BYTES_UINT = 8 bytes each
    escape_sz: int = n_px * N_BYTES_UINT
    # (2) FractalStats (if present): 2 Python ints + 8 gmpy2.mpfr objects;
    #     mpfr at p bits ~= 56 bytes (Python/MPFR struct overhead) + ceil(p/64)*8 bytes (mantissa)
    mpfr_sz: int = 56 + ((self.precision + 63) // 64) * 8
    stats_sz: int = 2 * 28 + 8 * mpfr_sz  # 2 Python ints + 8 mpfr fields
    return escape_sz + stats_sz

  @property
  def mem_sz_bytes(self) -> int:
    """Estimate the size in bytes of one image.Image object in RAM after histograms are built.

    A rendered Image with histograms holds three main data structures:

    1. Escape array (exact): width * height uint64 values at N_BYTES_UINT bytes each.
    2. Two Histogram objects (ext_hist, int_hist), each storing exactly three fields:
       - d_cumulative dict (n_lin entries): unique integer escape values → cumulative counts
       - d_bucket_linear dict (n_buck entries): smooth bucket keys → counts
       - bucket_cumulative list (n_buck entries): sorted (bucket_key, cumulative_count) pairs
       n_lin: at most min(n_px, depth + SMOOTH_EXTRA_ITERS) distinct integer escape values
       n_buck: at most min(n_px, n_lin * 2048) distinct smooth bucket keys;
       2048 = image._HIST_SUB_BINS, written as literal to avoid circular import
    3. One FractalStats object: 2 Python ints + 8 gmpy2.mpfr fields; mpfr at p bits
       costs 56 B (struct overhead) + ceil(p/64) * 8 B (mantissa limbs).

    This estimate underpins animation memory planning -- for example, how much RAM is
    needed to hold all frames of a ZoomParameters animation simultaneously.
    For the on-disk size (no histograms), use disk_sz_bytes.

    Returns:
      int: Estimated bytes occupied by a single in-memory Image with histograms.

    """
    n_px: int = self.width * self.height
    # (1) escape array: exact -- width*height uint64 values at N_BYTES_UINT = 8 bytes each
    escape_sz: int = n_px * N_BYTES_UINT
    # (2) two Image.Histogram objects (ext_hist, int_hist); each histogram stores:
    #     - d_cumulative dict:      n_lin entries
    #     - d_bucket_linear dict:   n_buck entries
    #     - bucket_cumulative list: n_buck entries
    #     n_lin: at most min(n_px, depth+SMOOTH_EXTRA_ITERS) distinct integer escape values
    #     n_buck: at most min(n_px, n_lin * sub_bins) distinct smooth bucket keys;
    #     2048 = image._HIST_SUB_BINS, written as literal to avoid circular import
    n_lin: int = min(n_px, self.depth + SMOOTH_EXTRA_ITERS)
    n_buck: int = min(n_px, n_lin * 2048)  # 2048 = image._HIST_SUB_BINS
    # per-entry cost across 2 histograms:
    #   dict entry:  ~60-byte hash-table slot + 2*28-byte Python ints ~= 116 B
    #   list entry:   8-byte list slot + 56-byte (int,int) tuple + 2*28-byte ints ~= 120 B
    # n_lin dimension: 2 histograms * 1 d_cumulative dict      -> 2 * 116 = 232 B/entry
    # n_buck dimension: 2 * (1 d_bucket_linear dict + 1 bucket_cumulative list)
    #                  -> 2 * (116 + 120)                       = 472 B/entry
    bytes_per_lin_entry: int = 232
    bytes_per_buck_entry: int = 472
    hist_sz: int = n_lin * bytes_per_lin_entry + n_buck * bytes_per_buck_entry
    # (3) FractalStats (if present): 2 Python ints + 8 gmpy2.mpfr objects;
    #     mpfr at p bits ~= 56 bytes (Python/MPFR struct overhead) + ceil(p/64)*8 bytes (mantissa)
    mpfr_sz: int = 56 + ((self.precision + 63) // 64) * 8
    stats_sz: int = 2 * 28 + 8 * mpfr_sz  # 2 Python ints + 8 mpfr fields
    return escape_sz + hist_sz + stats_sz

  @property
  def comp_memory_sz_bytes(self) -> int:
    """Estimate the peak RAM in bytes needed to render a single frame.

    Rendering one frame uses up to fractal.MAX_CONCURRENCE (= 16) parallel processes
    simultaneously, each holding an Image in RAM (escape array + stats, no histograms yet
    during computation) plus mpfr working variables:

    - One Image per process (escape array + stats = disk_sz_bytes; histograms are not
      built until after computation completes).
    - ~25 scalar gmpy2.mpfr working variables (zx, zy, magnitude, angle, stats-tracking
      bounds, normalization temporaries, etc.).
    - One gmpy2.mpfr per image column (the xs pre-computation array, width values).

    mpfr memory scales with self.precision: 56 B struct overhead +
    ceil(precision/64) * 8 B mantissa limbs.  self.precision already includes the
    guard bits required for numerical accuracy at this zoom depth.

    Formula:
      max_concurrence * (disk_sz_bytes + (width + 25) * mpfr_sz)

    Returns:
      int: Estimated peak bytes in RAM during a single-frame render.

    """
    # each worker process holds one image.Image with escape array + stats but NO histograms
    # (histograms are rebuilt after the parallel computation phase completes)
    per_proc_image_sz: int = self.disk_sz_bytes
    # inside `with params.context:` each process maintains gmpy2.mpfr values at
    # self.precision bits; the dominant per-process mpfr cost is:
    #   - xs: width gmpy2.mpfr values (precomputed real-axis pixel coordinates, one per column)
    #   - ~25 scalar mpfr working variables: zx, zy, zx2, zy2, mag_z2, cy, cx, min_z2, max_z2,
    #       mpfr_pi, mpfr_two_pi, max_iter_p_1, and stats-tracking bounds (max_lo, max_hi,
    #       min_lo, min_hi, ang_lo, ang_hi, imag_lo, imag_hi) plus normalization temporaries;
    #       mpfr size grows with self.depth because self.precision adds 2*ceil(log2(depth+1))
    #       guard bits to maintain per-pixel numerical accuracy over the iteration loop
    n_working_mpfr: int = 25
    mpfr_sz: int = 56 + ((self.precision + 63) // 64) * 8  # Python/MPFR overhead + mantissa limbs
    per_proc_mpfr_sz: int = (self.width + n_working_mpfr) * mpfr_sz
    return MAX_CONCURRENCE * (per_proc_image_sz + per_proc_mpfr_sz)

  def png_sz_bytes(self) -> tuple[int, int]:
    """Estimate the on-disk size of the PNG and JPG output files in bytes.

    Both estimates include a metadata block for all frame/computation/render parameters
    stored as tEXt chunks (PNG) or an EXIF comment (JPG).  The dominant variable cost
    is the 8 mpq coordinate strings, each stored as "p/q" with ~precision * log10(2)
    decimal digits per integer:
      meta_sz = 5000 + 8 * 2 * (precision * 3 // 10 + 1)  bytes

    Pixel compression empirical estimates (calibrated: 2100x2100 fractal -> PNG=4.2 MB,
    JPG=1.7 MB at quality 95):
      PNG  (zlib/deflate, 3-byte RGB): ~1.0 byte/pixel  -- deflate handles smooth
           gradient regions efficiently; fractal boundaries limit the overall ratio.
      JPG  (JPEG quality 95):         ~0.4 bytes/pixel  -- DCT compresses the dominant
           smooth exterior very well; the sharp fractal boundary is a small fraction of
           total pixels, so JPEG is typically smaller than PNG for fractal images.

    Returns:
      tuple[int, int]: Estimated file sizes as (png_bytes, jpg_bytes).

    """
    n_px: int = self.width * self.height
    # metadata overhead: all frame/computation/render/image parameters stored in tEXt chunks
    # (PNG) or EXIF comment (JPG); ~50 key-value pairs with ~5 KB fixed overhead (keys ~35
    # chars, hash values 64 chars, int/float values 1-20 chars) plus coordinate mpq strings
    # for the 8 frame coordinates (top_re, top_im, bottom_re, bottom_im, center_re, center_im,
    # width_re, height_im); each mpq stored as "p/q" decimal: ~precision * log10(2) digits per int;
    # integer approx: precision * 3 // 10; total: 8 coords * 2 ints * (precision * 3 // 10 + 1) bt
    meta_sz: int = 5000 + 8 * 2 * (self.precision * 3 // 10 + 1)
    # PNG stores pixels as 3-byte RGB and compresses with zlib/deflate; fractal images mix
    # highly-compressible smooth gradient regions with poorly-compressible fractal boundaries;
    # empirically a 1024x1024 fractal PNG is ~1 MB (see DEFAULT_IMAGE_SIZE comment above),
    # which is ~3:1 compression of 3 MB of raw RGB data -> ~1 byte/pixel on average;
    # the actual compression ratio varies widely by zoom depth and frame content
    png_sz: int = n_px + meta_sz  # ~1 byte/pixel + metadata
    # JPEG at JPEG_QUALITY=95 (image.JPEG_QUALITY, written as literal to avoid circular import)
    # for fractal images: the large smooth gradient exterior regions compress very well with
    # DCT (they dominate most of the image area), more than offsetting the poorly-compressible
    # fractal boundary pixels; empirically 2100x2100 fractal JPG at quality 95 is ~1.7 MB vs
    # ~4.2 MB for the same frame as PNG, i.e. ~0.4 bytes/pixel vs ~1 byte/pixel for PNG;
    # so JPEG is typically SMALLER than PNG for fractal images, not larger
    jpg_sz: int = n_px * 2 // 5 + meta_sz  # ~0.4 bytes/pixel at quality 95 + metadata
    return (png_sz, jpg_sz)

  @property
  def json(self) -> tbase.JSONDict:
    """Get a JSON-serializable dictionary representation of the computation parameters.

    Keys: `frm`, `width`, `height`, `depth`, `set_points`, where `frm` is the frame as a JSON dict,
        `width` and `height` and `depth` are int, and `set_points` is str | None.

    Returns:
      tbase.JSONDict: A dictionary representation of the computation parameters.

    """
    # ATTENTION: changing anything here changes the HASH!!
    return {
      'frm': self.frm.json,
      'width': self.width,
      'height': self.height,
      'depth': self.depth,
      'set_points': self.set_points.value if self.set_points else None,
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> ComputationParameters:
    """Create a ComputationParameters from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from ComputationParameters.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the frame. If the
          calculated hash does not match, an error is raised.

    Returns:
      ComputationParameters: A ComputationParameters object

    Raises:
      Error: on error

    """
    # create the object
    try:
      params = ComputationParameters(  # object creation will check the data is valid and consistent
        frm=Frame.FromJson(cast('tbase.JSONDict', data['frm'])),  # also checks the data
        width=int(str(data['width'])),
        height=int(str(data['height'])),
        depth=int(str(data['depth'])),
        set_points=SetHighlightAlgorithm(data['set_points']) if data['set_points'] else None,
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid ComputationParameters JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'ComputationParameters {params.sha!r} does not match expected {check_hash!r}')
    return params

  def CoordToPixel(
    self, re_inp: ExactInputType, im_inp: ExactInputType
  ) -> tuple[tuple[gmpy2.mpq, gmpy2.mpq], tuple[int, int]]:
    """Convert complex-plane coordinates to pixel coordinates in the image.

    Calculate pixel coordinates, with (0, 0) at the top-left corner of the image and
    (pixel_width-1, pixel_height-1) at the bottom-right corner; we use floor to ensure
    that coordinates on the boundary between two pixels are assigned to the pixel above/left,
    which is important for consistency and to avoid out-of-bounds pixel coordinates;
    the calculations are exact mpq. Formula is:

    x = floor((re - top_re) / (bottom_re - top_re) * pixel_width)
    y = floor((top_im - im) / (top_im - bottom_im) * pixel_height)

    Args:
      re_inp (ExactInputType): Real part of the complex coordinate.
      im_inp (ExactInputType): Imaginary part of the complex coordinate.

    Returns:
      tuple[tuple[gmpy2.mpq, gmpy2.mpq], tuple[int, int]]: The (re, im) complex coordinates and
          the (x, y) pixel coordinates corresponding to the complex coordinate

    Raises:
      Error: If the input coordinates are outside the frame or if the image dimensions are invalid.

    """
    re: gmpy2.mpq = re_inp if isinstance(re_inp, gmpy2.mpq) else gmpy2.mpq(re_inp)
    im: gmpy2.mpq = im_inp if isinstance(im_inp, gmpy2.mpq) else gmpy2.mpq(im_inp)
    # check parameters
    if not (self.frm.top_re <= re <= self.frm.bottom_re) or not (
      self.frm.bottom_im <= im <= self.frm.top_im
    ):
      raise Error(f'coordinates ({re}, {im}) are outside the frame {self.frm}')
    # do computation
    x: int = int(
      gmpy2.floor(
        (re - self.frm.top_re) / (self.frm.bottom_re - self.frm.top_re) * gmpy2.mpq(self.width)
      )
    )
    y: int = int(
      gmpy2.floor(
        (self.frm.top_im - im) / (self.frm.top_im - self.frm.bottom_im) * gmpy2.mpq(self.height)
      )
    )
    return ((re, im), (min(max(x, 0), self.width - 1), min(max(y, 0), self.height - 1)))

  def CoordsTupleToPixel(self, inp: str) -> tuple[tuple[gmpy2.mpq, gmpy2.mpq], tuple[int, int]]:
    """Parse a complex-plane tuple coordinates to pixel coordinates in the image.

    See CoordToPixel() for more details.

    Args:
      inp (str): A string representing the complex coordinate in the format "(re, im)".

    Returns:
      tuple[tuple[gmpy2.mpq, gmpy2.mpq], tuple[int, int]]: The (re, im) complex coordinates and
          the (x, y) pixel coordinates corresponding to the complex coordinate

    Raises:
      Error: If the input string is not in the correct format or if the coordinates are invalid

    """
    # parse and check the mark_coords, which should be in the format "(re,im)"
    co_re: str
    co_im: str
    co_re, co_im = inp.split(',')
    co_re, co_im = co_re.strip(), co_im.strip()
    if not co_re.startswith('(') or not co_im.endswith(')'):
      raise Error(f'Expected "(re,im)" input got {inp!r}')
    # convert the coordinate to pixel and draw the overlay
    return self.CoordToPixel(co_re[1:], co_im[:-1])

  @property
  def precision(self) -> int:
    """Estimate the MPFR precision needed to render this frame at the requested image size.

    This method chooses a conservative MPFR precision, in bits, for Mandelbrot-style arbitrary
    precision computations over this frame. The goal is not merely to store the frame coordinates,
    but to perform repeated fractal iteration with enough numerical precision that arithmetic error
    is far smaller than a rendered pixel. The estimate is based on the smallest complex-plane
    distance represented by one output pixel and on the largest coordinate magnitude appearing in
    the frame:

        pixel_size = min( frame_width / pixel_width , frame_height / pixel_height )
        coordinates_magnitude = max( abs(top_re), abs(bottom_re), abs(top_im), abs(bottom_im) , 1 )

    MPFR precision is relative, not absolute. Around a value with magnitude M, the spacing between
    adjacent representable MPFR numbers is approximately proportional to M * 2**-precision.
    Therefore, resolving a pixel of size h requires roughly:

        precision >= log2(M / h)

    This method computes that base requirement exactly from rational frame geometry, then adds
    guard bits. The fixed guard budget gives substantial safety margin beyond merely distinguishing
    neighboring pixels, while the iteration guard grows logarithmically with max_iter to account for
    accumulated rounding error during repeated fractal iteration.

    The resulting precision is:

        max(
          _MPFR_MIN_PRECISION,
          ceil(log2(coordinates_magnitude / pixel_size)) +
          2 * ceil(log2(max_iter + 1)) +
          _MPFR_MIN_GUARD_BITS
        )

    Assumptions:
      * The frame coordinates are exact gmpy2.mpq values.
      * The requested pixel dimensions are the dimensions of the actual render target.
      * The renderer maps pixels into this frame using the same horizontal and vertical scale
        implied by pixel_width and pixel_height.
      * The relevant numerical scale is the smallest of the horizontal and vertical complex-plane
        pixel sizes.
      * max_iter is the expected upper bound for the number of fractal iterations performed per
        pixel.
      * The computation is intended for Mandelbrot-like iteration near ordinary complex-plane
        magnitudes, but the coordinates_magnitude term makes the estimate valid for frames whose
        coordinates are far from the origin as well.

    Promise:
      The returned precision is intended to make coordinate representation error and ordinary MPFR
      rounding error much smaller than one output pixel, with additional safety margin for repeated
      iteration. In practical terms, using this precision should prevent visible artifacts caused by
      insufficient floating-point precision for the requested frame size and iteration count.

      This method does not and cannot guarantee mathematically correct classification of every pixel
      near the Mandelbrot boundary. Points can lie arbitrarily close to the boundary, where deciding
      escape versus non-escape may require more precision, more iterations, or a different
      algorithm. The promise is instead that the chosen precision is conservative relative to the
      image resolution: numerical noise should be well below the pixel scale, so any remaining
      ambiguity should come from the fractal problem itself rather than from an obviously inadequate
      MPFR precision.

    Returns:
      int: The estimated number of bits of MPFR precision needed

    Raises:
      Error: If the image dimensions or iteration count are outside allowed limits, or if the
          estimated precision exceeds _MPFR_MAX_PRECISION

    """
    # calculate pixel size and magnitude-to-pixel ratio, EXACT mpq computations
    pixel_re: gmpy2.mpq = (self.frm.bottom_re - self.frm.top_re) / gmpy2.mpq(self.width)
    pixel_im: gmpy2.mpq = (self.frm.top_im - self.frm.bottom_im) / gmpy2.mpq(self.height)
    pixel_size: gmpy2.mpq = min(pixel_re, pixel_im)
    magnitude_to_pixel_ratio: gmpy2.mpq = self.frm.coordinates_magnitude / pixel_size
    # calculate the number of bits needed so that MPFR spacing at this magnitude << pixel size
    with PrecisionContext():
      iter_guard: int = 2 * int(gmpy2.ceil(gmpy2.log2(self.depth + 1)))
      base_bits: int = int(gmpy2.ceil(gmpy2.log2(magnitude_to_pixel_ratio)))
    # join it all; check for precision cap and return
    n_precision: int = max(_MPFR_MIN_PRECISION, base_bits + iter_guard + _MPFR_MIN_GUARD_BITS)
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


def _ReflectIndex(i: int, n: int) -> int:
  """Reflect an index i into the range [0, n-1] by reflecting at the boundaries.

  For example, with n=5, the sequence of reflected indices is:
  i:   ... -7 -6 -5 -4 -3 -2 -1  r(i): ...  2  1  0  1  2  i:    0  1  2  3  4  5  6  7  ...
  This is useful for symmetric boundary conditions in smoothing operations.

  Args:
    i (int): The input index, which can be any integer.
    n (int): The size of the range to reflect into; must be positive.

  Returns:
    int: The reflected index within the range [0, n-1].

  """
  if n == 1:
    return 0
  while i < 0 or i >= n:
    if i < 0:
      i = -i
    elif i >= n:
      i = 2 * n - 2 - i
  return i


def SmoothDepths(  # noqa: C901, PLR0912
  depths: list[int],
  *,
  floor_at_raw: bool = False,
  margin: float = 0.03,
  margin_full_scale: float = math.log(1.5),
  spike_window: int = 5,
  spike_down_sigma: float = 4.0,
  spike_up_sigma: float = 8.0,
  enable_spike_clamp: bool = True,
  smooth_weights: tuple[float, ...] = (0.05, 0.15, 0.60, 0.15, 0.05),
) -> list[int]:
  """Convert raw Mandelbrot max-iteration estimates d(i) into smoothed depths s(i).

  Notice that s(i) is guaranteed > MIN_ITER, so that they are never considered sentinel/"AUTO".
  But notice that we do accept inputs of d(i)==MIN_ITER they'll just come up as at least
  MIN_ITER+1 in the output.

  The default smoothing kernel is a centered 5-stop low-pass. In z-transform form:
    H(z)= 0.05 z^2 + 0.15 z + 0.60 + 0.15 z^{-1} + 0.05 z^{-2}
  Because it is symmetric, it has zero phase shift when applied offline. So a mini-brot
  feature at stop i does not get delayed into later frames the way a causal EMA would.
  This filter is centered, so it uses future samples.

  Pipeline:
    1. log(depth)
    2. robust local spike clamp
    3. centered low-pass FIR smoothing
    4. exp() back to depth
    5. optional safety floor at raw d(i)

  Args:
    depths (list[int]): Raw estimated depths d(i), all positive.
    floor_at_raw (bool): If True, s(i) is never below d(i). Safer, but may preserve upward spikes.
    margin (float): Safety multiplier applied after smoothing.
    margin_full_scale (float): Log-depth variation that activates the full margin.
    spike_window (int): Odd local window used for robust outlier clamping.
    spike_down_sigma (float): How strongly to clamp downward outliers in log space.
    spike_up_sigma (float): How strongly to clamp upward outliers in log space.
    enable_spike_clamp (bool): Whether to do the robust local clamp.
    smooth_weights (tuple[float, ...]): Centered FIR weights. Must have odd length and sum roughly
        to 1.

  Returns:
    list[int]: Smoothed integer depths s(i), MIN_ITER < s(i) <= MAX_ITER.

  Raises:
    Error: on error

  """
  # check parameters
  if not depths:
    return []
  if any(d < MIN_ITER for d in depths):
    raise Error(f'all depths must be positive, >= {MIN_ITER}')
  if not spike_window % 2:
    raise Error('spike_window must be odd')
  if not len(smooth_weights) % 2:
    raise Error('smooth_weights must have odd length')
  if margin < 0.0:
    raise Error('margin must be >= 0')
  if margin_full_scale <= 0.0:
    raise Error('margin_full_scale must be > 0')
  if sum(smooth_weights) <= 0.0:
    raise Error('smooth_weights must have positive sum')
  n_depths: int = len(depths)
  # preserve true constants exactly, except for the sentinel rule
  if all(d == depths[0] for d in depths):
    return [min(max(d, MIN_ITER + 1), MAX_ITER) for d in depths]
  # (1) log-domain signal
  lds: list[float] = [math.log(float(d)) for d in depths]
  # (2) robust local spike clamp
  if enable_spike_clamp and n_depths >= spike_window:
    half_spike: int = spike_window // 2
    xr: list[float] = []
    for i in range(n_depths):
      window: list[float] = [
        lds[j] for j in (_ReflectIndex(i + j, n_depths) for j in range(-half_spike, half_spike + 1))
      ]
      median: float = statistics.median(window)
      sigma: float = 1.4826 * statistics.median(abs(v - median) for v in window) + 1e-9
      xr.append(
        max(median - spike_down_sigma * sigma, min(median + spike_up_sigma * sigma, lds[i]))
      )
  else:
    xr = list(lds)
  # (3) centered low-pass smoothing
  weights: list[float] = [w / sum(smooth_weights) for w in smooth_weights]
  half_smooth: int = len(weights) // 2
  smoothed: list[int] = []
  for i, raw in enumerate(depths):
    yi: float = sum(
      w * xr[_ReflectIndex(i + k - half_smooth, n_depths)] for k, w in enumerate(weights)
    )
    # local variation controls the safety margin; if the local region is flat, no margin is applied
    local_values: list[float] = [
      xr[_ReflectIndex(i + k - half_smooth, n_depths)] for k in range(len(weights))
    ]
    local_variation: float = max(local_values) - min(local_values)
    effective_margin: float = 1.0 + (margin * min(1.0, local_variation / margin_full_scale))
    s: int = math.ceil(effective_margin * math.exp(yi))
    if floor_at_raw:
      s = max(math.ceil(raw), s)
    smoothed.append(min(max(s, MIN_ITER + 1), MAX_ITER))
  return smoothed


def DeepSize(obj: Any, *, seen: set[int] | None = None) -> int:  # noqa: ANN401, C901
  """Recursively estimate the deep size of a Python object in bytes, including nested objects.

  Args:
    obj (Any): The object to estimate the size of.
    seen (set[int] | None): A set of object IDs that have already been seen during the recursion
        to avoid infinite loops with circular references. This should not be provided by the caller.

  Returns:
      int: An estimate of the deep size of the object in bytes.

  """
  # start with empty set() if not given
  seen = set() if seen is None else seen
  # check for circular references
  obj_id: int = id(obj)
  if obj_id in seen:
    return 0
  seen.add(obj_id)
  # base size of the object itself
  size: int = sys.getsizeof(obj)
  # recursively add size of nested objects based on type
  # dataclasses: add size of each field
  if dataclasses.is_dataclass(obj):
    for field in dataclasses.fields(obj):
      size += DeepSize(getattr(obj, field.name), seen=seen)
    return size
  # mappings: add size of keys and values
  if isinstance(obj, abc.Mapping):
    key: Any
    value: Any
    for key, value in obj.items():  # pyright: ignore[reportUnknownVariableType]
      size += DeepSize(key, seen=seen)
      size += DeepSize(value, seen=seen)
    return size
  # iterables: add size of each item; but treat strings and bytes as atomic (don't count each char)
  if isinstance(obj, (str, bytes, bytearray)):
    return size
  # iterables: add size of each item
  if isinstance(obj, abc.Iterable):
    item: Any
    for item in obj:  # pyright: ignore[reportUnknownVariableType]
      size += DeepSize(item, seen=seen)
  # objects with __dict__: add size of the __dict__ attributes
  if hasattr(obj, '__dict__'):  # pyright: ignore[reportUnknownArgumentType]
    size += DeepSize(vars(obj), seen=seen)
  # objects with __slots__: add size of each slot attribute if it exists
  if hasattr(obj, '__slots__'):  # pyright: ignore[reportUnknownArgumentType]
    slot: str
    for slot in obj.__slots__:  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportAttributeAccessIssue]
      if hasattr(obj, slot):  # pyright: ignore[reportUnknownArgumentType]
        size += DeepSize(getattr(obj, slot), seen=seen)  # pyright: ignore[reportUnknownArgumentType]
  # return the total size
  return size


def ConcurrenceToUse(n_processes: int | None = None) -> int:
  """Determine the number of concurrent processes to use for rendering based on the system limits.

  Args:
    n_processes (int | None): The desired number of processes to use. If None, it will default
        to the number of available CPU cores.

  Returns:
    int: The number of processes to use, which will be a positive integer not exceeding the
        available CPU cores or MAX_CONCURRENCE.

  Raises:
    Error: If n_processes is provided and is not a positive integer.

  """
  if n_processes is not None and n_processes < 1:
    raise Error(f'{n_processes=} must be a positive integer or None')
  return min(n_processes or AVAILABLE_CPU, MAX_CONCURRENCE, AVAILABLE_CPU)  # never exceed CPU!
