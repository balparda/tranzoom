# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing.

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>
"""

from __future__ import annotations

import dataclasses
import logging
import os
from collections import abc
from concurrent import futures
from typing import NoReturn, cast

import gmpy2
import tqdm

from tranzoom.core import frame, image

# automated search for iter

_ITER_SAFETY_FACTOR: float = 1.5  # we multiply the estimated iter by this to be safe

# multiprocessing

AVAILABLE_CPU: int = int(getattr(os, 'process_cpu_count', os.cpu_count)() or 1)
_MAX_PRE_PROCESS_CONCURRENCE: int = 4  # for the preprocess step, we limit the concurrency
MAX_CONCURRENCE: int = 16  # for the main rendering step, we limit the concurrency

# gmpy2.mpfr constants
_MPFR_ZERO: gmpy2.mpfr = gmpy2.mpfr('0')
_MPFR_SIXTEENTH: gmpy2.mpfr = gmpy2.mpfr('0.0625')
_MPFR_FOURTH: gmpy2.mpfr = gmpy2.mpfr('0.25')
_MPFR_ONE: gmpy2.mpfr = gmpy2.mpfr('1')
_MPFR_TWO: gmpy2.mpfr = gmpy2.mpfr('2')
_MPFR_FOUR: gmpy2.mpfr = gmpy2.mpfr('4')


class Error(image.Error):
  """Base fractal exception."""


def ComputeFractal(
  params: frame.ComputationParameters,
  *,
  progress_bar: bool = True,
  n_processes: int | None = None,
  print_comm: abc.Callable[[str], None] = print,
) -> tuple[frame.ComputationParameters, image.Image]:
  """Render the Mandelbrot frame rectangle to an Image.

  Args:
    params (frame.ComputationParameters): The computation parameters for the image.
    progress_bar (bool, optional): Whether to show a progress bar. Defaults to True.
    n_processes (int | None, optional): The number of processes to use for rendering. Defaults
        to None, which means to use all available CPU cores. Will be limited to MAX_CONCURRENCE.
    print_comm (Callable[[str], None], optional): A callable to print messages. Defaults to print.

  Returns:
    tuple[frame.ComputationParameters, image.Image]: A tuple containing the updated
        computation parameters and the rendered fractal image.

  Raises:
    Error: on error

  """
  # determine processes
  if n_processes is not None and n_processes < 1:
    raise Error(f'{n_processes=} must be a positive integer or None')
  is_preprocess: bool = (
    params.width == frame.MIN_IMAGE_SIZE and params.height == frame.MIN_IMAGE_SIZE
  )
  n_processes = n_processes or AVAILABLE_CPU
  n_processes = min(n_processes, _MAX_PRE_PROCESS_CONCURRENCE) if is_preprocess else n_processes
  n_processes = min(n_processes, MAX_CONCURRENCE, AVAILABLE_CPU)  # never exceed CPU!
  # if max_iter is MIN_ITER, we do an adaptive iteration limit calculation based on a small image;
  # BEWARE: the method call will call ComputeFractal() recursively, so skip MIN_IMAGE_SIZE
  stats: image.FractalStats | None = None
  if params.depth == frame.MIN_ITER and max(params.size) > frame.MIN_IMAGE_SIZE:
    # MIN_ITER is a special mark that means "automatically calculate the depth" based on the frame,
    # but we only do this if the image is larger than the minimum size (we use those for probing)
    max_iter: int
    max_iter, stats = _FractalAdaptiveIterations(
      params.frm, params.set_points, progress_bar, n_processes, print_comm
    )
    params = dataclasses.replace(params, depth=max_iter)  # update params with the new max_iter
  logging.debug(
    f'{params.frm.fractal.value.upper()} using {n_processes} process(es) '
    f'for {"PRE " if is_preprocess else ""}rendering'
  )
  # create inputs
  inp: list[_FractalTaskInput] = [
    _FractalTaskInput(
      params=params,
      progress_bar=progress_bar,
      n_task=i + 1,
      total_tasks=n_processes,
      stats=stats,
    )
    for i in range(n_processes)
  ]
  # execute in processes
  results: list[_FractalTaskOutput]
  computation: _FractalComputation = (
    _MandelbrotComputation if params.frm.fractal == frame.Fractal.MANDELBROT else _JuliaComputation
  )
  if n_processes == 1:
    # no multiprocessing, just run the single task directly in this process (also good for debug)
    results = [computation(inp[0])]
  else:
    # multiprocessing: run the tasks in separate processes and collect results
    with futures.ProcessPoolExecutor(max_workers=n_processes) as executor:
      results = list(executor.map(computation, inp))
  # at this point all tasks are finished: check we have them all!
  if len(results) != n_processes:
    raise Error(f'Expected {n_processes} results from computations, got {len(results)}')
  img: image.Image = results[0].img  # start with the first image to save time and space
  if n_processes > 1:
    # combine results into a single image; possible b/c each task wrote to a disjoint set of pixels
    for result in results[1:]:
      # copy only this task's interleaved pixels into the final image
      n_task: int = result.n_task - 1  # convert to 0-based index for stepped slice indexing
      img.escape[n_task::n_processes] = result.img.escape[n_task::n_processes]
    # combine stats from all tasks: n_interior is additive, _lo fields take min, _hi take max
    all_stats: list[image.FractalStats] = [r.img.stats for r in results if r.img.stats is not None]
    if all_stats:
      img.stats = image.FractalStats(
        n_px=all_stats[0].n_px,  # same in all tasks (= width * height)
        n_interior=sum(s.n_interior for s in all_stats),
        max_lo=min(s.max_lo for s in all_stats),
        max_hi=max(s.max_hi for s in all_stats),
        min_lo=min(s.min_lo for s in all_stats),
        min_hi=max(s.min_hi for s in all_stats),
        ang_lo=min(s.ang_lo for s in all_stats),
        ang_hi=max(s.ang_hi for s in all_stats),
        imag_lo=min(s.imag_lo for s in all_stats),
        imag_hi=max(s.imag_hi for s in all_stats),
      )
  # if the final image doesn't have stats, we can add them from the pre-process stats we collected
  if img.stats is None and stats is not None:
    img.stats = stats
  # all copied, so we can return the final image
  return (params, img)


def _FractalAdaptiveIterations(
  frm: frame.Frame,
  set_points: frame.SetHighlightAlgorithm | None,
  progress_bar: bool,
  n_processes: int,
  print_comm: abc.Callable[[str], None],
) -> tuple[int, image.FractalStats]:
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
    set_points (SetHighlightAlgorithm | None): Which algorithm to use for coloring the
        interior Set points, either None, or one of the SetHighlightAlgorithm values
    progress_bar (bool): Whether to show a progress bar during the test render.
    n_processes (int): The number of processes to use for the test render.
    print_comm (Callable[[str], None]): A callable to print messages

  Returns:
    int: The estimated max_iter for the full image, based on the escape histogram of the test render

  Raises:
    Error: if the estimated max_iter exceeds the adaptive limit

  """
  max_iter: int = frame.MAX_ITER
  for high_iter in frame.HIGH_ITERS:
    # make the smallest image
    img16: image.Image = ComputeFractal(
      frame.ComputationParameters(
        frm=frm,  # same frame
        width=frame.MIN_IMAGE_SIZE,  # smallest image size
        height=frame.MIN_IMAGE_SIZE,
        depth=high_iter,  # putative depth
        set_points=set_points,
      ),
      progress_bar=progress_bar,
      n_processes=n_processes,
      print_comm=print_comm,
    )[1]  # we only need the image, not the updated params, from this test render
    # estimate the needed iterations for the full image based on the smallest image;
    # make the histogram of escape iterations for the smallest image, and find the highest escape
    escape_histogram: dict[int, int] = {}
    for enc_escaped_at in img16.escape:
      escaped_at: int = image.Decode64ToIntFloat(enc_escaped_at)[0]
      esc: int = escaped_at if escaped_at >= 0 else high_iter  # interior point == high_iter
      escape_histogram[esc] = escape_histogram.get(esc, 0) + 1
    # check stats
    if img16.stats is None:
      raise Error('Fractal stats should have been collected during rendering, but are missing')
    # sort the histogram by escape iteration; find the highest escape iteration that < high limit
    # if all pixels hit high_iter then max_iter will be high_iter, and we WANT it to FAIL
    histogram: list[tuple[int, int]] = sorted(escape_histogram.items())
    max_iter = (
      histogram[-1][0] if histogram[-1][0] != high_iter or len(histogram) == 1 else histogram[-2][0]
    )
    # apply safety factor and clamp
    max_iter = min(frame.MAX_ITER, max(frame.MIN_ITER, int(max_iter * _ITER_SAFETY_FACTOR)))
    if max_iter < high_iter:
      # we found a winner! print and stop
      print_comm(
        f'Picked depth {max_iter}, histogram {image.SummaryHistogram(histogram)}, '
        f'{img16.stats.n_interior}/{img16.stats.n_px} set points'
      )
      return (max_iter, img16.stats)
    print_comm(f'[red]Iteration limit of {high_iter} was too low:[/] will try again 10x deeper...')
    # here we didn't find, so we loop to the next higher limit...
  # if we exhausted all the high_iters without finding a suitable max_iter, we have to give up
  raise Error(
    f'Estimated {max_iter=} is above the adaptive limit of {frame.HIGH_ITERS[-1]}; '
    'maybe this frame is interior-only (all pixels are non-escaping)'
  )


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class _FractalTaskInput:
  """Defines a Mandelbrot task."""

  params: frame.ComputationParameters
  progress_bar: bool
  n_task: int
  total_tasks: int
  stats: image.FractalStats | None = None

  def __post_init__(self) -> None:
    """Validate parameters.

    Raises:
      Error: on error

    """
    # check task numbers
    if not (1 <= self.n_task <= self.total_tasks):
      raise Error(f'{self.n_task=} must be between 1 and {self.total_tasks}')


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class _FractalTaskOutput:
  """Defines a Mandelbrot task output."""

  img: image.Image
  n_task: int
  total_tasks: int


type _FractalComputation = abc.Callable[[_FractalTaskInput], _FractalTaskOutput]


def _MandelbrotComputation(inp: _FractalTaskInput) -> _FractalTaskOutput:  # noqa: C901, PLR0912, PLR0914, PLR0915
  """Compute the Mandelbrot image for the given task input. ONE THREAD FOR MULTIPROCESSING.

  Args:
    inp (_FractalTaskInput): The task input containing all parameters for the computation.

  Returns:
    _FractalTaskOutput: The rendered fractal image and task information.

  Raises:
    Error: on error

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
    raise Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
  # start the mpfr context for floating-point computations with the precision needed
  with inp.params.context:
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
      stats_max = inp.stats.max_hi > inp.stats.max_lo
      sqrt_lo = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.max_lo))
      sqrt_delta = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.max_hi) - sqrt_lo)
      stats_min = inp.stats.min_hi > inp.stats.min_lo
      sqrt_lo2 = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.min_lo))
      sqrt_delta2 = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.min_hi) - sqrt_lo2)
      stats_ang = inp.stats.ang_hi > inp.stats.ang_lo
      ang_delta = inp.stats.ang_hi - inp.stats.ang_lo
      stats_imag = inp.stats.imag_hi > inp.stats.imag_lo
      imag_delta = inp.stats.imag_hi - inp.stats.imag_lo
    normalize: abc.Callable[[gmpy2.mpfr, gmpy2.mpfr, gmpy2.mpfr], int] = lambda v, lo, d: (
      -min(  # negative to mark it as interior!
        frame.SET_INTERIOR_RESOLUTION,  # clamp to the max
        max(
          1,  # clamped to at least 1, we can't have 0
          int(  # converted to int
            gmpy2.floor(  # scaled to [0,1], then to [0, SET_INTERIOR_RESOLUTION]
              max(_MPFR_ZERO, min(_MPFR_ONE, (v - lo) / d)) * frame.MPFR_SET_INTERIOR_RESOLUTION
            )
          )
          + 1,  # we want to start at 1, so add 1, -> [1, SET_INTERIOR_RESOLUTION + 1]
        ),
      )
    )
    # create progress bar based on total pixels and the options
    has_procs: bool = inp.total_tasks > 1
    n_task: int = inp.n_task - 1  # convert to 0-based index for easier modulo math
    p_bar: tqdm.tqdm[NoReturn] = tqdm.tqdm(
      total=inp.params.width * inp.params.height,
      desc='Pre' if is_preprocess else 'Img',
      unit='px',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='green',
      disable=not inp.progress_bar or (has_procs and n_task != 0),  # show for the 1st process only
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
            img.escape[px_count] = image.EncodeIntFloatTo64(-frame.SET_INTERIOR_RESOLUTION, 0.0)
            p_bar.update(1)  # we touched a pixel, so update the progress bar
            continue
          # period-2 bulb test
          x_plus_one: gmpy2.mpfr = cx + _MPFR_ONE
          if x_plus_one * x_plus_one + cy * cy <= _MPFR_SIXTEENTH:
            # point is in the period-2 bulb, so it's an interior point, no escape
            # mark negative so as to mark it as interior
            n_interior += 1
            img.escape[px_count] = image.EncodeIntFloatTo64(-frame.SET_INTERIOR_RESOLUTION, 0.0)
            p_bar.update(1)  # we touched a pixel, so update the progress bar
            continue
        # not in the main cardioid or period-2 bulb, do the full escape-time test in mpfr
        zx: gmpy2.mpfr = _MPFR_ZERO  # zx/zy -> the z in the iteration z = z^2 + c
        zy: gmpy2.mpfr = _MPFR_ZERO
        min_z2: gmpy2.mpfr = _MPFR_FOUR  # track min |z|^2 for potential use in coloring
        max_z2: gmpy2.mpfr = _MPFR_ZERO  # track max |z|^2 for potential use in coloring
        mag_z2: gmpy2.mpfr
        escaped_at: int = 0
        imag_acc: gmpy2.mpfr = _MPFR_ZERO  # accumulate sin(arg(z)) over orbit for smooth SAC
        # escape-time loop, implemented with explicit zx/zy variables
        for escaped_at in range(inp.params.depth):  # noqa: B007
          zx2: gmpy2.mpfr = zx * zx
          zy2: gmpy2.mpfr = zy * zy
          # avoid sqrt(abs(z)); compare squared magnitude to 2^2
          if (mag_z2 := zx2 + zy2) > _MPFR_FOUR:
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
            raise Error(f'Interior point exceeded max |z|^2 of 4, should never happen, {max_z2=}')
          # always count interior points, even if we don't do any special coloring for them
          n_interior += 1
          # now, for every possible set px algorithms, we do the final computations
          if inp.params.set_points is None:
            # default coloring: just mark as interior with a special negative value
            escaped_at = -frame.SET_INTERIOR_RESOLUTION  # negative to mark it as interior!
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MIN:
            # track the min |z|^2; first the stats...
            min_lo = min(min_lo, min_z2)
            min_hi = max(min_hi, min_z2)
            # ...then the normalized value for coloring
            sqrt_min: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(min_z2))
            escaped_at = (
              normalize(sqrt_min, sqrt_lo2, sqrt_delta2)  # sqrt_lo2 & sqrt_delta2 are pre-computed
              if stats_min
              else normalize(sqrt_min, _MPFR_ZERO, frame.MPFR_MAX_SET_Z)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MAX:
            # track the max |z|^2; first the stats...
            max_lo = min(max_lo, max_z2)
            max_hi = max(max_hi, max_z2)
            # ...then the normalized value for coloring
            sqrt_max: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(max_z2))
            escaped_at = (
              normalize(sqrt_max, sqrt_lo, sqrt_delta)  # sqrt_lo & sqrt_delta are pre-computed
              if stats_max
              else normalize(sqrt_max, _MPFR_ZERO, frame.MPFR_MAX_SET_Z)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.ANGLE:
            # angle stats for interior points; first the stats...
            ang: gmpy2.mpfr = gmpy2.atan2(zy, zx)  # angle in radians, between -pi and pi
            ang = (ang + mpfr_pi) / mpfr_two_pi  # shift to [0, 2pi] then to [0, 1]
            ang_lo = min(ang_lo, ang)
            ang_hi = max(ang_hi, ang)
            # ...then the normalized value for coloring
            escaped_at = (
              # ang_lo & ang_delta are pre-computed
              normalize(ang, inp.stats.ang_lo, ang_delta)  # type: ignore[union-attr]
              if stats_ang
              else normalize(ang, _MPFR_ZERO, _MPFR_ONE)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.IMAGINARY:
            # Imaginary Weight Average: mean(sin(arg(z))**2) over orbit; first the stats...
            imag_mean: gmpy2.mpfr = (imag_acc / max_iter_p_1) / frame.MPFR_MAX_SET_Z
            imag_lo = min(imag_lo, imag_mean)
            imag_hi = max(imag_hi, imag_mean)
            # ...then the normalized value for coloring
            escaped_at = (
              # imag_lo & imag_delta are pre-computed
              normalize(imag_mean, inp.stats.imag_lo, imag_delta)  # type: ignore[union-attr]
              if stats_imag
              else normalize(imag_mean, _MPFR_ZERO, _MPFR_ONE)
            )
          else:
            raise Error(f'Unknown fractal type {inp.params.set_points=}; should never happen')
        # either in or out of the set, we now should always have a value for escaped_at;
        # this is setting the pixel escape (not the coloring! that is done later in image.Image)
        img.escape[px_count] = image.EncodeIntFloatTo64(escaped_at, 0.0)  # carefully set
        p_bar.update(1)  # we touched a pixel, so update the progress bar
    # done; return the stats we collected with the task output
    p_bar.close()
    img.stats = image.FractalStats(
      n_px=inp.params.width * inp.params.height,
      n_interior=n_interior,
      max_lo=max_lo,
      max_hi=max_hi,
      min_lo=min_lo,
      min_hi=min_hi,
      ang_lo=ang_lo,
      ang_hi=ang_hi,
      imag_lo=imag_lo,
      imag_hi=imag_hi,
    )
    return _FractalTaskOutput(img=img, n_task=inp.n_task, total_tasks=inp.total_tasks)


def _JuliaComputation(inp: _FractalTaskInput) -> _FractalTaskOutput:  # noqa: C901, PLR0912, PLR0914, PLR0915
  """Compute the Julia image for the given task input. ONE THREAD FOR MULTIPROCESSING.

  Args:
    inp (_FractalTaskInput): The task input containing all parameters for the computation.

  Returns:
    _FractalTaskOutput: The rendered fractal image and task information.

  Raises:
    Error: on error

  """
  if inp.params.frm.fractal != frame.Fractal.JULIA:
    raise Error(f'Expected Julia computation, got {inp.params.frm.fractal}')
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
    raise Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
  # start the mpfr context for floating-point computations with the precision needed
  with inp.params.context:
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
      stats_max = inp.stats.max_hi > inp.stats.max_lo
      sqrt_lo = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.max_lo))
      sqrt_delta = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.max_hi) - sqrt_lo)
      stats_min = inp.stats.min_hi > inp.stats.min_lo
      sqrt_lo2 = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.min_lo))
      sqrt_delta2 = cast('gmpy2.mpfr', gmpy2.sqrt(inp.stats.min_hi) - sqrt_lo2)
      stats_ang = inp.stats.ang_hi > inp.stats.ang_lo
      ang_delta = inp.stats.ang_hi - inp.stats.ang_lo
      stats_imag = inp.stats.imag_hi > inp.stats.imag_lo
      imag_delta = inp.stats.imag_hi - inp.stats.imag_lo
    normalize: abc.Callable[[gmpy2.mpfr, gmpy2.mpfr, gmpy2.mpfr], int] = lambda v, lo, d: (
      -min(  # negative to mark it as interior!
        frame.SET_INTERIOR_RESOLUTION,  # clamp to the max
        max(
          1,  # clamped to at least 1, we can't have 0
          int(  # converted to int
            gmpy2.floor(  # scaled to [0,1], then to [0, SET_INTERIOR_RESOLUTION]
              max(_MPFR_ZERO, min(_MPFR_ONE, (v - lo) / d)) * frame.MPFR_SET_INTERIOR_RESOLUTION
            )
          )
          + 1,  # we want to start at 1, so add 1, -> [1, SET_INTERIOR_RESOLUTION + 1]
        ),
      )
    )
    # create progress bar based on total pixels and the options
    has_procs: bool = inp.total_tasks > 1
    n_task: int = inp.n_task - 1  # convert to 0-based index for easier modulo math
    p_bar: tqdm.tqdm[NoReturn] = tqdm.tqdm(
      total=inp.params.width * inp.params.height,
      desc='Pre' if is_preprocess else 'Img',
      unit='px',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='green',
      disable=not inp.progress_bar or (has_procs and n_task != 0),  # show for the 1st process only
    )
    # iterate over pixels in row-major order, computing escape iterations in mpfr
    cx: gmpy2.mpfr = gmpy2.mpfr(inp.params.frm.point_re)
    cy: gmpy2.mpfr = gmpy2.mpfr(inp.params.frm.point_im)
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
          img.escape[px_count] = image.EncodeIntFloatTo64(0, 0.0)  # orbit escapes at the start
          p_bar.update(1)
          continue
        # did not escape at fast check, do the whole thing
        escaped_at: int = 0
        # escape-time loop, implemented with explicit zx/zy variables
        for escaped_at in range(inp.params.depth):  # noqa: B007
          zx2: gmpy2.mpfr = zx * zx
          zy2: gmpy2.mpfr = zy * zy
          # avoid sqrt(abs(z)); compare squared magnitude to 2^2
          if (mag_z2 := zx2 + zy2) > _MPFR_FOUR:
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
            raise Error(f'Interior point exceeded max |z|^2 of 4, should never happen, {max_z2=}')
          # always count interior points, even if we don't do any special coloring for them
          n_interior += 1
          # now, for every possible set px algorithms, we do the final computations
          if inp.params.set_points is None:
            # default coloring: just mark as interior with a special negative value
            escaped_at = -frame.SET_INTERIOR_RESOLUTION  # negative to mark it as interior!
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MIN:
            # track the min |z|^2; first the stats...
            min_lo = min(min_lo, min_z2)
            min_hi = max(min_hi, min_z2)
            # ...then the normalized value for coloring
            sqrt_min: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(min_z2))
            escaped_at = (
              normalize(sqrt_min, sqrt_lo2, sqrt_delta2)  # sqrt_lo2 & sqrt_delta2 are pre-computed
              if stats_min
              else normalize(sqrt_min, _MPFR_ZERO, frame.MPFR_MAX_SET_Z)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MAX:
            # track the max |z|^2; first the stats...
            max_lo = min(max_lo, max_z2)
            max_hi = max(max_hi, max_z2)
            # ...then the normalized value for coloring
            sqrt_max: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(max_z2))
            escaped_at = (
              normalize(sqrt_max, sqrt_lo, sqrt_delta)  # sqrt_lo & sqrt_delta are pre-computed
              if stats_max
              else normalize(sqrt_max, _MPFR_ZERO, frame.MPFR_MAX_SET_Z)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.ANGLE:
            # angle stats for interior points; first the stats...
            ang: gmpy2.mpfr = gmpy2.atan2(zy, zx)  # angle in radians, between -pi and pi
            ang = (ang + mpfr_pi) / mpfr_two_pi  # shift to [0, 2pi] then to [0, 1]
            ang_lo = min(ang_lo, ang)
            ang_hi = max(ang_hi, ang)
            # ...then the normalized value for coloring
            escaped_at = (
              # ang_lo & ang_delta are pre-computed
              normalize(ang, inp.stats.ang_lo, ang_delta)  # type: ignore[union-attr]
              if stats_ang
              else normalize(ang, _MPFR_ZERO, _MPFR_ONE)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.IMAGINARY:
            # Imaginary Weight Average: mean(sin(arg(z))**2) over orbit; first the stats...
            imag_mean: gmpy2.mpfr = (imag_acc / max_iter_p_1) / frame.MPFR_MAX_SET_Z
            imag_lo = min(imag_lo, imag_mean)
            imag_hi = max(imag_hi, imag_mean)
            # ...then the normalized value for coloring
            escaped_at = (
              # imag_lo & imag_delta are pre-computed
              normalize(imag_mean, inp.stats.imag_lo, imag_delta)  # type: ignore[union-attr]
              if stats_imag
              else normalize(imag_mean, _MPFR_ZERO, _MPFR_ONE)
            )
          else:
            raise Error(f'Unknown fractal type {inp.params.set_points=}; should never happen')
        # either in or out of the set, we now should always have a value for escaped_at;
        # this is setting the pixel escape (not the coloring! that is done later in image.Image)
        img.escape[px_count] = image.EncodeIntFloatTo64(escaped_at, 0.0)  # carefully set
        p_bar.update(1)  # we touched a pixel, so update the progress bar
    # done; return the stats we collected with the task output
    p_bar.close()
    img.stats = image.FractalStats(
      n_px=inp.params.width * inp.params.height,
      n_interior=n_interior,
      max_lo=max_lo,
      max_hi=max_hi,
      min_lo=min_lo,
      min_hi=min_hi,
      ang_lo=ang_lo,
      ang_hi=ang_hi,
      imag_lo=imag_lo,
      imag_hi=imag_hi,
    )
    return _FractalTaskOutput(img=img, n_task=inp.n_task, total_tasks=inp.total_tasks)
