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
_MPFR_MAX_SET_Z: gmpy2.mpfr = _MPFR_TWO
_MPFR_SET_INTERIOR_RESOLUTION: gmpy2.mpfr = gmpy2.mpfr(frame.SET_INTERIOR_RESOLUTION)
_MPFR_SET_INTERIOR_SCALE: gmpy2.mpfr = _MPFR_SET_INTERIOR_RESOLUTION / _MPFR_MAX_SET_Z


class Error(image.Error):
  """Base fractal exception."""


def Mandelbrot(
  frm: frame.Frame,
  width: int,
  height: int,
  *,
  max_iter: int | None = None,
  progress_bar: bool = True,
  n_processes: int | None = None,
  print_comm: abc.Callable[[str], None] = print,
) -> image.Image:
  """Render the Mandelbrot frame rectangle to an Image.

  Args:
    frm (Frame): The frame to render.
    width (int): The width of the output image in pixels.
    height (int): The height of the output image in pixels.
    max_iter (int | None, optional): The maximum number of iterations to determine escape.
        Defaults to None, and that means "auto".
    progress_bar (bool, optional): Whether to show a progress bar. Defaults to True.
    n_processes (int | None, optional): The number of processes to use for rendering. Defaults
        to None, which means to use all available CPU cores. Will be limited to MAX_CONCURRENCE.
    print_comm (Callable[[str], None], optional): A callable to print messages. Defaults to print.

  Returns:
    image.Image: The rendered fractal image.

  Raises:
    Error: on error

  """
  # determine processes
  if n_processes is not None and n_processes < 1:
    raise Error(f'{n_processes=} must be a positive integer or None')
  is_preprocess: bool = width == frame.MIN_IMAGE_SIZE and height == frame.MIN_IMAGE_SIZE
  n_processes = n_processes or AVAILABLE_CPU
  n_processes = min(n_processes, _MAX_PRE_PROCESS_CONCURRENCE) if is_preprocess else n_processes
  n_processes = min(n_processes, MAX_CONCURRENCE, AVAILABLE_CPU)  # never exceed CPU!
  # if max_iter is None, we do an adaptive iteration limit calculation based on a small test render
  # BEWARE: the method call will call Mandelbrot() recursively, but with a fixed max_iter!
  max_iter = (
    _FractalAdaptiveIterations(frm, progress_bar, n_processes, print_comm)
    if max_iter is None
    else max_iter
  )
  logging.debug(
    f'Mandelbrot using {n_processes} process(es) for {"PRE " if is_preprocess else ""}rendering'
  )
  # create inputs
  inp: list[_FractalTaskInput] = [
    _FractalTaskInput(
      frm=frm,
      width=width,
      height=height,
      max_iter=max_iter,
      progress_bar=progress_bar,
      n_task=i + 1,
      total_tasks=n_processes,
    )
    for i in range(n_processes)
  ]
  # execute in processes
  results: list[_FractalTaskOutput]
  if n_processes == 1:
    # no multiprocessing, just run the single task directly in this process (also good for debug)
    results = [_MandelbrotComputation(inp[0])]
  else:
    # multiprocessing: run the tasks in separate processes and collect results
    with futures.ProcessPoolExecutor(max_workers=n_processes) as executor:
      results = list(executor.map(_MandelbrotComputation, inp))
  # at this point all tasks are finished: check we have them all!
  if len(results) != n_processes:
    raise Error(f'Expected {n_processes} results from Mandelbrot computations, got {len(results)}')
  img: image.Image = results[0].img  # start with the first image to save time and space
  if n_processes > 1:
    # combine results into a single image; possible b/c each task wrote to a disjoint set of pixels
    for result in results[1:]:
      # copy only this task's interleaved pixels into the final image
      n_task: int = result.n_task - 1  # convert to 0-based index for stepped slice indexing
      img.escape[n_task::n_processes] = result.img.escape[n_task::n_processes]
  # all copied, so we can return the final image
  return img


def Julia(
  frm: frame.FrameAndPoint,
  width: int,
  height: int,
  *,
  max_iter: int | None = None,
  progress_bar: bool = True,
  n_processes: int | None = None,
  print_comm: abc.Callable[[str], None] = print,
) -> image.Image:
  """Render the Julia frame rectangle to an Image.

  Args:
    frm (FrameAndPoint): The frame to render.
    width (int): The width of the output image in pixels.
    height (int): The height of the output image in pixels.
    max_iter (int | None, optional): The maximum number of iterations to determine escape.
        Defaults to None, and that means "auto".
    progress_bar (bool, optional): Whether to show a progress bar. Defaults to True.
    n_processes (int | None, optional): The number of processes to use for rendering. Defaults
        to None, which means to use all available CPU cores. Will be limited to MAX_CONCURRENCE.
    print_comm (Callable[[str], None], optional): A callable to print messages. Defaults to print.

  Returns:
    image.Image: The rendered fractal image.

  Raises:
    Error: on error

  """
  # determine processes
  if n_processes is not None and n_processes < 1:
    raise Error(f'{n_processes=} must be a positive integer or None')
  is_preprocess: bool = width == frame.MIN_IMAGE_SIZE and height == frame.MIN_IMAGE_SIZE
  n_processes = n_processes or AVAILABLE_CPU
  n_processes = min(n_processes, _MAX_PRE_PROCESS_CONCURRENCE) if is_preprocess else n_processes
  n_processes = min(n_processes, MAX_CONCURRENCE, AVAILABLE_CPU)  # never exceed CPU!
  # if max_iter is None, we do an adaptive iteration limit calculation based on a small test render
  # BEWARE: the method call will call Julia() recursively, but with a fixed max_iter!
  max_iter = (
    _FractalAdaptiveIterations(frm, progress_bar, n_processes, print_comm)
    if max_iter is None
    else max_iter
  )
  logging.debug(
    f'Julia using {n_processes} process(es) for {"PRE " if is_preprocess else ""}rendering'
  )
  # create inputs
  inp: list[_FractalTaskInput] = [
    _FractalTaskInput(
      frm=frm,
      width=width,
      height=height,
      max_iter=max_iter,
      progress_bar=progress_bar,
      n_task=i + 1,
      total_tasks=n_processes,
    )
    for i in range(n_processes)
  ]
  # execute in processes
  results: list[_FractalTaskOutput]
  if n_processes == 1:
    # no multiprocessing, just run the single task directly in this process (also good for debug)
    results = [_JuliaComputation(inp[0])]
  else:
    # multiprocessing: run the tasks in separate processes and collect results
    with futures.ProcessPoolExecutor(max_workers=n_processes) as executor:
      results = list(executor.map(_JuliaComputation, inp))
  # at this point all tasks are finished: check we have them all!
  if len(results) != n_processes:
    raise Error(f'Expected {n_processes} results from Julia computations, got {len(results)}')
  img: image.Image = results[0].img  # start with the first image to save time and space
  if n_processes > 1:
    # combine results into a single image; possible b/c each task wrote to a disjoint set of pixels
    for result in results[1:]:
      # copy only this task's interleaved pixels into the final image
      n_task: int = result.n_task - 1  # convert to 0-based index for stepped slice indexing
      img.escape[n_task::n_processes] = result.img.escape[n_task::n_processes]
  # all copied, so we can return the final image
  return img


def _FractalAdaptiveIterations(
  frm: frame.Frame, progress_bar: bool, n_processes: int, print_comm: abc.Callable[[str], None]
) -> int:
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
    img16: image.Image = {frame.Fractal.MANDELBROT: Mandelbrot, frame.Fractal.JULIA: Julia}[
      frm.fractal
    ](
      frm,  # type: ignore[arg-type]  # we know this should be correct
      frame.MIN_IMAGE_SIZE,
      frame.MIN_IMAGE_SIZE,
      max_iter=high_iter,
      progress_bar=progress_bar,
      n_processes=n_processes,
      print_comm=print_comm,
    )
    # estimate the needed iterations for the full image based on the smallest image;
    # make the histogram of escape iterations for the smallest image, and find the highest escape
    escape_histogram: dict[int, int] = {}
    for escaped_at in img16.escape:
      esc: int = escaped_at if escaped_at >= 0 else high_iter  # interior point == high_iter
      escape_histogram[esc] = escape_histogram.get(esc, 0) + 1
    # sort the histogram by escape iteration; find the highest escape iteration that < high limit
    # if all pixels hit high_iter then max_iter will be high_iter, and we WANT it to FAIL
    histogram: list[tuple[int, int]] = sorted(escape_histogram.items())
    max_iter = (
      histogram[-1][0] if histogram[-1][0] != high_iter or len(histogram) == 1 else histogram[-2][0]
    )
    # apply safety factor and clamp
    max_iter = min(frame.MAX_ITER, max(frame.MIN_ITER, int(max_iter * _ITER_SAFETY_FACTOR)))
    if max_iter < high_iter:
      # we found a winner!
      if len(histogram) > 7:  # noqa: PLR2004 ; 7 is 3 before, the middle, and 3 after
        # this is usually the case: many escape values, so summarize the middle ones
        summary_histogram: list[tuple[int, int] | tuple[str, int]] = [
          *histogram[:3],
          ('...', sum(count for _, count in histogram[3:-3])),
          *histogram[-3:],
        ]
        print_comm(f'Picked depth {max_iter}, histogram {summary_histogram}')
      else:
        # probably a pretty rare thing, but then we can show all
        print_comm(f'Picked depth {max_iter}, histogram {histogram}')
      # stop here
      return max_iter
    # here we didn't find, so we loop to the next higher limit...
  # if we exhausted all the high_iters without finding a suitable max_iter, we have to give up
  raise Error(
    f'Estimated {max_iter=} is above the adaptive limit of {frame.HIGH_ITERS[-1]}; '
    'maybe this frame is interior-only (all pixels are non-escaping)'
  )


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class _FractalTaskInput:
  """Defines a Mandelbrot task."""

  frm: frame.Frame
  width: int
  height: int
  max_iter: int
  progress_bar: bool
  n_task: int
  total_tasks: int

  def __post_init__(self) -> None:
    """Validate parameters.

    Raises:
      Error: on error

    """
    # check size
    if not (frame.MIN_IMAGE_SIZE <= self.width <= frame.MAX_IMAGE_SIZE) or not (
      frame.MIN_IMAGE_SIZE <= self.height <= frame.MAX_IMAGE_SIZE
    ):
      raise Error(
        f'{self.width=} and {self.height=} must be between '
        f'{frame.MIN_IMAGE_SIZE} and {frame.MAX_IMAGE_SIZE}'
      )
    # sanity check iter_limit: if error, it came from the user (b/c adaptive clamps to the limits)
    if not (frame.MIN_ITER <= self.max_iter <= frame.MAX_ITER):
      raise Error(f'{self.max_iter=} must be between {frame.MIN_ITER} and {frame.MAX_ITER}')
    # check task numbers
    if not (1 <= self.n_task <= self.total_tasks):
      raise Error(f'{self.n_task=} must be between 1 and {self.total_tasks}')


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class _FractalTaskOutput:
  """Defines a Mandelbrot task output."""

  img: image.Image
  n_task: int
  total_tasks: int


def _MandelbrotComputation(inp: _FractalTaskInput) -> _FractalTaskOutput:  # noqa: PLR0914
  """Compute the Mandelbrot image for the given task input. ONE THREAD FOR MULTIPROCESSING.

  Args:
    inp (_FractalTaskInput): The task input containing all parameters for the computation.

  Returns:
    _FractalTaskOutput: The rendered fractal image and task information.

  Raises:
    Error: on error

  """
  is_preprocess: bool = inp.width == frame.MIN_IMAGE_SIZE and inp.height == frame.MIN_IMAGE_SIZE
  # create image; will also check the parameters and frame validity in the Image constructor
  img: image.Image = image.Image(inp.frm, inp.width, inp.height)
  img.SetDepth(inp.max_iter)  # set the depth of the image to the max_iter we will use
  # compute pixel size in complex plane and check frame validity; exact computation (gmpy2.mpq)
  dx: gmpy2.mpq
  dy: gmpy2.mpq
  dx, dy = inp.frm.size
  dx, dy = dx / gmpy2.mpq(inp.width - 1), dy / gmpy2.mpq(inp.height - 1)
  if dx <= 0 or dy <= 0:
    raise Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
  # start the mpfr context for floating-point computations with the precision needed
  with img.context:
    # precompute x coordinates once: this matters because mpfr construction and arithmetic
    # are relatively expensive and we can reuse the x values across rows ("inner for loop");
    # also, this is where the "X" (real) coordinates are converted mpq->mpfr
    xs: list[gmpy2.mpfr] = [
      gmpy2.mpfr(inp.frm.top_re + gmpy2.mpq(i) * dx) for i in range(inp.width)
    ]
    # create progress bar based on total pixels and the options
    has_procs: bool = inp.total_tasks > 1
    n_task: int = inp.n_task - 1  # convert to 0-based index for easier modulo math
    p_bar: tqdm.tqdm[NoReturn] = tqdm.tqdm(
      total=inp.width * inp.height,
      desc='Pre' if is_preprocess else 'Img',
      unit='px',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='green',
      disable=not inp.progress_bar or (has_procs and n_task != 0),  # show for the 1st process only
    )
    # iterate over pixels in row-major order, computing escape iterations in mpfr
    px_count: int = -1
    for py in range(inp.height):
      # PILImage.frombytes interprets the first row written as the top row of the image, so
      # we iterate y inverted by starting at the top and going down;
      # this is the "outer for loop", no benefit in pre-computing y values;
      # also, this is where the "Y" (imaginary) coordinates are converted mpq->mpfr
      cy: gmpy2.mpfr = gmpy2.mpfr(inp.frm.top_im - gmpy2.mpq(py) * dy)
      # iterate over columns, reusing x values and doing the escape test in mpfr for correctness
      for px in range(inp.width):
        px_count += 1
        if has_procs and (px_count % inp.total_tasks) != n_task:
          # this pixel is not for this process, skip it but still update the progress bar
          p_bar.update(1)
          continue
        # either this is a solo process, or this pixel is for this process
        cx: gmpy2.mpfr = xs[px]
        # we can't have fast interior tests, b/c we want to tally the max |z| for interior points
        zx: gmpy2.mpfr = _MPFR_ZERO
        zy: gmpy2.mpfr = _MPFR_ZERO
        max_z2: gmpy2.mpfr = _MPFR_ZERO  # track the max |z|^2
        mag_z2: gmpy2.mpfr
        escaped_at: int = 0
        # escape-time loop, implemented with explicit zx/zy variables
        for escaped_at in range(inp.max_iter):  # noqa: B007
          zx2: gmpy2.mpfr = zx * zx
          zy2: gmpy2.mpfr = zy * zy
          # avoid sqrt(abs(z)); compare squared magnitude to 2^2
          if (mag_z2 := zx2 + zy2) > _MPFR_FOUR:
            break
          max_z2 = max(max_z2, mag_z2)  # track max |z|^2 for potential use in coloring
          # z = z^2 + c in terms of zx/zy: zx' = zx^2 - zy^2 + cx
          zy = _MPFR_TWO * zx * zy + cy
          zx = zx2 - zy2 + cx
        else:
          # if we didn't break, we reached max_iter, mark as non-escaped, so
          # we will declare this a Set point, interior; the max_z2 should be <= 4: check
          if not 0 <= max_z2 < _MPFR_FOUR:
            raise Error(f'Interior point exceeded max |z|^2 of 4, should never happen, {max_z2=}')
          # scale max_z2 to [1..SET_INTERIOR_RESOLUTION], never zero b/c being <0 is the marker!
          escaped_at = -(  # negative!
            int(gmpy2.floor(_MPFR_SET_INTERIOR_SCALE * cast('gmpy2.mpfr', gmpy2.sqrt(max_z2)))) + 1
          )  # add 1 to make it [1..SET_INTERIOR_RESOLUTION], never zero
        img.escape[px_count] = escaped_at  # carefully set this directly in the array
        p_bar.update(1)  # we touched a pixel, so update the progress bar
  # done
  p_bar.close()
  return _FractalTaskOutput(img=img, n_task=inp.n_task, total_tasks=inp.total_tasks)


def _JuliaComputation(inp: _FractalTaskInput) -> _FractalTaskOutput:  # noqa: PLR0914
  """Compute the Julia image for the given task input. ONE THREAD FOR MULTIPROCESSING.

  Args:
    inp (_FractalTaskInput): The task input containing all parameters for the computation.

  Returns:
    _FractalTaskOutput: The rendered fractal image and task information.

  Raises:
    Error: on error

  """
  if not isinstance(inp.frm, frame.FrameAndPoint):
    raise Error(f'Expected FrameAndPoint for Julia computation, got {type(inp.frm)}')
  is_preprocess: bool = inp.width == frame.MIN_IMAGE_SIZE and inp.height == frame.MIN_IMAGE_SIZE
  # create image; will also check the parameters and frame validity in the Image constructor
  img: image.Image = image.Image(inp.frm, inp.width, inp.height)
  img.SetDepth(inp.max_iter)  # set the depth of the image to the max_iter we will use
  # compute pixel size in complex plane and check frame validity; exact computation (gmpy2.mpq)
  dx: gmpy2.mpq
  dy: gmpy2.mpq
  dx, dy = inp.frm.size
  dx, dy = dx / gmpy2.mpq(inp.width - 1), dy / gmpy2.mpq(inp.height - 1)
  if dx <= 0 or dy <= 0:
    raise Error(f'frame must have positive area, got {dx=} and {dy=}, should never happen')
  # start the mpfr context for floating-point computations with the precision needed
  with img.context:
    # precompute x coordinates once: this matters because mpfr construction and arithmetic
    # are relatively expensive and we can reuse the x values across rows ("inner for loop");
    # also, this is where the "X" (real) coordinates are converted mpq->mpfr
    xs: list[gmpy2.mpfr] = [
      gmpy2.mpfr(inp.frm.top_re + gmpy2.mpq(i) * dx) for i in range(inp.width)
    ]
    # create progress bar based on total pixels and the options
    has_procs: bool = inp.total_tasks > 1
    n_task: int = inp.n_task - 1  # convert to 0-based index for easier modulo math
    p_bar: tqdm.tqdm[NoReturn] = tqdm.tqdm(
      total=inp.width * inp.height,
      desc='Pre' if is_preprocess else 'Img',
      unit='px',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='green',
      disable=not inp.progress_bar or (has_procs and n_task != 0),  # show for the 1st process only
    )
    # iterate over pixels in row-major order, computing escape iterations in mpfr
    cx: gmpy2.mpfr = gmpy2.mpfr(inp.frm.point_re)
    cy: gmpy2.mpfr = gmpy2.mpfr(inp.frm.point_im)
    px_count: int = -1
    for py in range(inp.height):
      # PILImage.frombytes interprets the first row written as the top row of the image, so
      # we iterate y inverted by starting at the top and going down;
      # this is the "outer for loop", no benefit in pre-computing y values;
      # also, this is where the "Y" (imaginary) coordinates are converted mpq->mpfr
      img_y: gmpy2.mpfr = gmpy2.mpfr(inp.frm.top_im - gmpy2.mpq(py) * dy)
      img_y2: gmpy2.mpfr = img_y * img_y  # precompute |img_y|*|img_y| once per row; reused per col
      # iterate over columns, reusing x values and doing the escape test in mpfr for correctness
      for px in range(inp.width):
        px_count += 1
        if has_procs and (px_count % inp.total_tasks) != n_task:
          # this pixel is not for this process, skip it but still update the progress bar
          p_bar.update(1)
          continue
        # either this is a solo process, or this pixel is for this process
        # starting point is inside escape radius; do the full escape-time iteration in mpfr
        zy: gmpy2.mpfr = img_y
        zx: gmpy2.mpfr = xs[px]
        max_z2: gmpy2.mpfr = _MPFR_ZERO  # track the max |z|^2
        mag_z2: gmpy2.mpfr
        # fast exterior pre-check: if |z_0|*|z_0| > 4 the starting point is already outside the
        # escape radius so the orbit escapes immediately, before any iteration; note that this is
        # the ONLY simple universal fast test available for Julia sets — unlike Mandelbrot (which
        # has closed-form algebraic interior tests for its main cardioid and period-2 bulb), Julia
        # sets have NO universal fast interior test: the filled Julia set's shape depends entirely
        # on c and has no simple global algebraic boundary description
        if zx * zx + img_y2 > _MPFR_FOUR:
          img.escape[px_count] = 0  # orbit escapes at the starting point, before any iteration
          p_bar.update(1)
          continue
        # did not escape at fast check, do the whole thing
        escaped_at: int = 0
        # escape-time loop, implemented with explicit zx/zy variables
        for escaped_at in range(inp.max_iter):  # noqa: B007
          zx2: gmpy2.mpfr = zx * zx
          zy2: gmpy2.mpfr = zy * zy
          # avoid sqrt(abs(z)); compare squared magnitude to 2^2
          if (mag_z2 := zx2 + zy2) > _MPFR_FOUR:
            break
          max_z2 = max(max_z2, mag_z2)  # track max |z|^2 for potential use in coloring
          # z = z^2 + c in terms of zx/zy: zx' = zx^2 - zy^2 + cx
          zy = _MPFR_TWO * zx * zy + cy
          zx = zx2 - zy2 + cx
        else:
          # if we didn't break, we reached max_iter, mark as non-escaped, so
          # we will declare this a Set point, interior; the max_z2 should be <= 4: check
          if not 0 <= max_z2 < _MPFR_FOUR:
            raise Error(f'Interior point exceeded max |z|^2 of 4, should never happen, {max_z2=}')
          # scale max_z2 to [1..SET_INTERIOR_RESOLUTION], never zero b/c being <0 is the marker!
          escaped_at = -(  # negative!
            int(gmpy2.floor(_MPFR_SET_INTERIOR_SCALE * cast('gmpy2.mpfr', gmpy2.sqrt(max_z2)))) + 1
          )  # add 1 to make it [1..SET_INTERIOR_RESOLUTION], never zero
        img.escape[px_count] = escaped_at  # carefully set this directly in the array
        p_bar.update(1)  # we touched a pixel, so update the progress bar
  # done
  p_bar.close()
  return _FractalTaskOutput(img=img, n_task=inp.n_task, total_tasks=inp.total_tasks)
