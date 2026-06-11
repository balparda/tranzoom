# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing, PYTHON.

<https://cython.readthedocs.io/en/latest/>

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>

BEWARE when debugging/editing this module:

On MacOS (Python ≥ 3.8) --- and presumably on other systems too --- the default multiprocessing
start method is "spawn", not "fork". With spawn, each worker process is a fresh Python interpreter
that re-imports all modules from disk when it starts. This means that unless `--threads` is
manually set to 1, the code will reload for every worker every time an image is rendered.

This means that if you are executing some long computation with many fractals (think animation),
and you start editing this part of the codebase, you may break your running computation in
really ugly ways.
"""

import math
import struct
import warnings
from typing import NoReturn, cast

import cython  # type: ignore[import-untyped]
import gmpy2
import tqdm.rich
from tqdm.std import TqdmExperimentalWarning

from tranzoom.core import frame, image

# gmpy2 C-API initialization: import_gmpy2() is declared in gmpy2.pxd and MUST be called
# in every Cython extension module that uses gmpy2 extension types via the C-API.
# The if-block is a no-op in plain Python mode (cython.compiled is False at runtime when
# not compiled); when compiled, Cython rewrites cython.compiled to True and the import
# resolves to the real C-level symbol from gmpy2.pxd.
if cython.compiled:  # True only when compiled with Cython; False in plain Python mode
  from cython.cimports.gmpy2 import import_gmpy2  # type: ignore

  import_gmpy2()

CYTHON: bool = cython.compiled

# gmpy2.mpfr constants
_MPFR_ZERO: gmpy2.mpfr = gmpy2.mpfr('0')
_MPFR_SIXTEENTH: gmpy2.mpfr = gmpy2.mpfr('0.0625')
_MPFR_FOURTH: gmpy2.mpfr = gmpy2.mpfr('0.25')
_MPFR_HALF: gmpy2.mpfr = gmpy2.mpfr('0.5')
_MPFR_ONE: gmpy2.mpfr = gmpy2.mpfr('1')
_MPFR_TWO: gmpy2.mpfr = gmpy2.mpfr('2')
_MPFR_FOUR: gmpy2.mpfr = gmpy2.mpfr('4')


def NormalizeSmoothEscape(n: int, nu: float) -> tuple[int, float]:
  """Normalize the smooth escape part to be in [0,1) and adjust n accordingly.

  The smooth escape part is a fractional value that represents how far the orbit went beyond
  the escape radius at the escape iteration. We want to ensure that the final escape value
  is n + nu, where n is an integer and nu is in [0,1). This allows for smooth coloring
  of the escape time.

  Args:
    n (int): The integer escape iteration count.
    nu (float): The smooth escape part, which can be any real number.

  Returns:
    tuple[int, float]: A tuple of the adjusted integer escape iteration and the normalized
        smooth escape part.

  Raises:
    image.Error: if the normalized smooth escape part is not in [0,1) after normalization

  """
  # if nu is not finite consider it an error
  if not math.isfinite(nu):
    raise image.Error(f'nu is not a valid number {nu=}, bug! report')
  # get the integer shift to apply to n, and the new nu in [0,1)
  shift: int = math.floor(nu)
  n += shift
  nu -= shift
  # if nu is negative, we need to shift back the other way, to ensure nu is in [0,1)
  if nu < 0.0:
    n -= 1
    nu += 1.0
  # ensure n is not negative, in case the shift made it negative
  n = max(0, n)
  if not math.isfinite(nu) or not (0.0 <= nu < 1.0):
    raise image.Error(f'Normalized smooth escape range 0 <= {nu=} < 1, {n=}, bug! report')
  return (n, nu)


def NormalizeSmoothSet(
  val: gmpy2.mpfr, lo_bound: gmpy2.mpfr, lo_hi_range: gmpy2.mpfr
) -> tuple[int, float]:
  """Normalize a value for Set points to be in [1, SET_INTERIOR_INT_MAX] with a fractional part.

  Args:
    val (gmpy2.mpfr): The value to normalize, which can be any real number.
    lo_bound (gmpy2.mpfr): The lower bound of the range for normalization.
    lo_hi_range (gmpy2.mpfr): The size of the range for normalization (hi - lo).

  Returns:
    tuple[int, float]: A tuple of the integer part (in -[1, SET_INTERIOR_INT_MAX]) and the
        fractional part (in [0,1)) of the normalized value.

  Raises:
    image.Error: on error

  """
  if lo_hi_range <= 0:
    raise image.Error(f'Invalid normalization range: {lo_hi_range=}, should be > 0, bug! report')
  # scale to [0, 1]
  norm: gmpy2.mpfr = max(_MPFR_ZERO, min(_MPFR_ONE, (val - lo_bound) / lo_hi_range))
  # re-scale/stretch to [1, 1 + MPFR_SET_INTERIOR_INT_SPAN] == [1, SET_INTERIOR_INT_MAX]
  scaled: gmpy2.mpfr = _MPFR_ONE + norm * frame.MPFR_SET_INTERIOR_INT_SPAN
  # convert to int, clamp to [1, SET_INTERIOR_INT_MAX]
  whole: int = min(frame.SET_INTERIOR_INT_MAX, max(1, int(gmpy2.floor(scaled))))
  # compute the fractional part
  frac_mpfr: gmpy2.mpfr = scaled - gmpy2.mpfr(whole)
  # defensive only: normal operation frac_mpfr is already in [0, 1)
  if frac_mpfr < _MPFR_ZERO:
    frac_mpfr = _MPFR_ZERO
  elif frac_mpfr >= _MPFR_ONE:
    if whole < frame.SET_INTERIOR_INT_MAX:
      whole += 1
      frac_mpfr -= _MPFR_ONE
    else:
      frac_mpfr = _MPFR_ZERO
  # convert to float and check again
  frac: float = float(frac_mpfr)
  if not math.isfinite(frac) or not (0.0 <= frac < 1.0):
    raise image.Error(f'Invalid normalized Set fractional part: {frac=}, {whole=}, {scaled=}')
  return (-whole, frac)


def EncodeIntFloatTo64(i: int, f: float) -> int:
  """Encode a signed int32 and a float32 into a single uint64, by concatenating their bits.

  This is benchmarked at ~1.6ns per call, ~160ms for a 1024x1024 image to encode all pixels.
  struct.pack()/unpack() does range checks already, so we DO NOT check inputs, as that degrades
  performance by a lot. We also use pre-compiled struct formats to speed this up.

  Args:
    i (int): The signed int32 to encode.
    f (float): The float32 to encode; garbage in, garbage out: if the float is not
        valid/finite (NaN or Inf), you will get the same garbage float back on Decode64ToIntFloat().

  Returns:
    int: The encoded uint64 containing both the int and float.

  Raises:
    image.Error: inputs out of range or other encoding issues

  """
  try:
    return cast('int', image.PACK_Q.unpack(image.PACK_IF.pack(i, f))[0])
  except (struct.error, OverflowError) as err:
    raise image.Error(f'Error encoding {i=} and {f=} to uint64: {err}') from err


def MandelbrotComputation(inp: image.FractalTaskInput) -> image.FractalTaskOutput:  # noqa: C901, PLR0912, PLR0914, PLR0915
  """Compute the Mandelbrot image for the given task input. ONE THREAD FOR MULTIPROCESSING.

  Args:
    inp (image.FractalTaskInput): The task input containing all parameters for the computation.

  Returns:
    image.FractalTaskOutput: The rendered fractal image and task information.

  Raises:
    image.Error: on error

  """
  is_preprocess: bool = (
    inp.params.width == frame.MIN_IMAGE_SIZE and inp.params.height == frame.MIN_IMAGE_SIZE
  )
  # create image; will also check the parameters and frame validity in the Image constructor
  img: image.Image = image.Image(inp.params)
  # compute pixel size in complex plane and check frame validity; exact computation (gmpy2.mpq)
  dx: gmpy2.mpq
  dy: gmpy2.mpq
  dx, dy = inp.params.frm.size
  dx, dy = dx / gmpy2.mpq(inp.params.width - 1), dy / gmpy2.mpq(inp.params.height - 1)
  if dx <= 0 or dy <= 0:
    raise image.Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
  # start the mpfr context for floating-point computations with the precision needed
  with inp.params.context:  # noqa: PLR1702
    # precompute x coordinates once: this matters because mpfr construction and arithmetic
    # are relatively expensive and we can reuse the x values across rows ("inner for loop");
    # also, this is where the "X" (real) coordinates are converted mpq->mpfr
    xs: list[gmpy2.mpfr] = [
      gmpy2.mpfr(inp.params.frm.top_re + gmpy2.mpq(i) * dx) for i in range(inp.params.width)
    ]
    # variables for stats we will track; we pre-compute all we can!
    mpfr_pi: gmpy2.mpfr = gmpy2.const_pi()  # pi with the current context precision
    mpfr_two_pi: gmpy2.mpfr = _MPFR_TWO * mpfr_pi  # 2*pi with the current context precision
    max_iter_p_1: gmpy2.mpfr = gmpy2.mpfr(inp.params.depth) + _MPFR_ONE
    n_interior: int = 0  # track how many points are interior (non-escaping)
    max_lo: gmpy2.mpfr = _MPFR_FOUR
    max_hi: gmpy2.mpfr = _MPFR_ZERO
    min_lo: gmpy2.mpfr = _MPFR_FOUR
    min_hi: gmpy2.mpfr = _MPFR_ZERO
    ang_lo: gmpy2.mpfr = _MPFR_ONE
    ang_hi: gmpy2.mpfr = _MPFR_ZERO
    imag_lo: gmpy2.mpfr = _MPFR_ONE
    imag_hi: gmpy2.mpfr = _MPFR_ZERO
    stats_max: bool = False
    sqrt_lo: gmpy2.mpfr = _MPFR_ZERO
    sqrt_delta: gmpy2.mpfr = _MPFR_ZERO
    stats_min: bool = False
    sqrt_lo2: gmpy2.mpfr = _MPFR_ZERO
    sqrt_delta2: gmpy2.mpfr = _MPFR_ZERO
    stats_ang: bool = False
    ang_delta: gmpy2.mpfr = _MPFR_ZERO
    stats_imag: bool = False
    imag_delta: gmpy2.mpfr = _MPFR_ZERO
    if inp.stats is not None:
      # stats_max/min/ang/imag are True only when pre-stats were collected (non-None) AND there is
      # a valid range to normalize against (hi > lo); used to decide normalization strategy below
      if stats_max := (
        inp.stats.max_lo is not None
        and inp.stats.max_hi is not None
        and inp.stats.max_hi > inp.stats.max_lo
      ):
        sqrt_lo = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.max_lo))  # pyright: ignore[reportArgumentType]
        sqrt_delta = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.max_hi) - sqrt_lo)  # pyright: ignore[reportArgumentType]
      if stats_min := (
        inp.stats.min_lo is not None
        and inp.stats.min_hi is not None
        and inp.stats.min_hi > inp.stats.min_lo
      ):
        sqrt_lo2 = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.min_lo))  # pyright: ignore[reportArgumentType]
        sqrt_delta2 = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.min_hi) - sqrt_lo2)  # pyright: ignore[reportArgumentType]
      if stats_ang := (
        inp.stats.ang_lo is not None
        and inp.stats.ang_hi is not None
        and inp.stats.ang_hi > inp.stats.ang_lo
      ):
        ang_delta = inp.stats.ang_hi - inp.stats.ang_lo  # pyright: ignore[reportOperatorIssue, reportUnknownVariableType]
      if stats_imag := (
        inp.stats.imag_lo is not None
        and inp.stats.imag_hi is not None
        and inp.stats.imag_hi > inp.stats.imag_lo
      ):
        imag_delta = inp.stats.imag_hi - inp.stats.imag_lo  # pyright: ignore[reportOperatorIssue, reportUnknownVariableType]
    # create progress bar based on total pixels and the options
    has_procs: bool = inp.total_tasks > 1
    n_task: int = inp.n_task - 1  # convert to 0-based index for easier modulo math
    with warnings.catch_warnings():
      warnings.simplefilter('ignore', category=TqdmExperimentalWarning)
      p_bar: tqdm.rich.tqdm[NoReturn] = tqdm.rich.tqdm(
        total=inp.params.width * inp.params.height,
        desc='Pre' if is_preprocess else 'Img',
        unit='px',
        dynamic_ncols=True,
        smoothing=0.1,
        colour='green',
        disable=not inp.progress_bar or (has_procs and n_task != 0),  # show for the 1st process
      )
    # iterate over pixels in row-major order, computing escape iterations in mpfr
    px_count: int = -1
    for py in range(inp.params.height):
      # PILImage.frombytes interprets the first row written as the top row of the image, so
      # we iterate y inverted by starting at the top and going down;
      # this is the "outer for loop", no benefit in pre-computing y values;
      # also, this is where the "Y" (imaginary) coordinates are converted mpq->mpfr
      cy: gmpy2.mpfr = gmpy2.mpfr(inp.params.frm.top_im - gmpy2.mpq(py) * dy)
      # iterate over columns, reusing x values and doing the escape test in mpfr for correctness
      for px in range(inp.params.width):
        px_count += 1
        if has_procs and (px_count % inp.total_tasks) != n_task:
          # this pixel is not for this process, skip it but still update the progress bar
          p_bar.update(1)
          continue
        # either this is a solo process, or this pixel is for this process
        cx: gmpy2.mpfr = xs[px]
        # fast interior tests, all in mpfr: main cardioid and period-2 bulb
        # we can't do these tests for the other highlight algorithms, b/c we need to track
        # the max|z|/angle/etc for interior points, so we have to do the full escape-time
        # test in mpfr for all points, even those that would be interior by the fast tests
        if inp.params.set_points is None:
          # main cardioid test
          # see <https://en.wikipedia.org/wiki/Mandelbrot_set#Main_cardioid_and_period_bulbs>
          x_minus_quarter: gmpy2.mpfr = cx - _MPFR_FOURTH
          q: gmpy2.mpfr = x_minus_quarter * x_minus_quarter + cy * cy
          if q * (q + x_minus_quarter) <= _MPFR_FOURTH * cy * cy:
            # point is in the main cardioid, so it's an interior point, no escape
            # mark negative so as to mark it as interior
            n_interior += 1
            img.escape[px_count] = EncodeIntFloatTo64(-frame.SET_INTERIOR_INT_MAX, 0.0)
            p_bar.update(1)  # we touched a pixel, so update the progress bar
            continue
          # period-2 bulb test
          x_plus_one: gmpy2.mpfr = cx + _MPFR_ONE
          if x_plus_one * x_plus_one + cy * cy <= _MPFR_SIXTEENTH:
            # point is in the period-2 bulb, so it's an interior point, no escape
            # mark negative so as to mark it as interior
            n_interior += 1
            img.escape[px_count] = EncodeIntFloatTo64(-frame.SET_INTERIOR_INT_MAX, 0.0)
            p_bar.update(1)  # we touched a pixel, so update the progress bar
            continue
        # not in the main cardioid or period-2 bulb, do the full escape-time test in mpfr
        zx: gmpy2.mpfr = _MPFR_ZERO  # zx/zy -> the z in the iteration z = z^2 + c
        zy: gmpy2.mpfr = _MPFR_ZERO
        min_z2: gmpy2.mpfr = _MPFR_FOUR  # track min |z|^2 for potential use in coloring
        max_z2: gmpy2.mpfr = _MPFR_ZERO  # track max |z|^2 for potential use in coloring
        mag_z2: gmpy2.mpfr
        escaped_at: int = 0
        smooth_escape: float = 0.0
        imag_acc: gmpy2.mpfr = _MPFR_ZERO  # accumulate sin(arg(z)) over orbit for smooth SAC
        # escape-time loop, implemented with explicit zx/zy variables
        for escaped_at in range(inp.params.depth):
          zx2: gmpy2.mpfr = zx * zx
          zy2: gmpy2.mpfr = zy * zy
          # avoid sqrt(abs(z)); compare squared magnitude to 2^2
          if (mag_z2 := zx2 + zy2) > _MPFR_FOUR:
            # the smooth escape formula is asymptotic: computing it immediately at |z| > 2
            # leaves visible iteration-correlated contour error, so we iterate a few more times
            # after escape before evaluating the potential
            for _ in range(frame.SMOOTH_EXTRA_ITERS):
              escaped_at += 1  # noqa: PLW2901
              zy = _MPFR_TWO * zx * zy + cy
              zx = zx2 - zy2 + cx
              zx2 = zx * zx
              zy2 = zy * zy
            mag_z2 = zx2 + zy2
            # the smooth_escape part is a fractional value that represents how far the orbit went
            # beyond the escape radius at the escape iteration; we want to ensure that the final
            # escape value is "n + nu", where n is an integer and nu is in [0,1), and we store
            # them separately for better precision
            smooth_escape = 1.0 - float(
              gmpy2.log2(_MPFR_HALF * cast('gmpy2.mpfr', gmpy2.log(mag_z2)))
            )
            escaped_at, smooth_escape = NormalizeSmoothEscape(escaped_at, smooth_escape)  # noqa: PLW2901
            break
          # Imaginary Weight Average: accumulate sin(arg(z))**2 = zy**2/|z|**2 BEFORE the update
          if inp.params.set_points == frame.SetHighlightAlgorithm.IMAGINARY and mag_z2 > _MPFR_ZERO:
            imag_acc += zy2 / mag_z2
          # z = z^2 + c in terms of zx/zy: zx' = zx^2 - zy^2 + cx - the actual Mandelbrot iteration
          zy = _MPFR_TWO * zx * zy + cy
          zx = zx2 - zy2 + cx
          # accumulate |z|; don't do this first, or else, for example, min() will always be 0.0
          if inp.params.set_points == frame.SetHighlightAlgorithm.MIN:
            min_z2 = min(min_z2, mag_z2)
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MAX:
            max_z2 = max(max_z2, mag_z2)
        else:
          # if we didn't break, we reached max_iter, mark as non-escaped, so
          # we will declare this a "Interior Set Point"; the max_z2 should always be <= 4: check
          if not 0 <= max_z2 < _MPFR_FOUR:
            raise image.Error(
              f'Interior point exceeded max |z|^2 of 4, should never happen, {max_z2=}'
            )
          # always count interior points, even if we don't do any special coloring for them
          n_interior += 1
          # now, for every possible set px algorithms, we do the final computations
          if inp.params.set_points is None:
            # default coloring: just mark as interior with a special negative value
            escaped_at = -frame.SET_INTERIOR_INT_MAX  # negative to mark it as interior!
            smooth_escape = 0.0
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MIN:
            # track the min |z|^2; first the stats...
            min_lo = min(min_lo, min_z2)
            min_hi = max(min_hi, min_z2)
            # ...then the normalized value for coloring
            sqrt_min: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(min_z2))
            escaped_at, smooth_escape = (
              NormalizeSmoothSet(sqrt_min, sqrt_lo2, sqrt_delta2)  # sqrt_lo2/delta2 pre-computed
              if stats_min
              else NormalizeSmoothSet(sqrt_min, _MPFR_ZERO, frame.MPFR_MAX_SET_Z)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MAX:
            # track the max |z|^2; first the stats...
            max_lo = min(max_lo, max_z2)
            max_hi = max(max_hi, max_z2)
            # ...then the normalized value for coloring
            sqrt_max: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(max_z2))
            escaped_at, smooth_escape = (
              NormalizeSmoothSet(sqrt_max, sqrt_lo, sqrt_delta)  # sqrt_lo/delta pre-computed
              if stats_max
              else NormalizeSmoothSet(sqrt_max, _MPFR_ZERO, frame.MPFR_MAX_SET_Z)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.ANGLE:
            # angle stats for interior points; first the stats...
            ang: gmpy2.mpfr = gmpy2.atan2(zy, zx)  # angle in radians, between -pi and pi
            ang = (ang + mpfr_pi) / mpfr_two_pi  # shift to [0, 2pi] then to [0, 1]
            ang_lo = min(ang_lo, ang)
            ang_hi = max(ang_hi, ang)
            # ...then the normalized value for coloring
            escaped_at, smooth_escape = (
              # ang_lo & ang_delta are pre-computed
              NormalizeSmoothSet(ang, inp.stats.ang_lo, ang_delta)  # type: ignore[union-attr, arg-type]
              if stats_ang
              else NormalizeSmoothSet(ang, _MPFR_ZERO, _MPFR_ONE)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.IMAGINARY:
            # Imaginary Weight Average: mean(sin(arg(z))**2) over orbit; first the stats...
            imag_mean: gmpy2.mpfr = (imag_acc / max_iter_p_1) / frame.MPFR_MAX_SET_Z
            imag_lo = min(imag_lo, imag_mean)
            imag_hi = max(imag_hi, imag_mean)
            # ...then the normalized value for coloring
            escaped_at, smooth_escape = (
              # imag_lo & imag_delta are pre-computed
              NormalizeSmoothSet(imag_mean, inp.stats.imag_lo, imag_delta)  # type: ignore[union-attr, arg-type]
              if stats_imag
              else NormalizeSmoothSet(imag_mean, _MPFR_ZERO, _MPFR_ONE)
            )
          else:
            raise image.Error(f'Unknown fractal type {inp.params.set_points=}; should never happen')
        # either in or out of the set, we now should always have a value for escaped_at;
        # this is setting the pixel escape (not the coloring! that is done later in image.Image)
        img.escape[px_count] = EncodeIntFloatTo64(escaped_at, smooth_escape)  # carefully set
        p_bar.update(1)  # we touched a pixel, so update the progress bar
    # done; return the stats we collected with the task output
    p_bar.close()
    img.stats = image.FractalStats(
      n_px=inp.params.width * inp.params.height,
      n_interior=n_interior,
      # max & min: sentinel (4, 0) means no data collected
      max_lo=frame.CanonicalMPFR(max_lo) if max_hi >= max_lo else None,
      max_hi=frame.CanonicalMPFR(max_hi) if max_hi >= max_lo else None,
      min_lo=frame.CanonicalMPFR(min_lo) if min_hi >= min_lo else None,
      min_hi=frame.CanonicalMPFR(min_hi) if min_hi >= min_lo else None,
      # angle & imaginary: sentinel (1, 0) means no data collected
      ang_lo=frame.CanonicalMPFR(ang_lo) if ang_hi >= ang_lo else None,
      ang_hi=frame.CanonicalMPFR(ang_hi) if ang_hi >= ang_lo else None,
      imag_lo=frame.CanonicalMPFR(imag_lo) if imag_hi >= imag_lo else None,
      imag_hi=frame.CanonicalMPFR(imag_hi) if imag_hi >= imag_lo else None,
    )
    return image.FractalTaskOutput(img=img, n_task=inp.n_task, total_tasks=inp.total_tasks)


def JuliaComputation(inp: image.FractalTaskInput) -> image.FractalTaskOutput:  # noqa: C901, PLR0912, PLR0914, PLR0915
  """Compute the Julia image for the given task input. ONE THREAD FOR MULTIPROCESSING.

  Args:
    inp (image.FractalTaskInput): The task input containing all parameters for the computation.

  Returns:
    image.FractalTaskOutput: The rendered fractal image and task information.

  Raises:
    image.Error: on error

  """
  if inp.params.frm.fractal != frame.Fractal.JULIA:
    raise image.Error(f'Expected Julia computation, got {inp.params.frm.fractal}')
  is_preprocess: bool = (
    inp.params.width == frame.MIN_IMAGE_SIZE and inp.params.height == frame.MIN_IMAGE_SIZE
  )
  # create image; will also check the parameters and frame validity in the Image constructor
  img: image.Image = image.Image(inp.params)
  # compute pixel size in complex plane and check frame validity; exact computation (gmpy2.mpq)
  dx: gmpy2.mpq
  dy: gmpy2.mpq
  dx, dy = inp.params.frm.size
  dx, dy = dx / gmpy2.mpq(inp.params.width - 1), dy / gmpy2.mpq(inp.params.height - 1)
  if dx <= 0 or dy <= 0:
    raise image.Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
  # start the mpfr context for floating-point computations with the precision needed
  with inp.params.context:  # noqa: PLR1702
    # precompute x coordinates once: this matters because mpfr construction and arithmetic
    # are relatively expensive and we can reuse the x values across rows ("inner for loop");
    # also, this is where the "X" (real) coordinates are converted mpq->mpfr
    xs: list[gmpy2.mpfr] = [
      gmpy2.mpfr(inp.params.frm.top_re + gmpy2.mpq(i) * dx) for i in range(inp.params.width)
    ]
    # variables for stats we will track; we pre-compute all we can!
    mpfr_pi: gmpy2.mpfr = gmpy2.const_pi()  # pi with the current context precision
    mpfr_two_pi: gmpy2.mpfr = _MPFR_TWO * mpfr_pi  # 2*pi with the current context precision
    max_iter_p_1: gmpy2.mpfr = gmpy2.mpfr(inp.params.depth) + _MPFR_ONE
    n_interior: int = 0  # track how many points are interior (non-escaping)
    max_lo: gmpy2.mpfr = _MPFR_FOUR
    max_hi: gmpy2.mpfr = _MPFR_ZERO
    min_lo: gmpy2.mpfr = _MPFR_FOUR
    min_hi: gmpy2.mpfr = _MPFR_ZERO
    ang_lo: gmpy2.mpfr = _MPFR_ONE
    ang_hi: gmpy2.mpfr = _MPFR_ZERO
    imag_lo: gmpy2.mpfr = _MPFR_ONE
    imag_hi: gmpy2.mpfr = _MPFR_ZERO
    stats_max: bool = False
    sqrt_lo: gmpy2.mpfr = _MPFR_ZERO
    sqrt_delta: gmpy2.mpfr = _MPFR_ZERO
    stats_min: bool = False
    sqrt_lo2: gmpy2.mpfr = _MPFR_ZERO
    sqrt_delta2: gmpy2.mpfr = _MPFR_ZERO
    stats_ang: bool = False
    ang_delta: gmpy2.mpfr = _MPFR_ZERO
    stats_imag: bool = False
    imag_delta: gmpy2.mpfr = _MPFR_ZERO
    if inp.stats is not None:
      # stats_max/min/ang/imag are True only when pre-stats were collected (non-None) AND there is
      # a valid range to normalize against (hi > lo); used to decide normalization strategy below
      if stats_max := (
        inp.stats.max_lo is not None
        and inp.stats.max_hi is not None
        and inp.stats.max_hi > inp.stats.max_lo
      ):
        sqrt_lo = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.max_lo))  # pyright: ignore[reportArgumentType]
        sqrt_delta = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.max_hi) - sqrt_lo)  # pyright: ignore[reportArgumentType]
      if stats_min := (
        inp.stats.min_lo is not None
        and inp.stats.min_hi is not None
        and inp.stats.min_hi > inp.stats.min_lo
      ):
        sqrt_lo2 = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.min_lo))  # pyright: ignore[reportArgumentType]
        sqrt_delta2 = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.min_hi) - sqrt_lo2)  # pyright: ignore[reportArgumentType]
      if stats_ang := (
        inp.stats.ang_lo is not None
        and inp.stats.ang_hi is not None
        and inp.stats.ang_hi > inp.stats.ang_lo
      ):
        ang_delta = inp.stats.ang_hi - inp.stats.ang_lo  # pyright: ignore[reportOperatorIssue, reportUnknownVariableType]
      if stats_imag := (
        inp.stats.imag_lo is not None
        and inp.stats.imag_hi is not None
        and inp.stats.imag_hi > inp.stats.imag_lo
      ):
        imag_delta = inp.stats.imag_hi - inp.stats.imag_lo  # pyright: ignore[reportOperatorIssue, reportUnknownVariableType]
    # create progress bar based on total pixels and the options
    has_procs: bool = inp.total_tasks > 1
    n_task: int = inp.n_task - 1  # convert to 0-based index for easier modulo math
    with warnings.catch_warnings():
      warnings.simplefilter('ignore', category=TqdmExperimentalWarning)
      p_bar: tqdm.rich.tqdm[NoReturn] = tqdm.rich.tqdm(
        total=inp.params.width * inp.params.height,
        desc='Pre' if is_preprocess else 'Img',
        unit='px',
        dynamic_ncols=True,
        smoothing=0.1,
        colour='green',
        disable=not inp.progress_bar or (has_procs and n_task != 0),  # show for the 1st process
      )
    # Julia c-parameter: fixed throughout the entire computation (the 'c' in z_{n+1} = z_n^2 + c)
    cx: gmpy2.mpfr = gmpy2.mpfr(inp.params.frm.point_re)
    cy: gmpy2.mpfr = gmpy2.mpfr(inp.params.frm.point_im)
    # iterate over pixels in row-major order, computing escape iterations in mpfr
    px_count: int = -1
    for py in range(inp.params.height):
      # PILImage.frombytes interprets the first row written as the top row of the image, so
      # we iterate y inverted by starting at the top and going down;
      # this is the "outer for loop", no benefit in pre-computing y values;
      # also, this is where the "Y" (imaginary) coordinates are converted mpq->mpfr
      img_y: gmpy2.mpfr = gmpy2.mpfr(inp.params.frm.top_im - gmpy2.mpq(py) * dy)
      img_y2: gmpy2.mpfr = img_y * img_y  # precompute |img_y|*|img_y| once per row; reused per col
      # iterate over columns, reusing x values and doing the escape test in mpfr for correctness
      for px in range(inp.params.width):
        px_count += 1
        if has_procs and (px_count % inp.total_tasks) != n_task:
          # this pixel is not for this process, skip it but still update the progress bar
          p_bar.update(1)
          continue
        # either this is a solo process, or this pixel is for this process
        # starting point is inside escape radius; do the full escape-time iteration in mpfr
        zy: gmpy2.mpfr = img_y
        zx: gmpy2.mpfr = xs[px]
        min_z2: gmpy2.mpfr = _MPFR_FOUR  # track min |z|^2 for potential use in coloring
        max_z2: gmpy2.mpfr = _MPFR_ZERO  # track max |z|^2 for potential use in coloring
        mag_z2: gmpy2.mpfr
        imag_acc: gmpy2.mpfr = _MPFR_ZERO  # accumulate sin(arg(z)) over orbit for smooth SAC
        # fast exterior pre-check: if |z_0|*|z_0| > 4 the starting point is already outside the
        # escape radius so the orbit escapes immediately, before any iteration; note that this is
        # the ONLY simple universal fast test available for Julia sets — unlike Mandelbrot (which
        # has closed-form algebraic interior tests for its main cardioid and period-2 bulb), Julia
        # sets have NO universal fast interior test: the filled Julia set's shape depends entirely
        # on c and has no simple global algebraic boundary description
        if zx * zx + img_y2 > _MPFR_FOUR:
          img.escape[px_count] = EncodeIntFloatTo64(0, 0.0)  # orbit escapes at the start
          p_bar.update(1)
          continue
        # did not escape at fast check, do the whole thing
        escaped_at: int = 0
        smooth_escape: float = 0.0
        # escape-time loop, implemented with explicit zx/zy variables
        for escaped_at in range(inp.params.depth):
          zx2: gmpy2.mpfr = zx * zx
          zy2: gmpy2.mpfr = zy * zy
          # avoid sqrt(abs(z)); compare squared magnitude to 2^2
          if (mag_z2 := zx2 + zy2) > _MPFR_FOUR:
            # the smooth escape formula is asymptotic: computing it immediately at |z| > 2
            # leaves visible iteration-correlated contour error, so we iterate a few more times
            # after escape before evaluating the potential
            for _ in range(frame.SMOOTH_EXTRA_ITERS):
              escaped_at += 1  # noqa: PLW2901
              zy = _MPFR_TWO * zx * zy + cy
              zx = zx2 - zy2 + cx
              zx2 = zx * zx
              zy2 = zy * zy
            mag_z2 = zx2 + zy2
            # the smooth_escape part is a fractional value that represents how far the orbit went
            # beyond the escape radius at the escape iteration; we want to ensure that the final
            # escape value is "n + nu", where n is an integer and nu is in [0,1), and we store
            # them separately for better precision
            smooth_escape = 1.0 - float(
              gmpy2.log2(_MPFR_HALF * cast('gmpy2.mpfr', gmpy2.log(mag_z2)))
            )
            escaped_at, smooth_escape = NormalizeSmoothEscape(escaped_at, smooth_escape)  # noqa: PLW2901
            break
          # Imaginary Weight Average: accumulate sin(arg(z))**2 = zy**2/|z|**2 BEFORE the update
          if inp.params.set_points == frame.SetHighlightAlgorithm.IMAGINARY and mag_z2 > _MPFR_ZERO:
            imag_acc += zy2 / mag_z2
          # z = z^2 + c in terms of zx/zy: zx' = zx^2 - zy^2 + cx - the actual Julia iteration
          zy = _MPFR_TWO * zx * zy + cy
          zx = zx2 - zy2 + cx
          # accumulate |z|; don't do this first, or else, for example, min() will always be 0.0
          if inp.params.set_points == frame.SetHighlightAlgorithm.MIN:
            min_z2 = min(min_z2, mag_z2)
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MAX:
            max_z2 = max(max_z2, mag_z2)
        else:
          # if we didn't break, we reached max_iter, mark as non-escaped, so
          # we will declare this a Set point, interior; the max_z2 should be <= 4: check
          if not 0 <= max_z2 < _MPFR_FOUR:
            raise image.Error(
              f'Interior point exceeded max |z|^2 of 4, should never happen, {max_z2=}'
            )
          # always count interior points, even if we don't do any special coloring for them
          n_interior += 1
          # now, for every possible set px algorithms, we do the final computations
          if inp.params.set_points is None:
            # default coloring: just mark as interior with a special negative value
            escaped_at = -frame.SET_INTERIOR_INT_MAX  # negative to mark it as interior!
            smooth_escape = 0.0
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MIN:
            # track the min |z|^2; first the stats...
            min_lo = min(min_lo, min_z2)
            min_hi = max(min_hi, min_z2)
            # ...then the normalized value for coloring
            sqrt_min: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(min_z2))
            escaped_at, smooth_escape = (
              NormalizeSmoothSet(sqrt_min, sqrt_lo2, sqrt_delta2)  # sqrt_lo2/delta2 pre-computed
              if stats_min
              else NormalizeSmoothSet(sqrt_min, _MPFR_ZERO, frame.MPFR_MAX_SET_Z)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MAX:
            # track the max |z|^2; first the stats...
            max_lo = min(max_lo, max_z2)
            max_hi = max(max_hi, max_z2)
            # ...then the normalized value for coloring
            sqrt_max: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(max_z2))
            escaped_at, smooth_escape = (
              NormalizeSmoothSet(sqrt_max, sqrt_lo, sqrt_delta)  # sqrt_lo/delta pre-computed
              if stats_max
              else NormalizeSmoothSet(sqrt_max, _MPFR_ZERO, frame.MPFR_MAX_SET_Z)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.ANGLE:
            # angle stats for interior points; first the stats...
            ang: gmpy2.mpfr = gmpy2.atan2(zy, zx)  # angle in radians, between -pi and pi
            ang = (ang + mpfr_pi) / mpfr_two_pi  # shift to [0, 2pi] then to [0, 1]
            ang_lo = min(ang_lo, ang)
            ang_hi = max(ang_hi, ang)
            # ...then the normalized value for coloring
            escaped_at, smooth_escape = (
              # ang_lo & ang_delta are pre-computed
              NormalizeSmoothSet(ang, inp.stats.ang_lo, ang_delta)  # type: ignore[union-attr, arg-type]
              if stats_ang
              else NormalizeSmoothSet(ang, _MPFR_ZERO, _MPFR_ONE)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.IMAGINARY:
            # Imaginary Weight Average: mean(sin(arg(z))**2) over orbit; first the stats...
            imag_mean: gmpy2.mpfr = (imag_acc / max_iter_p_1) / frame.MPFR_MAX_SET_Z
            imag_lo = min(imag_lo, imag_mean)
            imag_hi = max(imag_hi, imag_mean)
            # ...then the normalized value for coloring
            escaped_at, smooth_escape = (
              # imag_lo & imag_delta are pre-computed
              NormalizeSmoothSet(imag_mean, inp.stats.imag_lo, imag_delta)  # type: ignore[union-attr, arg-type]
              if stats_imag
              else NormalizeSmoothSet(imag_mean, _MPFR_ZERO, _MPFR_ONE)
            )
          else:
            raise image.Error(f'Unknown fractal type {inp.params.set_points=}; should never happen')
        # either in or out of the set, we now should always have a value for escaped_at;
        # this is setting the pixel escape (not the coloring! that is done later in image.Image)
        img.escape[px_count] = EncodeIntFloatTo64(escaped_at, smooth_escape)  # carefully set
        p_bar.update(1)  # we touched a pixel, so update the progress bar
    # done; return the stats we collected with the task output
    p_bar.close()
    img.stats = image.FractalStats(
      n_px=inp.params.width * inp.params.height,
      n_interior=n_interior,
      # max & min: sentinel (4, 0) means no data collected
      max_lo=frame.CanonicalMPFR(max_lo) if max_hi >= max_lo else None,
      max_hi=frame.CanonicalMPFR(max_hi) if max_hi >= max_lo else None,
      min_lo=frame.CanonicalMPFR(min_lo) if min_hi >= min_lo else None,
      min_hi=frame.CanonicalMPFR(min_hi) if min_hi >= min_lo else None,
      # angle & imaginary: sentinel (1, 0) means no data collected
      ang_lo=frame.CanonicalMPFR(ang_lo) if ang_hi >= ang_lo else None,
      ang_hi=frame.CanonicalMPFR(ang_hi) if ang_hi >= ang_lo else None,
      imag_lo=frame.CanonicalMPFR(imag_lo) if imag_hi >= imag_lo else None,
      imag_hi=frame.CanonicalMPFR(imag_hi) if imag_hi >= imag_lo else None,
    )
    return image.FractalTaskOutput(img=img, n_task=inp.n_task, total_tasks=inp.total_tasks)
