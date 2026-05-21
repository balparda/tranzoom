# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Mandelbrot zoom search with AI command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import dataclasses
import math
import pathlib
from typing import cast

import click
import gmpy2
import typer
from transcrypto.cli import clibase
from transcrypto.core import hashes
from transcrypto.utils import human, timer

from tranzoom import tranz
from tranzoom.cli import base
from tranzoom.core import ai, frame, image

_MANUAL_QUERY_WEIGHT: float = 0.8  # how much to weight the manual query vs the fractal score
_MAX_TOLERATED_MAG_ERROR: float = 0.02  # 2%


zoom_app = typer.Typer(
  no_args_is_help=True,
  help=(
    'Examples:\n\n\n\n'
    '# --- LLM-Guided Fractal Zoom ---\n'
    'poetry run tranz zoom ai\n'
    'poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 zoom -n 10 ai '
    '" -0.7436499" "0.13188204" "0.00073801"\n'
    'poetry run tranz --iterm zoom ai "/path/to/image.png"\n'
    'poetry run tranz --iterm zoom -s 700 --fractal julia ai\n\n'
    '# --- Human/Manual-Guided Fractal Zoom ---\n'
    'poetry run tranz --iterm zoom manual " -0.74303" "0.126433" "0.01611"\n'
    'poetry run tranz zoom manual "/path/to/image.png"\n'
    'poetry run tranz --iterm zoom -s 700 --fractal julia manual\n\n'
    '# --- Auto Fractal Zoom: Make Video ---\n'
    'poetry run tranz zoom -s 256 auto --fps 10 --duration 2\n'
    'poetry run tranz zoom auto " -5578776469/7500000000" "8244620127/62500000000" '
    '"0.00073801" "0.00073801" "2.1" --fps 10 --duration 15'
  ),
)
tranz.app.add_typer(zoom_app, name='zoom')


@zoom_app.callback(invoke_without_command=True)
@clibase.CLIErrorGuard
def ZoomOptions(  # documentation is in help/epilog  # noqa: D103
  *,
  ctx: click.Context,
  # note that these are the zoom image options, with default of 512x512
  fractal_type: frame.Fractal = base.FRACTAL_TYPE_OPTION,  # type: ignore[assignment]
  img_width: int = base.IMAGE_ZOOM_WIDTH_OPTION,  # type: ignore[assignment]
  img_height: int = base.IMAGE_ZOOM_HEIGHT_OPTION,  # type: ignore[assignment]
  img_size: int | None = base.IMAGE_SIZE_OPTION,  # type: ignore[assignment]
  max_steps: int = base.MAX_STEPS_OPTION,  # type: ignore[assignment]
  julia_re: str = base.JULIA_RE_OPTION,  # type: ignore[assignment]
  julia_im: str = base.JULIA_IM_OPTION,  # type: ignore[assignment]
) -> None:
  # store this command's options in the shared config so all sub-commands can read it
  if ctx.invoked_subcommand is not None and ctx.obj is not None:
    ctx.obj = dataclasses.replace(
      ctx.obj,
      fractal_type=fractal_type,
      img_width=img_width,
      img_height=img_height,
      img_size=img_size,
      max_steps=max_steps,
      julia_re=julia_re,
      julia_im=julia_im,
    )


@zoom_app.command(
  'ai',
  help='Use AI to search for an interest point.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run tranz zoom ai\n\n'
    '<start with full set and zoom in using model Qwen 32>\n\n\n\n'
    '$ poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 '
    'zoom -n 10 ai " -0.7436499" "0.13188204" "0.00073801"\n\n'
    '<zoom in using model Qwen 32 with higher temperature 0.7, '
    'start from "Seahorse Tail", stop after 10 steps>\n\n\n\n'
    '$ poetry run tranz --iterm zoom ai "/path/to/image.png"\n\n'
    '<gets the same frame used in "/path/to/image.png" and starts zoom there, '
    'print iTerm2 images>\n\n\n\n'
    '$ poetry run tranz --iterm zoom -s 700 --fractal julia ai\n\n'
    '<start with full default Julia Set and AI zoom with 700px size, print iTerm2 images>'
  ),
)
@clibase.CLIErrorGuard
def AI(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_ARGUMENT,  # type: ignore[assignment]
  query: str | None = base.AI_QUERY_OPTION,  # type: ignore[assignment]
  reason: bool = base.AI_OUTPUT_REASON_FIELD_OPTION,  # type: ignore[assignment]
  memory: int = base.MAX_CHAT_MEMORY_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: base.TranZoomConfig = ctx.obj
  frm: frame.Frame = base.MakeFrameFromCLIArgs(
    config.fractal_type, center_re, center_im, f_width, f_height, config.console.print
  )
  # if it is a Julia, make the Julia point and add it to the frame
  frm = (
    frame.FrameAndPoint.FromCenterAndPoint(
      frame.Fractal.JULIA,
      *base.MakePointFromCLIArgs(config.julia_re, config.julia_im, config.console.print),
      frm.center[0],
      frm.center[1],
      frm.size[0],
      frm.size[1],
    )
    if config.fractal_type == frame.Fractal.JULIA
    else frm
  )
  # determine width and height
  width: int
  height: int
  width, height = (
    frm.PixelDimensionsFromSize(config.img_size)
    if config.img_size
    else (config.img_width, config.img_height)
  )
  # we have a valid frame, let's start the AI search loop
  ai.ZoomLoop(
    frm,
    width,
    height,
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix or base.DEFAULT_IMAGE_PREFIX[frm.fractal],
    config.pal,
    config.set_pal,
    config.set_points,
    config.max_threads,
    config.model,
    config.spec_tokens,
    config.seed,
    config.context,
    config.temperature,
    config.gpu,
    config.gpu_layers,
    config.fp16,
    config.use_mmap,
    config.flash,
    config.kv_cache,
    config.timeout,
    query.strip() if query else None,
    reason,
    memory,
    config.max_steps,
    config.iterm,
    _MANUAL_QUERY_WEIGHT,
    config.console.print,
  )


@zoom_app.command(
  'manual',
  help='Manually navigate a Mandelbrot zoom search (no AI).',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run tranz zoom manual\n\n'
    '<start with full set and zoom in manually>\n\n\n\n'
    '$ poetry run tranz --iterm zoom manual " -0.7436499" "0.13188204" "0.00073801"\n\n'
    '<zoom in manually, start from "Seahorse Tail", print iTerm2 images>\n\n\n\n'
    '$ poetry run tranz zoom manual "/path/to/image.png"\n\n'
    '<gets the same frame used in "/path/to/image.png" and starts zoom there>\n\n\n\n'
    '$ poetry run tranz --iterm zoom -s 700 --fractal julia manual\n\n'
    '<start with full default Julia Set and manual zoom with 700px size, print iTerm2 images>'
  ),
)
@clibase.CLIErrorGuard
def Manual(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_ARGUMENT,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: base.TranZoomConfig = ctx.obj
  frm: frame.Frame = base.MakeFrameFromCLIArgs(
    config.fractal_type, center_re, center_im, f_width, f_height, config.console.print
  )
  # if it is a Julia, make the Julia point and add it to the frame
  frm = (
    frame.FrameAndPoint.FromCenterAndPoint(
      frame.Fractal.JULIA,
      *base.MakePointFromCLIArgs(config.julia_re, config.julia_im, config.console.print),
      frm.center[0],
      frm.center[1],
      frm.size[0],
      frm.size[1],
    )
    if config.fractal_type == frame.Fractal.JULIA
    else frm
  )
  # determine width and height
  width: int
  height: int
  width, height = (
    frm.PixelDimensionsFromSize(config.img_size)
    if config.img_size
    else (config.img_width, config.img_height)
  )
  # we have a valid frame, let's start the AI search loop
  ai.ManualLoop(
    frm,
    width,
    height,
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix or base.DEFAULT_IMAGE_PREFIX[frm.fractal],
    config.pal,
    config.set_pal,
    config.set_points,
    config.max_threads,
    config.max_steps,
    config.iterm,
    config.console.print,
  )


@zoom_app.command(
  'auto',
  help='Create a GIF/MP4 zoom fractal animation.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run tranz zoom -s 256 auto --fps 10 --duration 2\n\n'
    'Producing 256x256 10^1.00 zoom animation, 2.000 s long, at 10.00 FPS, '
    'with 20 frames, 112.88% per step...\n\n\n\n'
    '$ poetry run tranz zoom auto " -5578776469/7500000000" "8244620127/62500000000" '
    '"0.00073801" "0.00073801" "2.1" --fps 10 --duration 15\n\n'
    'Producing 512x512 10^2.10 zoom animation, 15.000 s long, at 10.00 FPS, '
    'with 150 frames, 103.30% per step...'
  ),
)
@clibase.CLIErrorGuard
def Auto(  # documentation is help/epilog/args  # noqa: C901, D103, PLR0912, PLR0914, PLR0915
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_ARGUMENT,  # type: ignore[assignment]
  dest_magnification_10: float = base.ANIM_DEST_MAGNIFICATION_ARGUMENT,  # type: ignore[assignment]
  anim_type: image.AnimationType = base.ANIM_TYPE_OPTION,  # type: ignore[assignment]
  duration: float | None = base.ANIM_DURATION_OPTION,  # type: ignore[assignment]
  frames: int | None = base.ANIM_FRAMES_OPTION,  # type: ignore[assignment]
  fps: float | None = base.ANIM_FPS_OPTION,  # type: ignore[assignment]
  loop: int = base.ANIM_LOOP_OPTION,  # type: ignore[assignment]
  max_iter: int | None = base.MAX_ITERATIONS_OPTION,  # type: ignore[assignment]
  mark_coords: str | None = base.MARK_COORDINATES_OPTION,  # type: ignore[assignment]
  mark_color: str = base.MARK_COLOR_OPTION,  # type: ignore[assignment]
  mark_width: int = base.MARK_WIDTH_OPTION,  # type: ignore[assignment]
  save_frames: bool = base.ANIM_SAVE_FRAMES_OPTION,  # type: ignore[assignment]
) -> None:
  # we intend passing config, so we add the options here...
  # check color so it won't raise plain KeyError
  col: str = mark_color.strip().upper()
  if col not in image.Color.__members__:
    raise click.ClickException(
      f'Invalid mark color {mark_color!r}; available colors: '
      + ', '.join(sorted(repr(c.name.lower()) for c in image.Color))
    )
  ctx.obj = dataclasses.replace(
    ctx.obj,
    max_iter=max_iter,
    mark_coords=mark_coords,
    mark_color=image.Color[col],
    mark_width=mark_width,
  )
  config: base.TranZoomConfig = ctx.obj
  timestamp: int = timer.Now()
  # check sanity, create frame, and print info about the image we're going to generate
  if duration and frames and not fps:
    fps = frames / duration
  elif duration and fps and not frames:
    frames = int(duration * fps)
  elif frames and fps and not duration:
    duration = frames / fps
  else:
    raise click.ClickException(
      'Please provide exactly 2 of the 3 options: `--duration`, `--frames` and `--fps`; '
      f'got {duration=}, {frames=} and {fps=}'
    )
  if not (image.MIN_FPS <= fps <= image.MAX_FPS):
    raise click.ClickException(
      f'FPS={fps:.2f} must be between {image.MIN_FPS:.2f} and {image.MAX_FPS:.2f}'
    )
  if not (image.MIN_FRAMES <= frames <= image.MAX_FRAMES):
    raise click.ClickException(
      f'Frames={frames} must be between {image.MIN_FRAMES} and {image.MAX_FRAMES}'
    )
  if not (image.MIN_DURATION <= duration <= image.MAX_DURATION):
    raise click.ClickException(
      f'Duration={duration:.2f} must be between {image.MIN_DURATION:.2f} and '
      f'{image.MAX_DURATION:.2f} seconds'
    )
  frm: frame.Frame = base.MakeFrameFromCLIArgs(
    config.fractal_type, center_re, center_im, f_width, f_height, config.console.print
  )
  # if it is a Julia, make the Julia point and add it to the frame
  frm = (
    frame.FrameAndPoint.FromCenterAndPoint(
      frame.Fractal.JULIA,
      *base.MakePointFromCLIArgs(config.julia_re, config.julia_im, config.console.print),
      frm.center[0],
      frm.center[1],
      frm.size[0],
      frm.size[1],
    )
    if config.fractal_type == frame.Fractal.JULIA
    else frm
  )
  original_frm: frame.Frame = frm
  # determine width and height
  width: int
  height: int
  width, height = (
    frm.PixelDimensionsFromSize(config.img_size)
    if config.img_size
    else (config.img_width, config.img_height)
  )
  # compute zoom constants; log
  steps: int = frames - 1
  mag_per_step: float = dest_magnification_10 / steps
  scalar_magnification: gmpy2.mpfr = gmpy2.exp10(dest_magnification_10)
  scalar_magnification_per_step: float = math.pow(10.0, mag_per_step)
  mpq_mag: gmpy2.mpq = frame.MPQFromFloatApprox(scalar_magnification_per_step, 100_000)
  # reproduce the zoom run to check the actual magnification we will get
  for _ in range(frames - 1):
    frm = frame.Frame.FromCenter(
      frm.fractal,
      frm.center[0],
      frm.center[1],
      frm.size[0] / mpq_mag,
      frm.size[1] / mpq_mag,
    )
  # now we can compute the actual final magnification
  actual_mag: gmpy2.mpfr = cast('gmpy2.mpfr', gmpy2.sqrt(original_frm.area / frm.area))
  mag_error: gmpy2.mpfr = abs(actual_mag - scalar_magnification) / scalar_magnification
  frm = original_frm  # reset frm to the original for the actual rendering loop
  # log; log errors
  config.console.print(
    f'\nProducing {width}x{height} 10^{dest_magnification_10:.2f} zoom animation, '
    f'{human.HumanizedSeconds(duration)} long, at {fps:.2f} FPS, '
    f'with {frames} frames, {100.0 * scalar_magnification_per_step:.2f}% per step ({mpq_mag}), '
    f'final magnification error {float(gmpy2.mpfr(100.0) * mag_error):.4f}%...\n'
  )
  if scalar_magnification_per_step >= image.THRESHOLD_JUMPY_ZOOM_PER_FRAME:
    config.console.print(
      '[red]Warning: the zoom per frame is high: 10**(mag/(frames-1)) = '
      f'10**({dest_magnification_10:.2f}/{steps}) = '
      f'{100.0 * scalar_magnification_per_step:.2f}%/step. '
      'The resulting animation may look jumpy. Consider increasing the number of frames '
      'or reducing the total magnification.[/]\n'
    )
  if mag_error > _MAX_TOLERATED_MAG_ERROR:
    config.console.print(
      f'[red]Warning: the actual magnification achieved by zooming in the frame is '
      f'{float(actual_mag):.2f}, which is {float(gmpy2.mpfr(100.0) * mag_error):.4f}% different '
      f'from the intended {scalar_magnification:.2f}. This means the gmpy2.mpq needs more '
      'precision for conversion. This is a bug! The final animation may not have the exact '
      'intended zoom level.[/]\n'
    )
  # main zoom loop, go for frames iterations, producing the image and then zooming in the frame
  img: image.Image | None = None
  img_data: bytes
  data_hash: str
  all_frames: list[bytes] = []
  all_hash: list[str] = []
  with timer.Timer(emit_log=False) as tmr:
    for i in range(frames):
      config.console.print(f'[yellow]Frame {i + 1} / {frames}[/]')
      # we have the frame, now feed it to the producer
      img, img_data, data_hash = base.ProduceFractalImage(
        frm, config, tm=timestamp, add_serial=i + 1, save_image=save_frames
      )
      all_frames.append(img_data)
      all_hash.append(data_hash)
      # zoom in the frame for the next iteration
      frm = (
        frame.FrameAndPoint.FromCenterAndPoint(
          frm.fractal,
          frm.point_re,
          frm.point_im,
          frm.center[0],
          frm.center[1],
          frm.size[0] / mpq_mag,
          frm.size[1] / mpq_mag,
        )
        if isinstance(frm, frame.FrameAndPoint) and frm.fractal == frame.Fractal.JULIA
        else frame.Frame.FromCenter(
          frm.fractal,
          frm.center[0],
          frm.center[1],
          frm.size[0] / mpq_mag,
          frm.size[1] / mpq_mag,
        )
      )
    # check we got something
    if not img:
      raise click.ClickException('No image produced for animation! should never happen; report bug')
  # compute hash and so the path
  video_hash: str = hashes.Hash256(
    ('|'.join(all_hash)).encode('ascii')  # stable if all images are the same
  ).hex()
  video_path: pathlib.Path = image.MakeImagePath(
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix or base.DEFAULT_IMAGE_PREFIX[frm.fractal],
    video_hash,
    tm=timestamp,
    suffix=anim_type.value,
  )
  # create metadata
  meta: dict[str, str] = image.MakeImageMeta(
    img,
    video_hash,
    pal=config.pal,
    set_pal=config.set_pal,
    set_points=config.set_points,
  )
  # add video-specific metadata
  meta[image.META_IMAGE_ANIMATION_KEY] = anim_type.value.lower()
  meta.update(
    # the extra animation keys
    {
      image.META_ANIM_INITIAL_WIDTH_RE_KEY: str(original_frm.size[0]),
      image.META_ANIM_INITIAL_HEIGHT_IM_KEY: str(original_frm.size[1]),
      image.META_ANIM_MAGNITUDE_KEY: str(dest_magnification_10),
      image.META_ANIM_MAGNITUDE_PER_STEP_KEY: str(mag_per_step),
      image.META_ANIM_MAGNIFICATION_PER_STEP_KEY: str(scalar_magnification_per_step),
      image.META_ANIM_MAGNIFICATION_PER_STEP_MPQ_KEY: str(mpq_mag),
      image.META_ANIM_DURATION_KEY: str(duration),
      image.META_ANIM_FRAMES_KEY: str(frames),
      image.META_ANIM_STEPS_KEY: str(steps),
      image.META_ANIM_FPS_KEY: str(fps),
      image.META_ANIM_LOOP_KEY: str(loop),
    }
  )
  # save the final animation
  if anim_type == image.AnimationType.GIF:
    image.WriteAnimatedGIF(
      all_frames, video_path, width, height, frames, duration, meta=meta, loop=loop
    )
  elif anim_type == image.AnimationType.MP4:
    image.WriteVideoMP4(all_frames, video_path, width, height, frames, duration, meta=meta)
  else:
    raise click.ClickException(f'Unsupported animation type: {anim_type}')
  # done
  config.console.print(f'\nSuccess: {anim_type.value.upper()} {video_hash!r} in {tmr}')
  config.console.print(f'Saved {anim_type.value.upper()} to "{video_path}"\n')
  # iterm
  if config.iterm and anim_type != image.AnimationType.MP4:  # iTerm2 does not support MP4, only GIF
    image.PrintITerm2(video_path.read_bytes())
    config.console.print()
