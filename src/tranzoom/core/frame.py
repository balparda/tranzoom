# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Frame: a rectangular region of the complex plane, with arbitrary precision. Exact."""

from __future__ import annotations

import dataclasses
import enum
import fractions
from collections import abc
from typing import cast

import gmpy2
from transcrypto.utils import base as tbase

# basic constants

type ExactInputType = str | float | gmpy2.mpq
MIN_IMAGE_SIZE: int = 16  # BEWARE: we use this for the "auto" depth calculation, so not too small!
MAX_IMAGE_SIZE: int = 16 * 1024  # huge image, 16k x 16k, 256Mpx, tens or hundreds of Mb per image
DEFAULT_IMAGE_SIZE: int = 1024  # good all-around default, 1Mpx, ~1Mb per image (compressed)
DEFAULT_ZOOM_SIZE: int = 512  # smaller default for zoom, since it can be more expensive

# iteration constants

N_BYTES_UINT: int = 4  # we use array of int32 to store pixel data / array.array('i') / signed 32
MIN_ITER: int = 1000  # minimum, but also a mark that we want to automatically calculate the depth
DEFAULT_ITER: int = 1000
HIGH_ITERS: list[int] = [100_000, 1_000_000, 10_000_000]  # these are very high iteration counts
SET_INTERIOR_RESOLUTION: int = 100_000_000  # interior points max val [0..SET_INTERIOR_RESOLUTION]
MAX_ITER: int = 2 ** (N_BYTES_UINT * 8 - 1) - 1  # ± 2_147_483_647, max value for array('i'), int32

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
DEFAULT_MPQ_ZOOM: gmpy2.mpq = gmpy2.mpq('5/3')  # 1.67
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


# TODO: create (optional) DB of stored frames
# TODO: for videos compute all mpq steps first with full mpq, then simplify fraction to 0.01% error;
#     frames are now deterministic and as reasonably small as possible, they are the entries to DB
# TODO: video/gif to save check the frames for existence, thus recovering from a crash
# TODO: image to store: on non-set/escaped the iteration plus a float(?) to compute "nu"
# TODO: image to store: on set/non-escaped the actual final value of the tracked constant;
#     and if we store the mpfr on a dict for example, we will have space for more info in the array
# TODO: make a way for images to be saved too, raw, so we can revisit computations;
#     what parameters REALLY determine an image pre-render?
# TODO: with all the frames in place (DB) and richer images and "nu" we can start video smoothing;
#     a class for video objects with all the frames
# TODO: before rendering video, decide on marker frames every X magnitude, make them first,
#     use them to compute colors and then smooth colors between maker frames smoothly


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
class Frame:
  """Defines a rectangular region of the complex plane, with arbitrary precision. Exact.

  An optional point coordinate is included. This is used for Julia, and ignored for Mandelbrot.
  This point is not required to be inside the rectangle; it is just an additional coordinate
  that can be used for various purposes, such as marking a specific location in the image or
  providing additional data like for the Julia fractal.
  """

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

  def __str__(self) -> str:
    """Get string representation of the frame.

    Format is:
      - "[MANDELBROT: (c_re, c_im) ± (dx_re, dy_im)]" without the point for Mandelbrot; or
      - "[JULIA: (c_re, c_im) ± (dx_re, dy_im) @ (p_re, p_im)]" for Julia; and note
      - "(c_re, c_im)" is the center of the frame; and
      - "(dx_re, dy_im)" is the size of the frame; and
      - "(p_re, p_im)" is the point for Julia, if any; and
      - if `dx_re` and `dy_im` are the same, we can simplify to "± dx" instead of "± (dx, dy)".

    Returns:
      str: String representation of the frame.

    Raises:
      Error: if the fractal type is unknown (should not happen b/c checked in __post_init__).

    """
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
  def magnification(self) -> tuple[gmpy2.mpfr, float]:
    """Get frame magnification: How much "zoom" this frame has in relation to the whole set.

    sqrt( DEFAULT_FRAMES[self.fractal].area / self.area ) i.e., sqrt( WHOLE / this )

    Returns:
      tuple[gmpy2.mpfr, float]: (magnification, log10(magnification))

    """
    with PrecisionContext():
      magnification: gmpy2.mpfr = cast(
        'gmpy2.mpfr', gmpy2.sqrt(DEFAULT_FRAMES[self.fractal].area / self.area)
      )
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
class ComputationParameters:
  """Arguments that determine a fractal computation completely (computation, not rendering)."""

  frm: Frame
  width: int
  height: int
  depth: int = MIN_ITER
  set_points: SetHighlightAlgorithm | None = None

  def __post_init__(self) -> None:
    """Check rectangle has an area and top/bottom ordering.

    Raises:
      Error: if the rectangle is invalid.

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
    """Get string representation of the computation parameters.

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
      str: String representation of the computation parameters.

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

  def CoordToPixel(self, re_inp: ExactInputType, im_inp: ExactInputType) -> tuple[int, int]:
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
      tuple[int, int]: The (x, y) pixel coordinates corresponding to the complex coordinate.

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
    return (min(max(x, 0), self.width - 1), min(max(y, 0), self.height - 1))

  def CoordsTupleToPixel(self, inp: str) -> tuple[int, int]:
    """Parse a complex-plane tuple coordinates to pixel coordinates in the image.

    See CoordToPixel() for more details.

    Args:
      inp (str): A string representing the complex coordinate in the format "(re, im)".

    Returns:
      tuple[int, int]: The (x, y) pixel coordinates corresponding to the complex coordinate

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


def MPQFromFloatApprox(value: float, max_denominator: int) -> gmpy2.mpq:
  """Convert a float to a gmpy2.mpq, using fractions.Fraction to find a good rational approximation.

  Args:
    value (float): The float value to convert.
    max_denominator (int): The maximum denominator to use for the approximation.

  Returns:
    gmpy2.mpq: The rational approximation of the float as a gmpy2.mpq.

  """
  frac: fractions.Fraction = fractions.Fraction(value).limit_denominator(max_denominator)
  return gmpy2.mpq(frac.numerator, frac.denominator)
