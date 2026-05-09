# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing.

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>
"""

from __future__ import annotations

import logging

import gmpy2
import tqdm

from tranzoom.core import frame, image

# iteration constants

MIN_ITER: int = 1000
DEFAULT_ITER: int = 1000
HIGH_ITERS: list[int] = [100_000, 1_000_000, 10_000_000]  # these are very high iteration counts
MAX_ITER: int = 2 ** (image.N_BYTES_UINT * 8) - 1  # 4_294_967_295, max value for array('I'), uint32

# automated search for iter

_ITER_SAFETY_FACTOR: float = 1.5  # we multiply the estimated iter by this to be safe

# gmpy2.mpfr constants
_MPFR_ZERO = gmpy2.mpfr('0')
_MPFR_SIXTEENTH = gmpy2.mpfr('0.0625')
_MPFR_FOURTH = gmpy2.mpfr('0.25')
_MPFR_ONE = gmpy2.mpfr('1')
_MPFR_TWO = gmpy2.mpfr('2')
_MPFR_FOUR = gmpy2.mpfr('4')


class Error(image.Error):
  """Base fractal exception."""


def Mandelbrot(  # noqa: PLR0914
  frm: frame.Frame,
  width: int,
  height: int,
  *,
  max_iter: int | None = None,
  progress_bar: bool = True,
) -> image.Image:
  """Render the frame rectangle to an Image.

  Args:
    frm (Frame): The frame to render.
    width (int): The width of the output image in pixels.
    height (int): The height of the output image in pixels.
    max_iter (int | None, optional): The maximum number of iterations to determine escape.
        Defaults to None, and that means "auto".
    progress_bar (bool, optional): Whether to show a progress bar. Defaults to True.

  Returns:
    image.Image: The rendered fractal image.

  Raises:
    Error: on error

  """
  # if max_iter is None, we do an adaptive iteration limit calculation based on a small test render
  max_iter = _MandelbrotAdaptiveIterations(frm, progress_bar) if max_iter is None else max_iter
  # sanity check the iter_limit: if error, it came from the user (b/c adaptive clamps to the limits)
  if not (MIN_ITER <= max_iter <= MAX_ITER):
    raise Error(f'{max_iter=} must be between {MIN_ITER} and {MAX_ITER}')
  # create image; will also check the parameters and frame validity in the Image constructor
  img: image.Image = image.Image(frm, width, height)
  # compute pixel size in complex plane and check frame validity; exact computation (gmpy2.mpq)
  dx: gmpy2.mpq
  dy: gmpy2.mpq
  dx, dy = frm.size
  dx, dy = dx / gmpy2.mpq(width - 1), dy / gmpy2.mpq(height - 1)
  if dx <= 0 or dy <= 0:
    raise Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
  # start the mpfr context for floating-point computations with the precision needed
  with frm.context:
    # precompute x coordinates once: this matters because mpfr construction and arithmetic
    # are relatively expensive and we can reuse the x values across rows ("inner for loop");
    # also, this is where the "X" (real) coordinates are converted mpq->mpfr
    xs: list[gmpy2.mpfr] = [gmpy2.mpfr(frm.top_re + gmpy2.mpq(i) * dx) for i in range(width)]
    # create progress bar based on total pixels and the options
    p_bar: tqdm.tqdm[int] = tqdm.tqdm(
      iterable=range(width * height),
      desc='Pre' if width == frame.MIN_IMAGE_SIZE and height == frame.MIN_IMAGE_SIZE else 'Img',
      unit='px',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='green',
      disable=not progress_bar,
    )
    # iterate over pixels in row-major order, computing escape iterations in mpfr
    for py in range(height):
      # PILImage.frombytes interprets the first row written as the top row of the image, so
      # we iterate y inverted by starting at the top and going down;
      # this is the "outer for loop", no benefit in pre-computing y values;
      # also, this is where the "Y" (imaginary) coordinates are converted mpq->mpfr
      cy: gmpy2.mpfr = gmpy2.mpfr(frm.top_im - gmpy2.mpq(py) * dy)
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
          img.escape[py * width + px] = max_iter  # carefully set this directly in the array
          p_bar.update(1)  # we touched a pixel, so update the progress bar
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
        img.escape[py * width + px] = escaped_at  # carefully set this directly in the array
        p_bar.update(1)  # we touched a pixel, so update the progress bar
  # done
  return img


def _MandelbrotAdaptiveIterations(frm: frame.Frame, progress_bar: bool) -> int:
  """Estimate a suitable max_iter for the full image by rendering a small test image.

  Current algorithm:
  - Render a very small image (MIN_IMAGE_SIZE x MIN_IMAGE_SIZE) with a very high iteration limit
    (HIGH_ITERS, starting with 100k and going up to 10M if needed).
  - Build a histogram of escape iterations for the small image, and find the highest escape
    iteration that is below the high iteration limit.
  - Multiply that escape iteration by a safety factor _ITER_SAFETY_FACTOR to get the estimated
    max_iter for the full image.
  - If the estimated max_iter is above the high iteration limit, try again with a higher
    high iteration limit from HIGH_ITERS.
  - If we exhaust all high iteration limits in HIGH_ITERS without finding a suitable max_iter,
    raise an Error.

  Args:
    frm (Frame): The frame to render.
    progress_bar (bool): Whether to show a progress bar during the test render.

  Returns:
    int: The estimated max_iter for the full image, based on the escape histogram of the test render

  Raises:
    Error: if the estimated max_iter exceeds the adaptive limit

  """
  max_iter: int = MAX_ITER
  for high_iter in HIGH_ITERS:
    # make the smallest image
    img16: image.Image = Mandelbrot(
      frm,
      frame.MIN_IMAGE_SIZE,
      frame.MIN_IMAGE_SIZE,
      max_iter=high_iter,
      progress_bar=progress_bar,
    )
    # estimate the needed iterations for the full image based on the smallest image;
    # make the histogram of escape iterations for the smallest image, and find the highest escape
    escape_histogram: dict[int, int] = {}
    for escaped_at in img16.escape:
      escape_histogram[escaped_at] = escape_histogram.get(escaped_at, 0) + 1
    # sort the histogram by escape iteration; find the highest escape iteration that < high limit
    histogram: list[tuple[int, int]] = sorted(escape_histogram.items())
    max_iter = (
      histogram[-1][0] if histogram[-1][0] != high_iter or len(histogram) == 1 else histogram[-2][0]
    )
    # apply safety factor and clamp
    max_iter = min(MAX_ITER, max(MIN_ITER, int(max_iter * _ITER_SAFETY_FACTOR)))
    if max_iter < high_iter:
      # we found a winner!
      if len(histogram) > 7:  # noqa: PLR2004 ; 7 is 3 before, the middle, and 3 after
        # this is usually the case: many escape values, so summarize the middle ones
        summary_histogram: list[tuple[int, int] | tuple[str, int]] = [
          *histogram[:3],
          ('...', sum(count for _, count in histogram[3:-3])),
          *histogram[-3:],
        ]
        logging.warning(f'Picked {max_iter=}: histogram {summary_histogram}')
      else:
        # probably a pretty rare thing, but then we can show all
        logging.warning(f'Picked {max_iter=}: histogram {histogram}')
      # stop here
      return max_iter
    # here we didn't find, so we loop to the next higher limit...
  # if we exhausted all the high_iters without finding a suitable max_iter, we have to give up
  raise Error(f'Estimated {max_iter=} is above the adaptive limit of {HIGH_ITERS[-1]}')
