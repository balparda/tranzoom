# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing.

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>
"""

from __future__ import annotations

import dataclasses
import logging
import math
from collections import abc
from concurrent import futures
from typing import NoReturn, cast

import gmpy2
import tqdm.rich

from tranzoom.core import frame, image

# automated search for iter

_ITER_OUTLIER_SKIP: int = 3  # skip up to this many extreme-outlier pixels in the probe
_ITER_SAFETY_FACTOR: float = 1.5  # we multiply the estimated iter by this to be safe

# gmpy2.mpfr constants
_MPFR_ZERO: gmpy2.mpfr = gmpy2.mpfr('0')
_MPFR_SIXTEENTH: gmpy2.mpfr = gmpy2.mpfr('0.0625')
_MPFR_FOURTH: gmpy2.mpfr = gmpy2.mpfr('0.25')
_MPFR_HALF: gmpy2.mpfr = gmpy2.mpfr('0.5')
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
  stats: image.FractalStats | None = None,
  print_comm: abc.Callable[[str], None] = print,
) -> tuple[frame.ComputationParameters, image.Image]:
  """Render the Mandelbrot frame rectangle to an Image.

  Args:
    params (frame.ComputationParameters): The computation parameters for the image.
    progress_bar (bool, optional): Whether to show a progress bar. Defaults to True.
    n_processes (int | None, optional): The number of processes to use for rendering. Defaults
        to None, which means to use all available CPU cores. Will be limited to MAX_CONCURRENCE.
    stats (image.FractalStats | None, optional): Optional pre-collected stats from a sample run.
    print_comm (Callable[[str], None], optional): A callable to print messages. Defaults to print.

  Returns:
    tuple[frame.ComputationParameters, image.Image]: A tuple containing the updated
        computation parameters and the rendered fractal image.

  Raises:
    Error: on error

  """
  # if max_iter is MIN_ITER, we do an adaptive iteration limit calculation based on a small image;
  # BEWARE: the method call will call ComputeFractal() recursively, so skip MIN_IMAGE_SIZE
  n_processes = frame.ConcurrenceToUse(n_processes)
  is_preprocess: bool = (
    params.width == frame.MIN_IMAGE_SIZE and params.height == frame.MIN_IMAGE_SIZE
  )
  if params.depth == frame.MIN_ITER and max(params.size) > frame.MIN_IMAGE_SIZE:
    # MIN_ITER is a special mark that means "automatically calculate the depth" based on the frame,
    # but we only do this if the image is larger than the minimum size (we use those for probing)
    max_iter: int
    max_iter, stats = FractalAdaptiveIterations(
      params.frm,
      set_points=params.set_points,
      progress_bar=progress_bar,
      n_processes=n_processes,
      print_comm=print_comm,
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
      # combine stats from all tasks: n_interior is additive, _lo fields take min of non-None
      # values (or None if all None), _hi fields take max of non-None values (or None if all None)
      img.stats = image.FractalStats(
        n_px=all_stats[0].n_px,  # same in all tasks (= width * height)
        n_interior=sum(s.n_interior for s in all_stats),
        max_lo=min((s.max_lo for s in all_stats if s.max_lo is not None), default=None),
        max_hi=max((s.max_hi for s in all_stats if s.max_hi is not None), default=None),
        min_lo=min((s.min_lo for s in all_stats if s.min_lo is not None), default=None),
        min_hi=max((s.min_hi for s in all_stats if s.min_hi is not None), default=None),
        ang_lo=min((s.ang_lo for s in all_stats if s.ang_lo is not None), default=None),
        ang_hi=max((s.ang_hi for s in all_stats if s.ang_hi is not None), default=None),
        imag_lo=min((s.imag_lo for s in all_stats if s.imag_lo is not None), default=None),
        imag_hi=max((s.imag_hi for s in all_stats if s.imag_hi is not None), default=None),
      )
  # if the final image doesn't have stats, we can add them from the pre-process stats we collected
  if img.stats is None and stats is not None:
    img.stats = stats
  # all copied, so we can return the final image; first trigger the histogram calculation
  img.RebuildHistograms()
  logging.info(
    f'ComputeFractal done: {params.frm.fractal.value} {params.width} x {params.height} '
    f'depth={params.depth}, interior={img.stats.n_interior if img.stats else "?"}'
  )
  return (params, img)


def FractalAdaptiveIterations(
  frm: frame.Frame,
  *,
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
    tuple[int, image.FractalStats]: The estimated max_iter for the full image (based on the
        escape histogram of the test render) and the FractalStats collected during the probe.

  Raises:
    Error: if the estimated max_iter exceeds the adaptive limit

  """
  logging.info(f'Auto-depth search for {frm.fractal.value} frame, limits: {frame.HIGH_ITERS}')
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
    # estimate the needed iterations for the full image based on the smallest image; check stats
    if img16.stats is None or img16.ext_hist is None or img16.int_hist is None:
      raise Error('Fractal stats should have been collected during rendering, but are missing')
    # do we have any exterior points that escaped? if not, we can't estimate
    if img16.ext_hist.count == 0:
      logging.info(f'Auto-depth: {high_iter=} produced no exterior points, retrying deeper')
      continue  # no exterior points
    # we have exterior points, so we can look at the histogram sorted by escape iteration;
    # find the trimmed max: skip the top _ITER_OUTLIER_SKIP pixels from the histogram tail
    remaining_to_skip: int = _ITER_OUTLIER_SKIP
    max_iter = img16.ext_hist.linear[-1][0]  # default: absolute max
    for value, count in reversed(img16.ext_hist.linear):
      if remaining_to_skip <= 0 or count > remaining_to_skip:
        max_iter = value
        break
      remaining_to_skip -= count
    # apply safety factor and clamp
    max_iter = min(frame.MAX_ITER, max(frame.MIN_ITER, int(max_iter * _ITER_SAFETY_FACTOR)))
    if max_iter < high_iter:
      # we found a winner! print and stop
      if progress_bar:
        print_comm(
          f'Picked depth {max_iter}, histogram {image.SummaryHistogram(img16.ext_hist.linear)}, '
          f'{img16.stats.n_interior}/{img16.stats.n_px} set points'
        )
      return (max_iter, img16.stats)
    if progress_bar:
      print_comm(
        f'[red]Iteration limit of {high_iter} was too low:[/] will try again [red]10x[/] deeper...'
      )
    # here we didn't find, so we loop to the next higher limit...
  # if we exhausted all the high_iters without finding a suitable max_iter, we have to give up
  raise Error(
    f'Estimated {max_iter=} is above the adaptive limit of {frame.HIGH_ITERS[-1]}; '
    'maybe this frame is interior-only (all pixels are non-escaping)'
  )


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class _FractalTaskInput:
  """Defines the input for a single Mandelbrot/Julia computation task.

  Attributes:
    params (frame.ComputationParameters): The full computation parameters for this task,
        including the frame, image dimensions, depth, and optional set points algorithm.
    progress_bar (bool): If True, this task should render a progress bar during computation.
    n_task (int): The 1-based index of this task among the total tasks.
    total_tasks (int): The total number of tasks in the computation batch.
    stats (image.FractalStats | None): Optional pre-collected stats from a sample run;
        if None, no sample-run stats are attached; default is None.

  """

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
  """Defines the output of a single Mandelbrot/Julia computation task.

  Attributes:
    img (image.Image): The completed fractal image produced by this task.
    n_task (int): The 1-based index of this task among the total tasks.
    total_tasks (int): The total number of tasks in the computation batch.

  """

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
    # pre-compute normalization function used everywhere for set points
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
    p_bar: tqdm.rich.tqdm[NoReturn] = tqdm.rich.tqdm(
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
            raise Error(f'Interior point exceeded max |z|^2 of 4, should never happen, {max_z2=}')
          # always count interior points, even if we don't do any special coloring for them
          n_interior += 1
          # now, for every possible set px algorithms, we do the final computations
          if inp.params.set_points is None:
            # default coloring: just mark as interior with a special negative value
            escaped_at = -frame.SET_INTERIOR_RESOLUTION  # negative to mark it as interior!
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MIN and stats_min:
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
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MAX and stats_max:
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
          elif inp.params.set_points == frame.SetHighlightAlgorithm.ANGLE and stats_ang:
            # angle stats for interior points; first the stats...
            ang: gmpy2.mpfr = gmpy2.atan2(zy, zx)  # angle in radians, between -pi and pi
            ang = (ang + mpfr_pi) / mpfr_two_pi  # shift to [0, 2pi] then to [0, 1]
            ang_lo = min(ang_lo, ang)
            ang_hi = max(ang_hi, ang)
            # ...then the normalized value for coloring
            escaped_at = (
              # ang_lo & ang_delta are pre-computed
              normalize(ang, inp.stats.ang_lo, ang_delta)  # type: ignore[union-attr, arg-type]
              if stats_ang
              else normalize(ang, _MPFR_ZERO, _MPFR_ONE)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.IMAGINARY and stats_imag:
            # Imaginary Weight Average: mean(sin(arg(z))**2) over orbit; first the stats...
            imag_mean: gmpy2.mpfr = (imag_acc / max_iter_p_1) / frame.MPFR_MAX_SET_Z
            imag_lo = min(imag_lo, imag_mean)
            imag_hi = max(imag_hi, imag_mean)
            # ...then the normalized value for coloring
            escaped_at = (
              # imag_lo & imag_delta are pre-computed
              normalize(imag_mean, inp.stats.imag_lo, imag_delta)  # type: ignore[union-attr, arg-type]
              if stats_imag
              else normalize(imag_mean, _MPFR_ZERO, _MPFR_ONE)
            )
          else:
            raise Error(f'Unknown fractal type {inp.params.set_points=}; should never happen')
        # either in or out of the set, we now should always have a value for escaped_at;
        # this is setting the pixel escape (not the coloring! that is done later in image.Image)
        img.escape[px_count] = image.EncodeIntFloatTo64(escaped_at, smooth_escape)  # carefully set
        p_bar.update(1)  # we touched a pixel, so update the progress bar
    # done; return the stats we collected with the task output
    p_bar.close()
    img.stats = image.FractalStats(
      n_px=inp.params.width * inp.params.height,
      n_interior=n_interior,
      max_lo=max_lo if max_hi >= max_lo else None,  # sentinel (4, 0) means no data collected
      max_hi=max_hi if max_hi >= max_lo else None,
      min_lo=min_lo if min_hi >= min_lo else None,  # sentinel (4, 0) means no data collected
      min_hi=min_hi if min_hi >= min_lo else None,
      ang_lo=ang_lo if ang_hi >= ang_lo else None,  # sentinel (1, 0) means no data collected
      ang_hi=ang_hi if ang_hi >= ang_lo else None,
      imag_lo=imag_lo if imag_hi >= imag_lo else None,  # sentinel (1, 0) means no data collected
      imag_hi=imag_hi if imag_hi >= imag_lo else None,
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
    # pre-compute normalization function used everywhere for set points
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
    p_bar: tqdm.rich.tqdm[NoReturn] = tqdm.rich.tqdm(
      total=inp.params.width * inp.params.height,
      desc='Pre' if is_preprocess else 'Img',
      unit='px',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='green',
      disable=not inp.progress_bar or (has_procs and n_task != 0),  # show for the 1st process only
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
          img.escape[px_count] = image.EncodeIntFloatTo64(0, 0.0)  # orbit escapes at the start
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
            raise Error(f'Interior point exceeded max |z|^2 of 4, should never happen, {max_z2=}')
          # always count interior points, even if we don't do any special coloring for them
          n_interior += 1
          # now, for every possible set px algorithms, we do the final computations
          if inp.params.set_points is None:
            # default coloring: just mark as interior with a special negative value
            escaped_at = -frame.SET_INTERIOR_RESOLUTION  # negative to mark it as interior!
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MIN and stats_min:
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
          elif inp.params.set_points == frame.SetHighlightAlgorithm.MAX and stats_max:
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
          elif inp.params.set_points == frame.SetHighlightAlgorithm.ANGLE and stats_ang:
            # angle stats for interior points; first the stats...
            ang: gmpy2.mpfr = gmpy2.atan2(zy, zx)  # angle in radians, between -pi and pi
            ang = (ang + mpfr_pi) / mpfr_two_pi  # shift to [0, 2pi] then to [0, 1]
            ang_lo = min(ang_lo, ang)
            ang_hi = max(ang_hi, ang)
            # ...then the normalized value for coloring
            escaped_at = (
              # ang_lo & ang_delta are pre-computed
              normalize(ang, inp.stats.ang_lo, ang_delta)  # type: ignore[union-attr, arg-type]
              if stats_ang
              else normalize(ang, _MPFR_ZERO, _MPFR_ONE)
            )
          elif inp.params.set_points == frame.SetHighlightAlgorithm.IMAGINARY and stats_imag:
            # Imaginary Weight Average: mean(sin(arg(z))**2) over orbit; first the stats...
            imag_mean: gmpy2.mpfr = (imag_acc / max_iter_p_1) / frame.MPFR_MAX_SET_Z
            imag_lo = min(imag_lo, imag_mean)
            imag_hi = max(imag_hi, imag_mean)
            # ...then the normalized value for coloring
            escaped_at = (
              # imag_lo & imag_delta are pre-computed
              normalize(imag_mean, inp.stats.imag_lo, imag_delta)  # type: ignore[union-attr, arg-type]
              if stats_imag
              else normalize(imag_mean, _MPFR_ZERO, _MPFR_ONE)
            )
          else:
            raise Error(f'Unknown fractal type {inp.params.set_points=}; should never happen')
        # either in or out of the set, we now should always have a value for escaped_at;
        # this is setting the pixel escape (not the coloring! that is done later in image.Image)
        img.escape[px_count] = image.EncodeIntFloatTo64(escaped_at, smooth_escape)  # carefully set
        p_bar.update(1)  # we touched a pixel, so update the progress bar
    # done; return the stats we collected with the task output
    p_bar.close()
    img.stats = image.FractalStats(
      n_px=inp.params.width * inp.params.height,
      n_interior=n_interior,
      max_lo=max_lo if max_hi >= max_lo else None,  # sentinel (4, 0) means no data collected
      max_hi=max_hi if max_hi >= max_lo else None,
      min_lo=min_lo if min_hi >= min_lo else None,  # sentinel (4, 0) means no data collected
      min_hi=min_hi if min_hi >= min_lo else None,
      ang_lo=ang_lo if ang_hi >= ang_lo else None,  # sentinel (1, 0) means no data collected
      ang_hi=ang_hi if ang_hi >= ang_lo else None,
      imag_lo=imag_lo if imag_hi >= imag_lo else None,  # sentinel (1, 0) means no data collected
      imag_hi=imag_hi if imag_hi >= imag_lo else None,
    )
    return _FractalTaskOutput(img=img, n_task=inp.n_task, total_tasks=inp.total_tasks)


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
    Error: if the normalized smooth escape part is not in [0,1) after normalization

  """
  # if nu is not finite consider it an error
  if not math.isfinite(nu):
    raise Error(f'nu is not a valid number {nu=}, bug! report')
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
  if not (0.0 <= nu < 1.0):
    raise Error(f'Normalized smooth escape range should be 0 <= {nu=} < 1, {n=}, bug! report')
  return (n, nu)
