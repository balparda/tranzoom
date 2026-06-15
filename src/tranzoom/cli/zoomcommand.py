# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Fractal zoom search with AI command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import dataclasses
import pathlib

import gmpy2
import typer
import typer._click.core
from transcrypto.cli import clibase
from transcrypto.utils import human

from tranzoom import tranz
from tranzoom.cli import base
from tranzoom.core import ai, frame, image, pixels, zoom

_AI_QUERY_WEIGHT: float = 0.8  # how much to weight the AI query vs the manual score


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
  ctx: typer._click.core.Context,
  # note that these are the zoom image options, with default of 512x512
  fractal_type: frame.Fractal = base.FRACTAL_TYPE_OPTION,  # type: ignore[assignment]
  img_width: int = base.IMAGE_ZOOM_WIDTH_OPTION,  # type: ignore[assignment]
  img_height: int = base.IMAGE_ZOOM_HEIGHT_OPTION,  # type: ignore[assignment]
  img_size: int | None = base.IMAGE_SIZE_OPTION,  # type: ignore[assignment]
  i_pixels: int = base.IMAGE_INTERPOLATION_PIXELS_OPTION,  # type: ignore[assignment]
  max_steps: int = base.MAX_STEPS_OPTION,  # type: ignore[assignment]
  julia_re: str = base.JULIA_RE_OPTION,  # type: ignore[assignment]
  julia_im: str = base.JULIA_IM_OPTION,  # type: ignore[assignment]
  mark_coords: str | None = base.MARK_COORDINATES_OPTION,  # type: ignore[assignment]
  mark_color: str = base.MARK_COLOR_OPTION,  # type: ignore[assignment]
  mark_width: int = base.MARK_WIDTH_OPTION,  # type: ignore[assignment]
) -> None:
  # store this command's options in the shared config so all sub-commands can read it
  if ctx.invoked_subcommand is not None and ctx.obj is not None:
    # check color so it won't raise plain KeyError
    col: str = mark_color.strip().upper()
    if col not in pixels.Color.__members__:
      raise base.UsageError(
        f'Invalid mark color {mark_color!r}; available colors: '
        + ', '.join(sorted(repr(c.name.lower()) for c in pixels.Color))
      )
    ctx.obj = dataclasses.replace(
      ctx.obj,
      fractal_type=fractal_type,
      img_width=img_width,
      img_height=img_height,
      img_size=img_size,
      i_pixels=i_pixels,
      max_steps=max_steps,
      julia_re=julia_re,
      julia_im=julia_im,
      mark_coords=mark_coords,
      mark_color=pixels.Color[col],
      mark_width=mark_width,
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
  ctx: typer._click.core.Context,
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
  frm: frame.Frame = base.MakeFrameFromConfig(config, center_re, center_im, f_width, f_height)
  params: frame.ComputationParameters = base.MakeComputationParameters(frm, config)
  render: pixels.RenderParameters
  out: image.ImageOutputConfig
  render, out = base.MakeRenderParameters(params, config)
  # call the main zoom loop
  with config.OpenDB() as db:
    ai.ZoomLoop(
      db,
      params,
      render,
      out,
      max_threads=config.max_threads,
      model=config.model,
      optimization=config.python_optimization,
      spec_tokens=config.spec_tokens,
      seed=config.seed,
      context=config.context,
      temperature=config.temperature,
      gpu=config.gpu,
      gpu_layers=config.gpu_layers,
      fp16=config.fp16,
      use_mmap=config.use_mmap,
      flash=config.flash,
      kv_cache=config.kv_cache,
      timeout=config.timeout,
      query=query.strip() if query else None,
      reason=reason,
      memory=memory,
      max_steps=config.max_steps,
      iterm=config.iterm,
      target_weight=_AI_QUERY_WEIGHT,
      print_comm=config.console.print,
      force=config.img_force_redo,
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
  ctx: typer._click.core.Context,
  center_re: str = base.FRAME_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_ARGUMENT,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: base.TranZoomConfig = ctx.obj
  frm: frame.Frame = base.MakeFrameFromConfig(config, center_re, center_im, f_width, f_height)
  params: frame.ComputationParameters = base.MakeComputationParameters(frm, config)
  render: pixels.RenderParameters
  out: image.ImageOutputConfig
  render, out = base.MakeRenderParameters(params, config)
  # call the main zoom loop
  with config.OpenDB() as db:
    ai.ZoomLoop(
      db,
      params,
      render,
      out,
      max_threads=config.max_threads,
      optimization=config.python_optimization,
      max_steps=config.max_steps,
      iterm=config.iterm,
      print_comm=config.console.print,
      manual=True,
      force=config.img_force_redo,
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
def Auto(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: typer._click.core.Context,
  center_re: str = base.FRAME_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_ARGUMENT,  # type: ignore[assignment]
  dest_magnification_10: str = base.ANIM_DEST_MAGNIFICATION_ARGUMENT,  # type: ignore[assignment]
  anim_type: zoom.AnimationType = base.ANIM_TYPE_OPTION,  # type: ignore[assignment]
  duration: float | None = base.ANIM_DURATION_OPTION,  # type: ignore[assignment]
  frames: int | None = base.ANIM_FRAMES_OPTION,  # type: ignore[assignment]
  fps: float | None = base.ANIM_FPS_OPTION,  # type: ignore[assignment]
  i_frames: int = base.ANIM_INTERPOLATION_FRAMES_OPTION,  # type: ignore[assignment]
  loop: int = base.ANIM_LOOP_OPTION,  # type: ignore[assignment]
  save_frames: bool = base.ANIM_SAVE_FRAMES_OPTION,  # type: ignore[assignment]
) -> None:
  # we intend passing config, so we add the options here...
  config: base.TranZoomConfig = ctx.obj
  # make basic video params conversion; will be validated later in ZoomParameters
  if duration and frames and not fps:
    pass  # no need, we prefer to have duration and frames anyway...
  elif duration and fps and not frames:
    frames = int(duration * fps)
  elif frames and fps and not duration:
    duration = frames / fps
  else:
    raise base.UsageError(
      'Please provide exactly 2 of the 3 options: `--duration`, `--frames` and `--fps`; '
      f'got {duration=}, {frames=} and {fps=}'
    )
  # build parameters
  frm: frame.Frame = base.MakeFrameFromConfig(config, center_re, center_im, f_width, f_height)
  params: frame.ComputationParameters = base.MakeComputationParameters(frm, config)
  render: pixels.RenderParameters
  out: image.ImageOutputConfig
  render, out = base.MakeRenderParameters(params, config)
  zoom_params: zoom.ZoomParameters = zoom.ZoomParameters(
    tp=anim_type,
    img=params,  # zoom is created with the sentinel value (if on AUTO) and does NOT update!
    render=render,  # notice this render does not have prev/next markers!
    mag=gmpy2.mpq(dest_magnification_10),
    n_frames=frames,
    duration=round(duration * zoom.VIDEO_DURATION_STORE_SCALE),
    i_frames=i_frames,
    loop=loop,
  )
  # call
  img_p: pathlib.Path
  img_sz: int
  img_p, img_sz = base.ProduceFractalAnimation(config, out, zoom_params, save_frames)
  # log
  config.console.print(
    f'Saved {zoom_params.tp.value.upper()} to {str(img_p)!r}, {human.HumanizedBytes(img_sz)}\n'
  )
  # iterm
  if config.iterm and zoom_params.tp != zoom.AnimationType.MP4:  # iTerm2 does not support MP4
    pixels.PrintITerm2(img_p.read_bytes())
    config.console.print()
