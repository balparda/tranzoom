# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Zoom."""

from __future__ import annotations

import bisect
import dataclasses
import enum
import io
import json
import logging
import math
import pathlib
from collections import abc
from typing import cast

import gmpy2
import imageio
import numpy as np
from PIL import Image as PILImage
from PIL import ImageChops, ImageFilter
from transcrypto.utils import base as tbase
from transcrypto.utils import timer

from tranzoom.core import fractal, frame, image

# basic computation constants
MAX_COLOR: int = 255  # max color value for 8-bit RGB channels

# interpolation constants; these could conceivably be made user-configurable, but for that they
# would need to be added to the ZoomParameters dataclass and serialized in the JSON, which is
# a bit overkill for now
DEFAULT_USE_QUADRATIC: bool = True  # use quadratic interpolation for smoother transitions
_ERODE_LINEAR: int = 5
_BLUR_LINEAR: float = 16.0
_ERODE_QUADRATIC: int = 8
_BLUR_QUADRATIC: float = 32.0

# animation constants

MIN_FRAMES: int = 3  # sanity limit for number of frames in an animation
MAX_FRAMES: int = 1_000_000  # sanity limit for number of frames in an animation
MIN_DURATION: float = 0.1  # minimum duration of an animation in seconds, for sanity checking
MAX_DURATION: float = 45000.0  # maximum duration of an animation in seconds, for sanity checking
VIDEO_DURATION_STORE_SCALE = 40_000  # MAX_DURATION * VIDEO_DURATION_STORE_SCALE < 2**31; HASH!
MIN_FPS: float = 0.1  # minimum frames per second for an animation, for sanity checking
MAX_FPS: float = 30.0  # maximum frames per second for an animation, for sanity checking
MIN_LOOP: int = 0  # minimum number of loops for a GIF animation; 0 means infinite loop
MAX_LOOP: int = 1000  # maximum number of loops for a GIF animation, for sanity checking

MAX_ZOOM_MAGNITUDE_10: float = 10000.0  # this is 10**10000 which is more than enough
DEFAULT_DEST_MAGNITUDE_10: str = '1'  # default dest magnification for zooms 10**1 = 10x zoom
DEFAULT_LOOP: int = 0  # 0 means infinite loop for GIFs
THRESHOLD_JUMPY_ZOOM_PER_FRAME: float = 1.25  # if zoom per frame is above this warn about jumpiness
MAX_TOLERATED_FRAME_MAG_ERROR: float = 0.0002  # 0.02% - max error Frame vs. reduced mpq Frame
MAX_TOLERATED_TOTAL_MAG_ERROR: float = 0.001  # 0.1% - max total cumulative error of total zoom
MAX_TOLERATED_MARKER_MAG_ERROR: float = 0.15  # 15% max error for marker frames
MAX_INTERPOLATION_FRAMES: int = 7  # sanity limit for number of interpolated frames

# gmpy2.mpq constants
_MPQ_ZERO: gmpy2.mpq = gmpy2.mpq('0')
MPQ_VIDEO_DURATION_STORE_SCALE: gmpy2.mpq = gmpy2.mpq(str(VIDEO_DURATION_STORE_SCALE))
MAGNITUDE_PER_FRAME_MARKER: gmpy2.mpq = gmpy2.mpq('13/14')  # ~8.5x zoom/marker (10**(13/14)=8.483)
MAGNITUDE_PER_DEPTH_MARKER: gmpy2.mpq = gmpy2.mpq('3/10')  # ~2x zoom/frame (10**(3/10)=1.995)


class Error(fractal.Error):
  """Base zoom exception."""


class AnimationType(enum.Enum):
  """Animation type enum."""

  GIF = 'gif'  # also the file suffix!
  MP4 = 'mp4'


DEFAULT_ANIMATION_TYPE: AnimationType = AnimationType.GIF


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class ZoomParameters(frame.SerializingFractalObject):
  """Defines the zoom parameters for video planning and rendering.

  ATTENTION: changing any attribute changes the object SHA-256 hash.

  Attributes:
    tp (AnimationType): The animation output type ('gif' or 'mp4').
    img (frame.ComputationParameters): The initial frame computation parameters; the same
        parameters are used for all frames in the animation.
    render (RenderParameters): The render parameters applied to all frames in the animation.
    mag (gmpy2.mpq): The destination magnification (as a log10 magnitude order).
    n_frames (int): The total number of frames in the animation.
    duration (int): The animation duration stored as
        round(seconds * VIDEO_DURATION_STORE_SCALE), to avoid float precision issues.
    loop (int): Number of loops for GIF animations; 0 means infinite loop;
        ignored for non-GIF types; default is 0.

  """

  # ATTENTION: changing anything here changes the HASH!!
  tp: AnimationType  # 'gif' or 'mp4'
  img: frame.ComputationParameters  # INITIAL frame; one computation parameters for all images
  render: image.RenderParameters  # one render parameters for all images
  mag: gmpy2.mpq  # destination magnitude
  n_frames: int  # number of frames in the animation
  duration: int  # round(duration in seconds * VIDEO_DURATION_STORE_SCALE): no float precision snafu
  i_frames: int = 0  # number of interpolated frames to render between every two computed frames
  loop: int = 0  # number of loops for GIFs; 0 means infinite loop; ignored for non-GIFs

  def __post_init__(self) -> None:  # noqa: C901
    """Check ZoomParameters for validity.

    Raises:
      Error: if any parameter is invalid.

    """
    # check type is valid
    if self.tp not in {AnimationType.GIF, AnimationType.MP4}:
      raise Error(f'Unknown animation type: {self.tp}')
    # check magnitude is valid
    if not (-MAX_ZOOM_MAGNITUDE_10 <= self.mag <= MAX_ZOOM_MAGNITUDE_10):
      raise Error(f'Magnitude abs() must be <= {MAX_ZOOM_MAGNITUDE_10}, got {self.mag}')
    if self.mag == _MPQ_ZERO:
      raise Error('Magnitude cannot be zero')
    # check number of frames is valid
    if not (MIN_FRAMES <= self.n_frames <= MAX_FRAMES) or self.n_steps <= 1:
      raise Error(
        f'Number of frames must be between {MIN_FRAMES} and {MAX_FRAMES}, got {self.n_frames}'
      )
    # check duration is valid
    if not (MIN_DURATION <= self.n_seconds <= MAX_DURATION):
      raise Error(
        f'Duration must be between {MIN_DURATION} and {MAX_DURATION} seconds, got {self.n_seconds}'
      )
    # check fps is valid: we already validated n_frames and duration that are used to compute fps
    if not (MIN_FPS <= self.fps <= MAX_FPS):
      raise Error(f'Frames per second must be between {MIN_FPS} and {MAX_FPS}, got {self.fps}')
    # check i_frames is valid
    ValidateIFrames(self.i_frames)
    # check ifps is valid: it also has to be between MIN_FPS and MAX_FPS
    if not (MIN_FPS <= self.ifps <= MAX_FPS):
      raise Error(f'Final interpolated FPS must be between {MIN_FPS} and {MAX_FPS} got {self.ifps}')
    # re-check total frames is valid: it also has to be between MIN_FRAMES and MAX_FRAMES
    if not (MIN_FRAMES <= self.all_frames <= MAX_FRAMES):
      raise Error(
        f'Final total frames must be between {MIN_FRAMES} and {MAX_FRAMES}, got {self.all_frames}'
      )
    # check loop count is valid for GIFs
    if self.tp == AnimationType.GIF and not (MIN_LOOP <= self.loop <= MAX_LOOP):
      raise Error(f'Loop count for GIFs must be between {MIN_LOOP} and {MAX_LOOP}, got {self.loop}')
    if self.tp != AnimationType.GIF and self.loop != 0:
      raise Error(f'Loop count is only applicable for GIFs, got {self.loop} for {self.tp}')

  def __str__(self) -> str:
    """Get string representation of the ZoomParameters.

    Format is:
      "<[ANIMATION_TYPE]: [RENDER_PARAMETERS] -> [COMPUTATION_PARAMETERS] / "
      "(mag:[MAGNIFICATION], n:[N_FRAMES]|[ALL_FRAMES], "
      "d:[DURATION(sec)], fps:([FPS])*[I_FRAMES+1], l:[LOOP])>"

    Returns:
      str: String representation of the ZoomParameters.

    """
    return (
      f'<{self.tp.name.upper()}: {self.img} -> {self.render} / '
      f'(mag:{self.mag}, n:{self.n_frames}|{self.all_frames}, d:{self.n_seconds}, '
      f'fps:({self.fps})*{self.i_frames + 1}, l:{self.loop})>'
    )

  @property
  def n_steps(self) -> int:
    """Zoom steps (always one less than the number of frames). Exact.

    Returns:
      int: The number of zoom steps.

    """
    return self.n_frames - 1  # steps is one less than frames

  @property
  def n_seconds(self) -> gmpy2.mpq:
    """Get duration, in seconds. Exactly consistent, but within ~1/VIDEO_DURATION_STORE_SCALE.

    Returns:
      gmpy2.mpq: The video duration in seconds.

    """
    return gmpy2.mpq(self.duration) / MPQ_VIDEO_DURATION_STORE_SCALE

  @property
  def fps(self) -> gmpy2.mpq:
    """Get the frames per second for this animation, calculated from n_frames and duration. Exact.

    Returns:
      gmpy2.mpq: The frames per second for this animation.

    """
    return gmpy2.mpq(self.n_frames) / self.n_seconds

  @property
  def ifps(self) -> gmpy2.mpq:
    """Get the interpolated frames per second for this animation. Exact.

    Returns:
      gmpy2.mpq: The interpolated frames per second for this animation.

    """
    return self.fps * gmpy2.mpq(self.i_frames + 1)

  @property
  def all_frames(self) -> int:
    """Get the total number of frames, including interpolated frames, for this animation. Exact.

    For every frame, except the last one, we render i_frames interpolated frames,
    so total frames is: (n_frames - 1) * (i_frames + 1) + 1

    Returns:
      int: The total number of frames for this animation.

    """
    return ((self.n_frames - 1) * (self.i_frames + 1)) + 1

  @property
  def mag_per_step(self) -> gmpy2.mpq:
    """Get the magnification per step for this animation. Exact.

    Returns:
      gmpy2.mpq: The magnification per step for this animation.

    """
    return self.mag / gmpy2.mpq(self.n_steps)

  @property
  def scalar_magnification(self) -> gmpy2.mpfr:
    """Get the scalar magnification for the whole zoom. Ultra-precision, but not exact.

    Returns:
      gmpy2.mpfr: The scalar magnification for the whole zoom.

    """
    with frame.PrecisionContext():
      return gmpy2.exp10(self.mag)

  @property
  def scalar_magnification_per_step(self) -> gmpy2.mpq:
    """Get the scalar magnification per step for this animation. Good precision, but not exact.

    Returns:
      gmpy2.mpq: The scalar magnification per step for this animation.

    """
    m: gmpy2.mpfr = gmpy2.exp10(self.mag_per_step)  # mpq -> mpfr -> mpq unavoidable, unfortunately
    return gmpy2.mpq(m)

  @property
  def data_sz_bytes(self) -> int:
    """Estimate the total RAM in bytes needed to hold all animation frames simultaneously.

    All n_frames Image objects are held with histograms (needed for FrameColorNorm during
    animation rendering), sharing the same escape_sz and hist_sz (width, height, and depth
    are constant), so those components scale linearly.  Only the FractalStats component
    grows with precision, which increases by ~ceil(mag * log2(10)) bits from the initial
    to the final frame as the zoom deepens.

    To avoid underestimating, the stats component uses the average precision over the
    animation, linearly interpolated between precision_initial and precision_final:
      stats_sz_delta = 8 * (mpfr_sz_avg - mpfr_sz_initial)  extra bytes per frame

    Uses img.mem_sz_bytes (with histograms) because frames need histograms for coloring.
    For the per-frame on-disk size (no histograms), see img.disk_sz_bytes.

    Formula:
      n_frames * img.mem_sz_bytes  +  n_frames * stats_sz_delta

    Returns:
      int: Estimated bytes to hold all n_frames Image objects simultaneously in RAM.

    """
    # all frames share the same escape_sz and hist_sz (same width/height/depth every frame);
    # only the FractalStats size (stats_sz) depends on precision, which grows as the zoom
    # deepens: precision grows ~ceil(mag * log2(10)) bits from initial to final frame;
    # the stats_sz contribution is tiny vs escape+hist but we properly interpolate
    # using the average precision over the animation
    precision_initial: int = self.img.precision
    # log2(10) ~= 3.32193; ceil(mag * log2(10)) gives extra bits needed for final frame
    precision_delta: int = math.ceil(float(self.mag) * math.log2(10))
    # clamp to valid range: 140 = _MPFR_MIN_PRECISION, 300_000 = _MPFR_MAX_PRECISION
    precision_final: int = max(140, min(precision_initial + precision_delta, 300_000))
    precision_avg: int = (precision_initial + precision_final) // 2
    # stats_sz = 2*28B (Python ints) + 8 gmpy2.mpfr fields; mpfr at p bits: 56B + ceil(p/64)*8B
    mpfr_sz_initial: int = 56 + ((precision_initial + 63) // 64) * 8
    mpfr_sz_avg: int = 56 + ((precision_avg + 63) // 64) * 8
    stats_sz_delta: int = 8 * (mpfr_sz_avg - mpfr_sz_initial)  # per-frame gain vs initial
    return self.n_frames * self.img.mem_sz_bytes + self.n_frames * stats_sz_delta

  @property
  def comp_memory_sz_bytes(self) -> int:
    """Estimate the peak RAM in bytes needed to render the full zoom animation.

    Combines all-frames-in-memory storage (data_sz_bytes, with histograms) with the
    parallel render overhead at the deepest (highest-precision) frame -- the worst case
    for mpfr object sizes.  Peak precision is max(precision_initial, precision_final),
    accounting for both forward and reverse zooms.

    Each of the up to 16 parallel processes (frame.MAX_CONCURRENCE) holds at peak
    during computation (no histograms yet -- histograms are rebuilt after computation):
    - One Image per process (escape array + stats = img.disk_sz_bytes).
    - ~25 scalar gmpy2.mpfr working variables.
    - One gmpy2.mpfr per image column (the xs pre-computation array).

    Formula:
      data_sz_bytes  +  max_concurrence * (img.disk_sz_bytes + (width + 25) * mpfr_sz_peak)

    Returns:
      int: Estimated peak bytes in RAM at the most memory-intensive point of the render.

    """
    # precision grows from initial to final frame as the zoom deepens (or decreases for neg mag);
    # log2(10) ~= 3.32193; ceil(mag * log2(10)) gives extra bits needed for the final frame
    precision_initial: int = self.img.precision
    precision_delta: int = math.ceil(float(self.mag) * math.log2(10))
    # clamp to valid range: 140 = _MPFR_MIN_PRECISION, 300_000 = _MPFR_MAX_PRECISION
    precision_final: int = max(140, min(precision_initial + precision_delta, 300_000))
    precision_peak: int = max(precision_initial, precision_final)  # worst case: deepest init./final
    # peak computation occurs at the deepest (highest-precision) frame; each of the
    # max_concurrence parallel processes holds one Image with escape array + stats but NO
    # histograms (histograms are rebuilt after parallel computation completes) = disk_sz_bytes;
    # mpfr field at p bits: 56B struct overhead + ceil(p/64)*8B mantissa limbs;
    # n_working_mpfr ~25 scalar vars + one column pre-computation (width mpfr values)
    n_working_mpfr: int = 25  # same as in frame.ComputationParameters.comp_memory_sz_bytes
    mpfr_sz_peak: int = 56 + ((precision_peak + 63) // 64) * 8
    per_proc_mpfr_sz_peak: int = (self.img.width + n_working_mpfr) * mpfr_sz_peak
    # peak = all frames in RAM (with histograms) + single-frame computation cost (no histograms)
    return self.data_sz_bytes + frame.MAX_CONCURRENCE * (
      self.img.disk_sz_bytes + per_proc_mpfr_sz_peak
    )

  def animation_sz_bytes(self) -> tuple[int, int]:
    """Estimate the on-disk size in bytes of the output GIF and MP4 animation files.

    Both formats benefit enormously from the high temporal coherence of fractal zoom
    animations -- each frame is a slightly zoomed version of the previous -- which
    inter-frame prediction (H.264) and delta-transparency encoding (GIF) exploit well.

    Empirical per-format estimates (bytes per pixel per frame):
      GIF  (PIL optimize=True, 256-color palette, LZW):  n_frames * n_px / 8   (~8:1)
      MP4  (H.264 CRF=16, preset=slow):                  n_frames * n_px / 20  (~20:1)

    Metadata cost is ONE JSON block per output file (not per frame), written as a GIF
    comment extension or MP4 container tag; the dominant variable cost is the initial
    frame's 8 mpq coordinate strings (~precision_initial * log10(2) digits each):
      meta_sz = 5000 + 8 * 2 * (precision_initial * 3 // 10 + 1)  bytes

    Returns:
      tuple[int, int]: Estimated file sizes as (gif_bytes, mp4_bytes).

    """
    n_px: int = self.img.width * self.img.height
    # GIF: each frame stored as 256-color palette (8-bit) + LZW compression; PIL saves with
    # optimize=True and delta-encodes unchanged pixels as transparent (disposal=1); for fractal
    # frames the smooth gradient interiors map well to 256-color palettes and LZW achieves
    # moderate compression; empirically ~0.125 bytes/pixel/frame on average (8:1 vs uncompressed)
    gif_sz: int = self.all_frames * n_px // 8
    # MP4: H.264 (libx264) at CRF=16 (high quality, ~2x the bits of CRF=23), preset=slow
    # (WriteVideoMP4 parameters); fractal zooms have high temporal coherence (each frame is a
    # slightly zoomed version of the previous) which H.264 inter-frame prediction exploits very
    # well; empirically ~0.05 bytes/pixel/frame on average (20:1 vs uncompressed RGB)
    mp4_sz: int = self.all_frames * n_px // 20
    # metadata: ONE JSON block per file (NOT per frame) written as the GIF comment extension
    # or the MP4 container comment tag (json.dumps(meta) in WriteAnimatedGIF/WriteVideoMP4);
    # contains all zoom/computation/render/frame parameters; see png_sz_bytes formula;
    # dominant variable cost: INITIAL FRAME coordinate strings (8 mpq values each stored as
    # "p/q" with ~precision_initial * log10(2) decimal digits per numerator and denominator);
    # 8 coords * 2 ints * (precision_initial * 3 // 10 + 1) bytes for coordinate strings
    precision_initial: int = self.img.precision
    meta_sz: int = 5000 + 8 * 2 * (precision_initial * 3 // 10 + 1)
    return (gif_sz + meta_sz, mp4_sz + meta_sz)

  @property
  def json(self) -> tbase.JSONDict:
    """Get a JSON-serializable dictionary representation of the ZoomParameters.

    Keys: `tp`, `img`, `render`, `mag`, `n_frames`, `duration`, `i_frames`, `loop`.

    Returns:
      tbase.JSONDict: A dictionary representation of the ZoomParameters.

    """
    return {
      # ATTENTION: changing anything here changes the HASH!!
      'tp': self.tp.value,
      'img': self.img.json,
      'render': self.render.json,
      'mag': str(self.mag),
      'n_frames': self.n_frames,
      'duration': self.duration,
      'i_frames': self.i_frames,
      'loop': self.loop,
    }

  @staticmethod
  def FromJson(data: tbase.JSONDict, *, check_hash: str | None = None) -> ZoomParameters:
    """Create a ZoomParameters from a JSON dictionary.

    Args:
      data (tbase.JSONDict): A dictionary like from ZoomParameters.json.
      check_hash (str | None): If provided, the expected SHA-256 hash of the ZoomParameters.
          If the calculated hash does not match, an error is raised.

    Returns:
      ZoomParameters: A ZoomParameters object

    Raises:
      Error: on error

    """
    # create the object
    try:
      params = ZoomParameters(  # object creation will check the data is valid and consistent
        tp=AnimationType(data['tp']),
        img=frame.ComputationParameters.FromJson(cast('tbase.JSONDict', data['img'])),
        render=image.RenderParameters.FromJson(cast('tbase.JSONDict', data['render'])),
        mag=gmpy2.mpq(str(data['mag'])),
        n_frames=int(str(data['n_frames'])),
        duration=int(str(data['duration'])),
        i_frames=int(str(data.get('i_frames', '0'))),
        loop=int(str(data.get('loop', '0'))),
      )
    except (KeyError, ValueError, TypeError, Error) as err:
      raise Error(f'Invalid ZoomParameters JSON data: {err}') from err
    # check hash if provided
    if check_hash is not None and params.sha != check_hash:
      raise Error(f'ZoomParameters {params.sha!r} does not match expected {check_hash!r}')
    return params

  def Frames(
    self,
  ) -> tuple[list[frame.Frame], list[tuple[int, frame.Frame]], list[tuple[int, frame.Frame]]]:
    """Get the Frames. Could be a property, but is a method to remind this is an expensive-ish call.

    Returns:
      tuple[list[frame.Frame], list[tuple[int, frame.Frame]], list[tuple[int, frame.Frame]]]:
          The (frames, marker_frames, depth_frames) for this animation,
          where marker_frames & depth_frames are a strict subset of frames and are lists
          of sorted (index, frame) pairs for frames that were picked

    Raises:
      Error: if the frames cannot be generated within the tolerated error threshold.

    """
    dx: gmpy2.mpq
    dy: gmpy2.mpq
    rdx: gmpy2.mpq
    rdy: gmpy2.mpq
    mpq_mag: gmpy2.mpq = self.scalar_magnification_per_step
    all_frames: list[frame.Frame] = [self.img.frm]  # start with initial frame, keep as-is
    # reproduce the zoom run with full precision
    frm: frame.Frame = self.img.frm
    max_denominator: int
    err_x: float
    err_y: float
    max_error_dim: float = 0.0
    with timer.Timer('frame generation'):
      # float magnification tracking: avoids 30k-bit precision mpfr computation in every loop step;
      # frm.magnification[1] is only used to compute max_denominator for limit_denominator, so
      # a float approximation is precise enough (error is << MAX_TOLERATED_FRAME_MAG_ERROR)
      mag_log10: float = self.img.frm.magnification[1]  # log10 magnification of the initial frame
      mag_step: float = float(self.mag_per_step)  # log10 magnification increment per step
      cur_mag_log10: float  # current step's approximate log10 magnification, updated each iteration
      for i in range(self.n_steps):
        # compute the current expected log10 magnification analytically (cheap float operation)
        cur_mag_log10 = mag_log10 + (i + 1) * mag_step
        # keep frm full precision and iterate
        frm = frame.Frame.FromCenter(
          frm.fractal,
          *frm.center,
          frm.size[0] / mpq_mag,  # these mpq will get HUGE: the reason we keep them in check below
          height=frm.size[1] / mpq_mag,  # these mpq will get HUGE
          point_re=frm.point_re,
          point_im=frm.point_im,
        )
        if i and not i % 10:
          # we have to keep the mpq in check; use precomputed float mag (avoids 30k-bit mpfr call)
          max_denominator = 10_000_000 * (10 ** math.ceil(cur_mag_log10 + 1e-9))
          dx, dy = frm.size
          frm = frame.Frame.FromCenter(
            frm.fractal,
            *frm.center,
            # don't call dx|dy.limit_denominator(max_denominator) read LimitMPQDenominator() pydoc!!
            frame.LimitMPQDenominator(dx, max_denominator=max_denominator)[0],
            height=frame.LimitMPQDenominator(dy, max_denominator=max_denominator)[0],
            point_re=frm.point_re,
            point_im=frm.point_im,
          )
        # make a less aggressive version of the zoom; 1e-9: if the true value is exactly an integer
        # (ex: 5) float accumulation in mag_log10 + (i+1) * mag_step can produce 4.9999999999999982
        # instead, causing math.ceil to return 4 rather than 5, making max_denominator 10x too
        # small, so 1e-9 before ceil means "within a billionth of an integer rounds up to it"
        max_denominator = 10_000 * (10 ** math.ceil(cur_mag_log10 + 1e-9))
        dx, dy = frm.size
        # don't call dx|dy.limit_denominator(max_denominator) read LimitMPQDenominator() pydoc!!
        rdx, err_x = frame.LimitMPQDenominator(dx, max_denominator=max_denominator)
        rdy, err_y = frame.LimitMPQDenominator(dy, max_denominator=max_denominator)
        max_error_dim = max(max_error_dim, err_x, err_y)
        # test error
        if max_error_dim > MAX_TOLERATED_FRAME_MAG_ERROR:
          raise Error(
            f'Frame {i + 2} has size {frm.size} but reduced frame has size {(rdx, rdy)}, '
            f'which is {100.0 * err_x:.6f}% different in width '
            f'and {100.0 * err_y:.6f}% '
            f'different in height, which is above the tolerated error threshold, '
            f'{100.0 * MAX_TOLERATED_FRAME_MAG_ERROR:.6f}%. This is a bug! (workaround: zoom with '
            'smaller jumps, i.e., any/some of: less zoom mag, more frames, more fps, more duration)'
          )
        # accept rdx/rdy as the new frame size for the reduced frame: make the frame
        all_frames.append(
          frame.Frame.FromCenter(
            frm.fractal, *frm.center, rdx, height=rdy, point_re=frm.point_re, point_im=frm.point_im
          )
        )
    # done adding frames, final check: directly compute the actual magnification achieved
    # to make sure the accumulated error is within the tolerated threshold
    actual_mag: gmpy2.mpfr = cast(
      'gmpy2.mpfr', gmpy2.log10(gmpy2.sqrt(all_frames[-1].mag2 / all_frames[0].mag2))
    )
    if (mag_error := abs(actual_mag - self.mag) / self.mag) > MAX_TOLERATED_TOTAL_MAG_ERROR:
      raise Error(
        'the actual magnification achieved by zooming in the frame is '
        f'{float(actual_mag):.6f}, which is {100.0 * float(mag_error):e}% different '
        f'from the intended {self.mag} ({float(self.mag):.6f}). This means the gmpy2.mpq needs '
        'more precision for conversion. This is a bug!'
      )
    logging.info(
      f'Generated {len(all_frames)} REGULAR Frames for the zoom, '
      f'max frame error {100.0 * float(max_error_dim):e}%, '
      f'final magnification error {100.0 * float(mag_error):e}% '
      f'(actual {float(actual_mag):.6f} vs intended {float(self.mag):.6f})'
    )
    # we finished the frame generation, now we pick them special ones
    return (
      all_frames,
      self._FramesSubset(all_frames, MAGNITUDE_PER_FRAME_MARKER, 'marker'),
      self._FramesSubset(all_frames, MAGNITUDE_PER_DEPTH_MARKER, 'depth'),
    )

  def _FramesSubset(
    self,
    all_frames: list[frame.Frame],
    mag_per_step: gmpy2.mpq,
    name: str,
  ) -> list[tuple[int, frame.Frame]]:
    """Get a subset of frames based on the given magnification step.

    Args:
      all_frames (list[frame.Frame]): The list of all frames generated for the zoom.
      mag_per_step (gmpy2.mpq): The magnification step per frame.
      name (str): The name of the subset, used for logging.

    Returns:
      list[tuple[int, frame.Frame]]: A list of (index, frame) pairs for frames that were picked.

    Raises:
      Error: if the frames cannot be generated within the tolerated error threshold.

    """
    # float magnification tracking: avoids 30k-bit precision mpfr computation in every loop step;
    # frm.magnification[1] is only used to compute max_denominator for limit_denominator, so
    # a float approximation is precise enough (error is << MAX_TOLERATED_FRAME_MAG_ERROR)
    mag_log10: float = self.img.frm.magnification[1]  # log10 magnification of the initial frame
    mag_step: float = float(self.mag_per_step)  # log10 magnification increment per step
    # we don't care about the number of frames, we care about a fixed zoom magnitude
    n_marker_steps: int = int(cast('gmpy2.mpz', max(math.floor(self.mag / mag_per_step), 1)))
    if n_marker_steps <= 1 or self.n_frames < 5:  # noqa: PLR2004
      # if we only have 2 or fewer markers (1 step), just use the first and last frames as
      # markers; same thing for few frames: [1st, X, Y, Z, last] is the smallest degenerate
      # case where it is worth having a "marker", frame Y, and return [1st, Y, last]
      logging.info(f'Frames subset {name!r} is trivial, will use [first, last]')
      return [(0, all_frames[0]), (len(all_frames) - 1, all_frames[-1])]
    # we will need more markers; start from the first and find the "ideal" stops
    with timer.Timer(f'{name} generation'):
      marker_mag: gmpy2.mpq = self.mag / gmpy2.mpq(n_marker_steps)
      marker_mag = gmpy2.mpq(
        gmpy2.exp10(marker_mag)
      )  # mpq -> mpfr -> mpq unavoidable, unfortunately
      # precompute analytical frame magnifications for O(log n) bisect-based marker search;
      # float precision is sufficient since MAX_TOLERATED_MARKER_MAG_ERROR tolerance is 6%
      all_mag_log10: list[float] = [mag_log10 + j * mag_step for j in range(len(all_frames))]
      ideal_marker_mag_log10: float = mag_log10  # tracks the ideal marker magnification
      # log10(exp10(x)) = x exactly, so use the underlying value rather than gmpy2.log10(marker_mag)
      marker_mag_step_log10: float = float(self.mag) / float(n_marker_steps)
      frm: frame.Frame = all_frames[0]  # start with initial frame, keep as-is
      marker_frames: list[tuple[int, frame.Frame]] = [(0, frm)]  # start with the first frame
      last_idx: int = 0
      idx: int
      delta_log10: float
      max_min_mag_float: float = 0.0
      for i in range(n_marker_steps):
        # advance ideal marker magnification analytically (no growing-denominator mpq computation)
        ideal_marker_mag_log10 += marker_mag_step_log10
        # find the actual frame closest to the ideal magnification using O(log n) bisect search
        insert_pos: int = bisect.bisect_left(all_mag_log10, ideal_marker_mag_log10, last_idx)
        if insert_pos >= len(all_frames):
          idx = len(all_frames) - 1
        elif insert_pos == last_idx or abs(
          all_mag_log10[insert_pos] - ideal_marker_mag_log10
        ) <= abs(
          all_mag_log10[insert_pos - 1] - ideal_marker_mag_log10
        ):  # short-circuit: when insert_pos == last_idx, insert_pos-1 is not evaluated
          idx = insert_pos
        else:
          idx = insert_pos - 1
        # track maximum relative error in mag2 space: |f.mag2 - ideal.mag2| / ideal.mag2
        # float equivalent: |10^(2*(f_log10 - ideal_log10)) - 1| (same formula, just in log space)
        delta_log10 = all_mag_log10[idx] - ideal_marker_mag_log10
        max_min_mag_float = max(max_min_mag_float, abs(10.0 ** (2.0 * delta_log10) - 1.0))
        # test that the frames are in the expected order and we are not going backwards
        new_marker: frame.Frame = all_frames[idx]
        if idx == last_idx:
          raise Error(
            f'Frames sub-set {name!r} / {i + 1} is closer to last marker index {last_idx}. Bug!'
          )
        # make sure we don't have duplicates; add it
        if (idx, new_marker) in marker_frames:
          raise Error(f'Duplicate frame found in {name!r} subset; bug! report. Frame: {new_marker}')
        marker_frames.append((idx, new_marker))
        last_idx = idx
    # done; check we arrived at the last frame and error is acceptable; if so, all is good
    if marker_frames[-1] != (len(all_frames) - 1, all_frames[-1]):
      raise Error(
        f'Last frame in {name!r} subset is not the same as the last frame; bug! report. '
        f'Last frame in subset: {marker_frames[-1]}, last frame: {all_frames[-1]}'
      )
    if any(1 for j, f in marker_frames if all_frames[j] != f):
      raise Error(f'Inconsistent hashes in {name!r} sub-set do not match frames list; Report bug!')
    if max_min_mag_float > MAX_TOLERATED_MARKER_MAG_ERROR:
      raise Error(
        f'Frames sub-set {name!r} are not close enough to the ideal frames; bug! report. '
        f'Maximum deviation in mag2 is {100.0 * max_min_mag_float:.6f}%, which is a bug! report'
      )
    logging.info(
      f'Generated {len(marker_frames) - 2} non-trivial {name!r} Frames for the zoom, '
      f'max frame deviation from ideal {100.0 * float(max_min_mag_float):.6f}%'
    )
    return marker_frames


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


def PNGBytesFromRGBArray(arr: np.ndarray) -> bytes:
  """Encode an RGB uint8 numpy array as PNG bytes.

  Args:
    arr (np.ndarray): A 3D numpy array of shape (height, width, 3) and dtype uint8: an RGB image

  Returns:
    bytes: The PNG-encoded bytes of the image.

  Raises:
    Error: If the input array is not of dtype uint8

  """
  # sanity check
  if arr.dtype != np.uint8:
    raise Error(f'Expected uint8 array, got {arr.dtype}')
  # save to PNG bytes
  with io.BytesIO() as buf:
    PILImage.fromarray(arr, mode='RGB').save(buf, format='PNG')
    return buf.getvalue()


def CenterZoomRGB(
  img: PILImage.Image,
  scale: float,
  *,
  return_mask: bool = False,
  fill_color: tuple[int, int, int] | None = None,
) -> tuple[PILImage.Image, PILImage.Image | None]:
  """Return img zoomed around its center.

  scale > 1 zooms in.
  scale < 1 zooms out.
  scale == 1 returns a copy.

  If return_mask is True, also return an L-mode validity mask:
    MAX_COLOR where the transformed output samples from inside the source image.
    0 where the transformed output is outside the source image.

  Args:
    img (PILImage.Image): The input RGB image to be zoomed.
    scale (float): The zoom scale factor. Must be a finite positive number.
    return_mask (bool): Whether to return the transform validity mask; default False.
    fill_color (tuple[int, int, int] | None): Optional RGB fill color for areas outside the
        source image. If None, the fill color is estimated from the median of the border pixels.

  Returns:
    tuple[PILImage.Image, PILImage.Image | None]: The zoomed image,
        optionally with its validity mask.

  Raises:
    Error: on error

  """
  # check image and scale are valid
  if img.mode != 'RGB':
    raise Error(f'expected RGB image, got {img.mode!r}')
  if not math.isfinite(scale) or scale <= 0.0:
    raise Error(f'invalid interpolation zoom scale: {scale}')
  if fill_color and (max(fill_color) > MAX_COLOR or min(fill_color) < 0):
    raise Error(f'invalid fill_color: {fill_color}')
  # if scale is effectively 1, return a copy
  if abs(scale - 1.0) < 1e-12:  # noqa: PLR2004
    return (img.copy(), PILImage.new('L', img.size, MAX_COLOR) if return_mask else None)
  # get center
  width: int
  height: int
  width, height = img.size
  cx: float = (width - 1) / 2.0
  cy: float = (height - 1) / 2.0
  # compute inverse scale for Pillow affine transform
  inv: float = 1.0 / scale
  affine: tuple[float, float, float, float, float, float] = (
    inv,
    0.0,
    cx - cx * inv,
    0.0,
    inv,
    cy - cy * inv,
  )
  out: PILImage.Image = img.transform(
    img.size,
    PILImage.Transform.AFFINE,
    affine,
    resample=PILImage.Resampling.BICUBIC,
    fillcolor=fill_color or BorderFillColor(img),
  )
  # if the caller does not want a mask, return just the zoomed image
  if not return_mask:
    return (out, None)
  # create a mask of the same size as the input image, filled with MAX_COLOR (valid)
  mask_src: PILImage.Image = PILImage.new('L', img.size, MAX_COLOR)
  mask: PILImage.Image = mask_src.transform(
    img.size,
    PILImage.Transform.AFFINE,
    affine,
    resample=PILImage.Resampling.NEAREST,
    fillcolor=0,
  )
  return (out, mask)


def BorderFillColor(img: PILImage.Image) -> tuple[int, int, int]:
  """Estimate a safer affine fill color from the median of the image border pixels.

  Args:
    img (PILImage.Image): The input RGB image.

  Returns:
    tuple[int, int, int]: The estimated fill color as an RGB tuple.

  Raises:
    Error: on error

  """
  # pick up only border pixels (top, bottom, left, right)
  arr: np.ndarray = np.asarray(img, dtype=np.uint8)
  border: np.ndarray = np.concatenate(
    (
      arr[0, :, :],
      arr[-1, :, :],
      arr[:, 0, :],
      arr[:, -1, :],
    ),
    axis=0,
  )
  # compute the median color of the border pixels
  color: np.ndarray = np.median(border, axis=0)
  if color.shape != (3,):
    raise Error(f'Unexpected border color shape: {color.shape}')
  return tuple(int(x) for x in color)  # type: ignore[return-value]


def FeatherValidMask(
  mask: PILImage.Image,
  *,
  erode_pixels: int,
  blur_pixels: float,
) -> PILImage.Image:
  """Return a soft validity mask.

  The valid region is first eroded, then blurred. This creates a smooth
  alpha ramp from valid transformed pixels to invalid/out-of-bounds pixels.

  Args:
    mask (PILImage.Image): L-mode mask, MAX_COLOR valid and 0 invalid.
    erode_pixels (int): Pixels to shrink the hard valid region before blur.
    blur_pixels (float): Gaussian blur radius for the alpha ramp.

  Returns:
    PILImage.Image: L-mode soft mask.

  Raises:
    Error: on error

  """
  # sanity check
  if mask.mode != 'L':
    raise Error(f'expected L mask, got {mask.mode!r}')
  if erode_pixels < 0:
    raise Error(f'pixels must be >= 0, got {erode_pixels}')
  if blur_pixels < 0.0:
    raise Error(f'blur_pixels must be >= 0, got {blur_pixels}')
  # erode first
  soft_mask: PILImage.Image = mask
  if erode_pixels:
    soft_mask = soft_mask.filter(ImageFilter.MinFilter(erode_pixels * 2 + 1))
  # then blur
  if blur_pixels:
    soft_mask = soft_mask.filter(ImageFilter.GaussianBlur(blur_pixels))
  # critical: GaussianBlur leaks white alpha into the invalid region:
  # clamp it so invalid transformed pixels remain fully transparent
  return ImageChops.multiply(soft_mask, mask)


def MaskArray(mask: PILImage.Image) -> np.ndarray:
  """Convert an L-mode mask to a float32 alpha array in [0, 1].

  Args:
    mask (PILImage.Image): L-mode mask, MAX_COLOR valid and 0 invalid

  Returns:
    np.ndarray: A float32 array of shape (height, width, 1) with values in [0, 1].

  Raises:
    Error: on error

  """
  # sanity check
  if mask.mode != 'L':
    raise Error(f'expected L mask, got {mask.mode!r}')
  # convert to float32 array in [0, 1]
  return np.asarray(mask, dtype=np.float32)[:, :, None] / float(MAX_COLOR)


def LinearInterpolatedFrame(
  curr_img: RenderedZoomFrame,
  next_img: RenderedZoomFrame,
  *,
  zoom_per_step: float,
  frac: float,
) -> bytes:
  """Interpolate between curr_img and next_img at fraction frac.

  Args:
    curr_img (_RenderedZoomFrame): The current rendered zoom frame.
    next_img (_RenderedZoomFrame): The next rendered zoom frame.
    zoom_per_step (float): The zoom factor per step between frames.
    frac (float): The interpolation fraction between 0.0 and 1.0.

  Returns:
    bytes: The PNG-encoded bytes of the interpolated image.

  Raises:
    Error: on error

  """
  # check params and convert images
  if not math.isfinite(zoom_per_step) or zoom_per_step <= 0.0:
    raise Error(f'Invalid zoom_per_step: {zoom_per_step}')
  if not (0.0 <= frac <= 1.0):
    raise Error(f'Invalid interpolation fraction: {frac}')
  c: PILImage.Image = image.RGBImageFromPNG(curr_img.data)
  n: PILImage.Image = image.RGBImageFromPNG(next_img.data)
  # align both images to the virtual zoom depth between the two real frames
  curr_border: tuple[int, int, int] = BorderFillColor(c)
  curr_aligned: PILImage.Image = CenterZoomRGB(c, zoom_per_step**frac, fill_color=curr_border)[0]
  next_aligned_raw: PILImage.Image
  next_valid_mask: PILImage.Image | None
  next_aligned_raw, next_valid_mask = CenterZoomRGB(
    n, zoom_per_step ** (frac - 1.0), return_mask=True, fill_color=curr_border
  )
  if not next_valid_mask:
    raise Error('next_valid_mask is None, but it should not be; bug! report')
  # the future frames will have a black border where the zoomed-out image is outside the
  # original image; we create a soft alpha mask to blend the current frame into the next frame
  # to avoid harsh transitions
  next_alpha_mask: PILImage.Image = FeatherValidMask(
    next_valid_mask, erode_pixels=_ERODE_LINEAR, blur_pixels=_BLUR_LINEAR
  )
  a0: np.ndarray = np.asarray(curr_aligned, dtype=np.float32)
  a1: np.ndarray = np.asarray(next_aligned_raw, dtype=np.float32)
  alpha1: np.ndarray = frac * MaskArray(next_alpha_mask)
  out: np.ndarray = a0 * (1.0 - alpha1) + a1 * alpha1
  return PNGBytesFromRGBArray(np.clip(out, 0, MAX_COLOR).astype(np.uint8))


def QuadraticInterpolatedFrame(  # noqa: PLR0914
  curr_img: RenderedZoomFrame,
  next_img_1: RenderedZoomFrame,
  next_img_2: RenderedZoomFrame,
  *,
  zoom_per_step: float,
  frac: float,
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

  Returns:
    bytes: The PNG-encoded bytes of the interpolated image.

  Raises:
    Error: on error

  """
  # check params and convert images
  if not math.isfinite(zoom_per_step) or zoom_per_step <= 0.0:
    raise Error(f'Invalid zoom_per_step: {zoom_per_step}')
  if not (0.0 <= frac <= 1.0):
    raise Error(f'Invalid interpolation fraction: {frac}')
  c: PILImage.Image = image.RGBImageFromPNG(curr_img.data)
  n1: PILImage.Image = image.RGBImageFromPNG(next_img_1.data)
  n2: PILImage.Image = image.RGBImageFromPNG(next_img_2.data)
  # align all three samples to the same virtual zoom depth
  curr_border: tuple[int, int, int] = BorderFillColor(c)
  curr_aligned: PILImage.Image = CenterZoomRGB(c, zoom_per_step**frac, fill_color=curr_border)[0]
  next_aligned_1_raw: PILImage.Image
  next_valid_mask_1: PILImage.Image | None
  next_aligned_1_raw, next_valid_mask_1 = CenterZoomRGB(
    n1, zoom_per_step ** (frac - 1.0), return_mask=True, fill_color=curr_border
  )
  next_aligned_2_raw: PILImage.Image
  next_valid_mask_2: PILImage.Image | None
  next_aligned_2_raw, next_valid_mask_2 = CenterZoomRGB(
    n2, zoom_per_step ** (frac - 2.0), return_mask=True, fill_color=curr_border
  )
  if not next_valid_mask_1 or not next_valid_mask_2:
    raise Error('next_valid_mask_1|2 is None, but it should not be; bug! report')
  # the future frames will have a black border where the zoomed-out image is outside the
  # original image; we create a soft alpha mask to blend the current frame into the next frame
  # to avoid harsh transitions
  soft_mask_1: PILImage.Image = FeatherValidMask(
    next_valid_mask_1, erode_pixels=_ERODE_LINEAR, blur_pixels=_BLUR_LINEAR
  )
  soft_mask_2: PILImage.Image = FeatherValidMask(
    next_valid_mask_2, erode_pixels=_ERODE_QUADRATIC, blur_pixels=_BLUR_QUADRATIC
  )
  # blend using Lagrange interpolation
  a0: np.ndarray = np.asarray(curr_aligned, dtype=np.float32)
  a1: np.ndarray = np.asarray(next_aligned_1_raw, dtype=np.float32)
  a2: np.ndarray = np.asarray(next_aligned_2_raw, dtype=np.float32)
  w0: float = ((frac - 1.0) * (frac - 2.0)) / 2.0
  w1: float = -frac * (frac - 2.0)
  w2: float = (frac * (frac - 1.0)) / 2.0
  alpha1: np.ndarray = MaskArray(soft_mask_1)
  alpha2: np.ndarray = MaskArray(soft_mask_2)
  # fade future-frame contributions out near their invalid borders;
  # important: when future weights are masked away, give the missing weight
  # back to curr_aligned: this keeps brightness stable and avoids dark seams
  effective_w1: np.ndarray = w1 * alpha1
  effective_w2: np.ndarray = w2 * alpha2
  effective_w0: np.ndarray = w0 + (w1 * (1.0 - alpha1)) + (w2 * (1.0 - alpha2))
  out: np.ndarray = effective_w0 * a0 + effective_w1 * a1 + effective_w2 * a2
  return PNGBytesFromRGBArray(np.clip(out, 0, MAX_COLOR).astype(np.uint8))


def InterpolatedFrameStream(
  pairs: abc.Iterable[tuple[RenderedZoomFrame, RenderedZoomFrame | None]],
  *,
  i_frames: int,
  zoom_per_step: float,
  use_quadratic: bool = DEFAULT_USE_QUADRATIC,
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
    use_quadratic (bool): Whether to use quadratic interpolation (True) or linear
        interpolation only (False); default is DEFAULT_USE_QUADRATIC

  Yields:
    bytes: The PNG-encoded bytes of each frame (real and interpolated).

  Raises:
    Error: on error

  """
  # check params
  ValidateIFrames(i_frames)
  if not math.isfinite(zoom_per_step) or zoom_per_step <= 0.0:
    raise Error(f'Invalid zoom_per_step: {zoom_per_step}')
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
      if next2 is None or not use_quadratic:
        yield LinearInterpolatedFrame(
          curr_frame,
          next_frame,
          zoom_per_step=zoom_per_step,
          frac=frac,
        )
      else:
        yield QuadraticInterpolatedFrame(
          curr_frame,
          next_frame,
          next2,
          zoom_per_step=zoom_per_step,
          frac=frac,
        )
    # if we have a next triple, advance the frames; otherwise, we are done
    if next_pending is None:
      return  # done
    curr_frame, next_frame = next_pending


def ValidateIFrames(i_frames: int) -> None:
  """Validate the interpolation frames parameter.

  Args:
    i_frames (int): The number of interpolation frames to validate.

  Raises:
    Error: If i_frames is not between 0 and MAX_INTERPOLATION_FRAMES (inclusive).

  """
  if not (0 <= i_frames <= MAX_INTERPOLATION_FRAMES):
    raise Error(f'Interpolation must be between 0 and {MAX_INTERPOLATION_FRAMES}, got {i_frames=}')


def WriteAnimatedGIF(
  frames: abc.Iterable[bytes],
  path: pathlib.Path,
  width: int,
  height: int,
  n_frames: int,
  duration: float,
  *,
  meta: dict[str, str] | None = None,
  loop: int = 0,  # 0 == infinite loop
) -> None:
  """Write PIL Image frames to an animated GIF.

  Args:
    frames (abc.Iterable[bytes]): An iterable (or generator) of PIL Image frames to include in
        the GIF. Frames are consumed lazily one at a time, so they do not need to all fit in
        memory at once.
    path (pathlib.Path): The file path to save the GIF.
    width (int): The width of the GIF frames.
    height (int): The height of the GIF frames.
    n_frames (int): The number of frames in the GIF: has to match exactly the number of frames
        provided.
    duration (float): The duration of the GIF, in seconds.
    loop (int): The number of times to loop the GIF (0 for infinite loop). Default is 0
        (infinite loop).
    meta (dict[str, str] | None): Optional metadata to include in the GIF; default None

  Raises:
    Error: on error

  """
  # check inputs
  if not (MIN_FRAMES <= n_frames <= MAX_FRAMES):
    raise Error(f'n_frames must be between {MIN_FRAMES} and {MAX_FRAMES}, got {n_frames}')
  if not (frame.MIN_IMAGE_SIZE <= width <= frame.MAX_IMAGE_SIZE) or not (
    frame.MIN_IMAGE_SIZE <= height <= frame.MAX_IMAGE_SIZE
  ):
    raise Error(
      f'{width=} and {height=} must be between {frame.MIN_IMAGE_SIZE} and {frame.MAX_IMAGE_SIZE}'
    )
  if not (MIN_DURATION <= duration <= MAX_DURATION):
    raise Error(f'duration must be between {MIN_DURATION} and {MAX_DURATION}, got {duration}')
  if loop < 0:
    raise Error(f'loop must be >= 0, got {loop}')
  # calculate fps and check sanity of duration vs n_frames
  fps: float = n_frames / duration
  if not (MIN_FPS <= fps <= MAX_FPS):
    raise Error(f'FPS={fps:.2f} must be between {MIN_FPS:.2f} and {MAX_FPS:.2f}')
  # pull the first frame from the iterator; remaining frames are consumed lazily via a generator
  frames_iter: abc.Iterator[bytes] = iter(frames)
  try:
    first_frame: bytes = next(frames_iter)
  except StopIteration:
    raise Error('frames iterable is empty')  # noqa: B904
  frame_count: list[int] = [1]  # mutable container so the nested generator can mutate it

  def _RemainingFrames() -> abc.Iterator[PILImage.Image]:
    for frm in frames_iter:
      frame_count[0] += 1
      yield image.RGBImageFromPNG(frm)

  # save the whole GIF, normalizing each frame; PIL will iterate _RemainingFrames() lazily to save
  img0: PILImage.Image = image.RGBImageFromPNG(first_frame)
  img0.save(
    # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif
    path,
    save_all=True,
    # append without repeating the first frame, which is already saved as img0
    append_images=_RemainingFrames(),
    duration=round(1000.0 * duration / n_frames),  # duration in milliseconds per frame
    loop=loop,
    disposal=1,  # 1 == do not dispose, overwrite; more efficient b/c we don't have any transparency
    # delta-encode unchanged pixels as transparent to reduce file size
    optimize=True,  # optimize the palette and compression for smaller file size
    # GIF comment field can store arbitrary bytes, we use it to store JSON metadata
    comment=json.dumps(meta).encode('utf-8') if meta is not None else None,
  )
  # done, check that the frame count matches n_frames
  if frame_count[0] != n_frames:
    raise Error(f'frames generator produced {frame_count[0]} frames, expected {n_frames}')


def ReWriteAnimatedGIFMeta(
  old_path: pathlib.Path,
  new_path: pathlib.Path,
  meta: dict[str, str] | None,
  loop: int = 0,  # 0 == infinite loop
) -> None:
  """Read old_path GIF and re-write to new_path with the same frames and new metadata.

  We more-or-less assume the file was written with WriteAnimatedGIF().

  Args:
    old_path (pathlib.Path): The file path of the original GIF to read.
    new_path (pathlib.Path): The file path to save the modified GIF.
    meta (dict[str, str] | None): Optional metadata to include in the new GIF; default None
    loop (int): The number of times to loop the GIF (0 for infinite loop). Default is 0 which
        means infinite loop.

  Raises:
    Error: on error

  """
  # open the original GIF; keep it open so the lazy generator can seek through remaining frames
  with PILImage.open(old_path) as img:
    n_frames: int = getattr(img, 'n_frames', 1)
    if n_frames < 1:
      raise Error(f'GIF file has no frames: {old_path}')
    # read the first frame; duration is assumed uniform since WriteAnimatedGIF() uses a single value
    img.seek(0)
    first_frame: PILImage.Image = img.copy()
    frame_duration: int = int(img.info.get('duration', 100))  # ms per frame, assumed uniform

    def _RemainingFrames() -> abc.Iterator[PILImage.Image]:
      # yield frame copies one at a time so we never hold more than one extra frame in memory
      for i in range(1, n_frames):
        img.seek(i)
        yield img.copy()

    # re-save streaming frames lazily; PIL processes each frame before the generator advances
    first_frame.save(
      # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif
      new_path,
      save_all=True,
      append_images=_RemainingFrames(),
      duration=frame_duration,  # uniform per-frame duration in milliseconds
      loop=loop,
      disposal=1,  # 1 == do not dispose, overwrite
      optimize=True,
      comment=json.dumps(meta).encode('utf-8') if meta is not None else None,
    )


def WriteVideoMP4(
  frames: abc.Iterable[bytes],
  path: pathlib.Path,
  width: int,
  height: int,
  n_frames: int,
  duration: float,
  *,
  meta: dict[str, str] | None = None,
) -> None:
  """Write PIL Image frames to an MP4 video using H.264, the most broadly compatible video format.

  Args:
    frames (abc.Iterable[bytes]): An iterable (or generator) of PIL Image frames to include in
        the video. Frames are consumed lazily one at a time, so they do not need to all fit in
        memory at once.
    path (pathlib.Path): The file path to save the video.
    width (int): The width of the video frames.
    height (int): The height of the video frames.
    n_frames (int): The number of frames in the video: has to match exactly the number of frames
        provided.
    duration (float): The duration of the video, in seconds.
    meta (dict[str, str] | None): Optional metadata to include in the video; default None

  Raises:
    Error: on error

  """
  # check inputs
  if not (MIN_FRAMES <= n_frames <= MAX_FRAMES):
    raise Error(f'n_frames must be between {MIN_FRAMES} and {MAX_FRAMES}, got {n_frames}')
  if not (frame.MIN_IMAGE_SIZE <= width <= frame.MAX_IMAGE_SIZE) or not (
    frame.MIN_IMAGE_SIZE <= height <= frame.MAX_IMAGE_SIZE
  ):
    raise Error(
      f'{width=} and {height=} must be between {frame.MIN_IMAGE_SIZE} and {frame.MAX_IMAGE_SIZE}'
    )
  if not (MIN_DURATION <= duration <= MAX_DURATION):
    raise Error(f'duration must be between {MIN_DURATION} and {MAX_DURATION}, got {duration}')
  # calculate fps and check sanity of duration vs n_frames
  fps: float = n_frames / duration
  if not (MIN_FPS <= fps <= MAX_FPS):
    raise Error(f'FPS={fps:.2f} must be between {MIN_FPS:.2f} and {MAX_FPS:.2f}')
  # prepare metadata
  output_params: list[str] = []
  output_params.extend(['-movflags', '+faststart'])  # allows start playing before fully downloaded
  output_params.extend(['-crf', '16'])  # good quality, lower is better
  output_params.extend(['-preset', 'slow'])  # slower presets give better compression
  if meta:
    # store all metadata as a single JSON string in the 'comment' field so it can be read back;
    # ffmpeg -metadata key=value stores to format.tags which imageio doesn't expose on read
    output_params.extend(['-metadata', f'comment={json.dumps(meta)}'])
  # save the whole MP4, normalizing each frame
  frame_count = 0
  with imageio.get_writer(  # pyright: ignore[reportUnknownMemberType]
    path,
    fps=fps,
    format='ffmpeg',  # type: ignore[arg-type]
    codec='libx264',
    pixelformat='yuv420p',
    macro_block_size=1,
    output_params=output_params,
  ) as writer:
    for frm in frames:
      writer.append_data(np.asarray(image.RGBImageFromPNG(frm)))  # type: ignore[attr-defined]
      frame_count += 1
  # done, check that the frame count matches n_frames
  if frame_count != n_frames:
    raise Error(f'frames generator produced {frame_count} frames, expected {n_frames}')


def ReWriteVideoMP4Meta(
  old_path: pathlib.Path, new_path: pathlib.Path, meta: dict[str, str] | None
) -> None:
  """Read old_path MP4 and re-write to new_path with the same frames and new metadata.

  We more-or-less assume the file was written with WriteVideoMP4().

  Args:
    old_path (pathlib.Path): The file path of the original MP4 to read.
    new_path (pathlib.Path): The file path to save the modified MP4.
    meta (dict[str, str] | None): Optional metadata to include in the new MP4; default None

  """
  # open the original MP4 and read the fps from its metadata
  reader = imageio.get_reader(old_path, format='ffmpeg')  # type: ignore[arg-type]
  fps: float = float(reader.get_meta_data().get('fps', 25.0))
  # prepare metadata output params, same settings as WriteVideoMP4
  output_params: list[str] = []
  output_params.extend(['-movflags', '+faststart'])  # allows start playing before fully downloaded
  output_params.extend(['-crf', '16'])  # good quality, lower is better
  output_params.extend(['-preset', 'slow'])  # slower presets give better compression
  if meta:
    # store all metadata as a single JSON string in the 'comment' field (mirrors WriteVideoMP4)
    output_params.extend(['-metadata', f'comment={json.dumps(meta)}'])
  # stream frames from reader directly into writer (no full in-memory buffering)
  with imageio.get_writer(  # pyright: ignore[reportUnknownMemberType]
    new_path,
    fps=fps,
    format='ffmpeg',  # type: ignore[arg-type]
    codec='libx264',
    pixelformat='yuv420p',
    macro_block_size=1,
    output_params=output_params,
  ) as writer:
    for frm in reader:  # type: ignore[attr-defined]
      writer.append_data(frm)  # type: ignore[attr-defined]
  reader.close()
