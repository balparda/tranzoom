# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Zoom."""

from __future__ import annotations

import dataclasses
import io
import math
import pathlib
from collections import abc

import numpy as np
from PIL import Image as PILImage

from tranzoom.core import fractal, image


class Error(fractal.Error):
  """Base zoom exception."""


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class RenderedZoomFrame:
  """One fully-rendered base animation frame."""

  idx: int
  data: bytes
  data_hash: str
  img_path: pathlib.Path


def FrameEstimatedIters(d: int, s: image.FractalStats) -> int:
  """Estimate a measure for how hard the iterations will be for this frame.

  We will use the following approximation:
    - 1/5 of depth, plus
    - 4/5 of depth allocated as percentage of estimated set points (s.n_interior / s.n_px)

  Args:
    d (int): estimated depth for frame
    s (image.FractalStats):  estimated stats for image

  Returns:
    int: estimated iteration count for frame, used for progress bar estimation;
        (d // 5) <= estimate <= d

  """
  return d // 5 + math.floor((4.0 * d * s.n_interior) / (5.0 * s.n_px))


def PngBytesFromRGBArray(arr: np.ndarray) -> bytes:
  """Encode an RGB uint8 numpy array as PNG bytes.

  Args:
    arr (np.ndarray): A 3D numpy array of shape (height, width, 3) and dtype uint8: an RGB image

  Returns:
    bytes: The PNG-encoded bytes of the image.

  Raises:
    image.Error: If the input array is not of dtype uint8

  """
  # sanity check
  if arr.dtype != np.uint8:
    raise image.Error(f'Expected uint8 array, got {arr.dtype}')
  # save to PNG bytes
  with io.BytesIO() as buf:
    PILImage.fromarray(arr, mode='RGB').save(buf, format='PNG')
    return buf.getvalue()


def RGBImageFromBytes(img_data: bytes, width: int, height: int) -> PILImage.Image:
  """Decode frame bytes and return an RGB Pillow image copy.

  Args:
    img_data (bytes): The PNG-encoded bytes of the image.
    width (int): The expected width of the image.
    height (int): The expected height of the image.

  Returns:
    PILImage.Image: A Pillow Image object in RGB mode.

  Raises:
    image.Error: on error

  """
  # open
  with PILImage.open(io.BytesIO(img_data)) as img:
    # check size and mode
    if img.size != (width, height):
      raise image.Error(f'frame size {img.size} != {(width, height)}')
    if img.mode != 'RGB':
      raise image.Error(f'frame mode {img.mode} != RGB')
    # make a copy
    return img.copy()


def CenterZoomRGB(img: PILImage.Image, scale: float) -> PILImage.Image:
  """Return img zoomed around its center.

  scale > 1 zooms in.
  scale < 1 zooms out.
  scale == 1 returns a copy.

  Pillow affine transforms use an inverse mapping: for every output pixel,
  the coefficients map back into the input image.

  Args:
    img (PILImage.Image): The input RGB image to be zoomed.
    scale (float): The zoom scale factor. Must be a finite positive number.

  Returns:
    PILImage.Image: A new Pillow Image object that is the zoomed version of the input

  Raises:
    image.Error: on error

  """
  # check scale is valid
  if not math.isfinite(scale) or scale <= 0.0:
    raise image.Error(f'invalid interpolation zoom scale: {scale}')
  # if scale is effectively 1, return a copy
  if abs(scale - 1.0) < 1e-12:  # noqa: PLR2004
    return img.copy()
  # get center
  width, height = img.size
  cx: float = (width - 1) / 2.0
  cy: float = (height - 1) / 2.0
  # compute inverse scale for Pillow affine transform
  inv: float = 1.0 / scale
  return img.transform(
    img.size,
    PILImage.Transform.AFFINE,
    (
      inv,
      0.0,
      cx - cx * inv,
      0.0,
      inv,
      cy - cy * inv,
    ),
    resample=PILImage.Resampling.BICUBIC,
    fillcolor=(0, 0, 0),
  )


def LinearInterpolatedFrame(
  curr_img: RenderedZoomFrame,
  next_img: RenderedZoomFrame,
  *,
  zoom_per_step: float,
  frac: float,
  width: int,
  height: int,
) -> bytes:
  """Interpolate between curr_img and next_img at fraction frac.

  Args:
    curr_img (_RenderedZoomFrame): The current rendered zoom frame.
    next_img (_RenderedZoomFrame): The next rendered zoom frame.
    zoom_per_step (float): The zoom factor per step between frames.
    frac (float): The interpolation fraction between 0.0 and 1.0.
    width (int): The width of the images.
    height (int): The height of the images.

  Returns:
    bytes: The PNG-encoded bytes of the interpolated image.

  Raises:
    image.Error: on error

  """
  # check params and convert images
  if not math.isfinite(zoom_per_step) or zoom_per_step <= 0.0:
    raise image.Error(f'Invalid zoom_per_step: {zoom_per_step}')
  if not (0.0 <= frac <= 1.0):
    raise image.Error(f'Invalid interpolation fraction: {frac}')
  c: PILImage.Image = RGBImageFromBytes(curr_img.data, width, height)
  n: PILImage.Image = RGBImageFromBytes(next_img.data, width, height)
  # align both images to the virtual zoom depth between the two real frames
  curr_aligned: PILImage.Image = CenterZoomRGB(c, zoom_per_step**frac)
  next_aligned: PILImage.Image = CenterZoomRGB(n, zoom_per_step ** (frac - 1.0))
  # blend
  return PngBytesFromRGBArray(np.asarray(PILImage.blend(curr_aligned, next_aligned, frac)))


def QuadraticInterpolatedFrame(
  curr_img: RenderedZoomFrame,
  next_img_1: RenderedZoomFrame,
  next_img_2: RenderedZoomFrame,
  *,
  zoom_per_step: float,
  frac: float,
  width: int,
  height: int,
) -> bytes:
  """Quadratic interpolation using curr_img, next_img_1, next_img_2.

  Points are interpreted as:
    curr_img  at x = 0
    next_img_1 at x = 1
    next_img_2 at x = 2

  We evaluate the quadratic at x = t, where 0 < t < 1.

  Args:
    curr_img (_RenderedZoomFrame): The current rendered zoom frame.
    next_img_1 (_RenderedZoomFrame): The next rendered zoom frame.
    next_img_2 (_RenderedZoomFrame): The next rendered zoom frame after next_img_1.
    zoom_per_step (float): The zoom factor per step between frames.
    frac (float): The interpolation fraction between 0.0 and 1.0.
    width (int): The width of the images.
    height (int): The height of the images.

  Returns:
    bytes: The PNG-encoded bytes of the interpolated image.

  Raises:
    image.Error: on error

  """
  # check params and convert images
  if not math.isfinite(zoom_per_step) or zoom_per_step <= 0.0:
    raise image.Error(f'Invalid zoom_per_step: {zoom_per_step}')
  if not (0.0 <= frac <= 1.0):
    raise image.Error(f'Invalid interpolation fraction: {frac}')
  c: PILImage.Image = RGBImageFromBytes(curr_img.data, width, height)
  n1: PILImage.Image = RGBImageFromBytes(next_img_1.data, width, height)
  n2: PILImage.Image = RGBImageFromBytes(next_img_2.data, width, height)
  # align all three samples to the same virtual zoom depth
  curr_aligned: PILImage.Image = CenterZoomRGB(c, zoom_per_step**frac)
  next_aligned_1: PILImage.Image = CenterZoomRGB(n1, zoom_per_step ** (frac - 1.0))
  next_aligned_2: PILImage.Image = CenterZoomRGB(n2, zoom_per_step ** (frac - 2.0))
  # blend using Lagrange interpolation
  a0: np.ndarray = np.asarray(curr_aligned, dtype=np.float32)
  a1: np.ndarray = np.asarray(next_aligned_1, dtype=np.float32)
  a2: np.ndarray = np.asarray(next_aligned_2, dtype=np.float32)
  w0: float = ((frac - 1.0) * (frac - 2.0)) / 2.0
  w1: float = -frac * (frac - 2.0)
  w2: float = (frac * (frac - 1.0)) / 2.0
  out: np.ndarray = w0 * a0 + w1 * a1 + w2 * a2
  return PngBytesFromRGBArray(out)


def InterpolatedFrameStream(
  pairs: abc.Iterable[tuple[RenderedZoomFrame, RenderedZoomFrame | None]],
  *,
  i_frames: int,
  zoom_per_step: float,
  width: int,
  height: int,
) -> abc.Iterator[bytes]:
  """Yield real + interpolated animation frames.

  For every real curr frame:
    - yield curr
    - if next exists, yield M interpolated frames between curr and next

  The pair is named (curr, next), but for quadratic interpolation we use
  the current pair plus the next pair's next frame by keeping one-frame
  lookahead in this function.

  Args:
    pairs (RenderedZoomFrame, RenderedZoomFrame | None]]): An iterable of pairs of frames
        (curr, next).
    i_frames (int): The number of interpolated frames to generate between each pair of real frames.
    zoom_per_step (float): The zoom factor per step between frames.
    width (int): The width of the images.
    height (int): The height of the images.

  Yields:
    bytes: The PNG-encoded bytes of each frame (real and interpolated).

  Raises:
    image.Error: on error

  """
  # check params
  image.ValidateIFrames(i_frames)
  if not math.isfinite(zoom_per_step) or zoom_per_step <= 0.0:
    raise image.Error(f'Invalid zoom_per_step: {zoom_per_step}')
  # create an iterator over the pairs, get the first one
  it: abc.Iterator[tuple[RenderedZoomFrame, RenderedZoomFrame | None]] = iter(pairs)
  curr_frame: RenderedZoomFrame
  next_frame: RenderedZoomFrame | None
  try:
    curr_frame, next_frame = next(it)
  except StopIteration:
    # no frames to yield
    return
  # loop over the pairs, yielding the current frame and interpolated frames until we get the last
  next_pending: tuple[RenderedZoomFrame, RenderedZoomFrame | None] | None
  while True:
    # get the next triple for lookahead
    try:
      next_pending = next(it)
    except StopIteration:
      next_pending = None
    # always yield the real current frame
    yield curr_frame.data
    # no next real frame means curr is the final real frame
    if next_frame is None:
      return  # done
    # for quadratic interpolation of curr_frame -> next_frame, use next2 when available.
    next2: RenderedZoomFrame | None = None if next_pending is None else next_pending[1]
    for jj in range(i_frames):
      frac: float = float(jj + 1) / float(i_frames + 1)
      if next2 is None:
        yield LinearInterpolatedFrame(
          curr_frame,
          next_frame,
          zoom_per_step=zoom_per_step,
          frac=frac,
          width=width,
          height=height,
        )
      else:
        yield QuadraticInterpolatedFrame(
          curr_frame,
          next_frame,
          next2,
          zoom_per_step=zoom_per_step,
          frac=frac,
          width=width,
          height=height,
        )
    # if we have a next triple, advance the frames; otherwise, we are done
    if next_pending is None:
      return  # done
    curr_frame, next_frame = next_pending
