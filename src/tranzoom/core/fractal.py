# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing.

BEWARE when debugging/editing this module:

On MacOS (Python ≥ 3.8) --- and presumably on other systems too --- the default multiprocessing
start method is "spawn", not "fork". With spawn, each worker process is a fresh Python interpreter
that re-imports all modules from disk when it starts. This means that unless `--threads` is
manually set to 1, the code will reload for every worker every time an image is rendered.

This means that if you are executing some long computation with many fractals (think animation),
and you start editing this part of the codebase, you may break your running computation in
really ugly ways.

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>
"""

from __future__ import annotations

import dataclasses
import logging
from collections import abc
from concurrent import futures

from tranzoom.core import fractalfast, frame, image

_ITER_OUTLIER_SKIP: int = 3  # skip up to this many extreme-outlier pixels in the probe
_ITER_SAFETY_FACTOR: float = 1.5  # we multiply the estimated iter by this to be safe


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
  # log the start of the render (not pre-computation anymore here)
  logging.info(
    f'{params.frm.fractal.value.upper()} using {n_processes} process(es) '
    f'for {"PRE " if is_preprocess else ""}rendering '
    f'- {"CYTHON fractalfast.py" if fractalfast.CYTHON else "PURE PYTHON fractalfast.py"}'
  )
  # create inputs
  inp: list[image.FractalTaskInput] = [
    image.FractalTaskInput(
      params=params,
      progress_bar=progress_bar,
      n_task=i + 1,
      total_tasks=n_processes,
      stats=stats,
    )
    for i in range(n_processes)
  ]
  # execute in processes
  results: list[image.FractalTaskOutput]
  computation: image.FractalComputation = (
    fractalfast.MandelbrotComputation
    if params.frm.fractal == frame.Fractal.MANDELBROT
    else fractalfast.JuliaComputation
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
