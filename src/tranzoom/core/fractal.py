# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing.

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>
"""

from __future__ import annotations

import gmpy2
import tqdm

from tranzoom.core import frame, image

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
  max_iter: int = frame.DEFAULT_ITER,
  progress_bar: bool = True,
) -> image.Image:
  """Render the frame rectangle to an Image.

  Args:
    frm (Frame): The frame to render.
    width (int): The width of the output image in pixels.
    height (int): The height of the output image in pixels.
    max_iter (int, optional): The maximum number of iterations to determine escape.
        Defaults to frame.DEFAULT_ITER.
    progress_bar (bool, optional): Whether to show a progress bar. Defaults to True.

  Returns:
    image.Image: The rendered fractal image.

  Raises:
    Error: on error

  """
  # create image; will also check the parameters and frame validity in the Image constructor
  img: image.Image = image.Image(frm, width, height, max_iter)
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
  # done
  return img
