# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Fractal zoom search with AI command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import dataclasses
import pathlib

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

# gmpy2.mpq constants
_MPQ_ZERO: gmpy2.mpq = gmpy2.mpq('0')


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
  mark_coords: str | None = base.MARK_COORDINATES_OPTION,  # type: ignore[assignment]
  mark_color: str = base.MARK_COLOR_OPTION,  # type: ignore[assignment]
  mark_width: int = base.MARK_WIDTH_OPTION,  # type: ignore[assignment]
) -> None:
  # store this command's options in the shared config so all sub-commands can read it
  if ctx.invoked_subcommand is not None and ctx.obj is not None:
    # check color so it won't raise plain KeyError
    col: str = mark_color.strip().upper()
    if col not in image.Color.__members__:
      raise base.UsageError(
        f'Invalid mark color {mark_color!r}; available colors: '
        + ', '.join(sorted(repr(c.name.lower()) for c in image.Color))
      )
    ctx.obj = dataclasses.replace(
      ctx.obj,
      fractal_type=fractal_type,
      img_width=img_width,
      img_height=img_height,
      img_size=img_size,
      max_steps=max_steps,
      julia_re=julia_re,
      julia_im=julia_im,
      mark_coords=mark_coords,
      mark_color=image.Color[col],
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
  frm: frame.Frame = base.MakeFrameFromConfig(config, center_re, center_im, f_width, f_height)
  params: frame.ComputationParameters = base.MakeComputationParameters(frm, config)
  render: image.RenderParameters
  out: image.ImageOutputConfig
  render, out = base.MakeRenderParameters(params, config)
  # call the main zoom loop
  with config.OpenDB() as db:
    ai.ZoomLoop(
      db,
      params,
      render,
      out,
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
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_ARGUMENT,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: base.TranZoomConfig = ctx.obj
  frm: frame.Frame = base.MakeFrameFromConfig(config, center_re, center_im, f_width, f_height)
  params: frame.ComputationParameters = base.MakeComputationParameters(frm, config)
  render: image.RenderParameters
  out: image.ImageOutputConfig
  render, out = base.MakeRenderParameters(params, config)
  # call the main zoom loop
  with config.OpenDB() as db:
    ai.ZoomLoop(
      db,
      params,
      render,
      out,
      config.max_threads,
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
def Auto(  # documentation is help/epilog/args  # noqa: C901, D103, PLR0912, PLR0914, PLR0915
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_ARGUMENT,  # type: ignore[assignment]
  dest_magnification_10: str = base.ANIM_DEST_MAGNIFICATION_ARGUMENT,  # type: ignore[assignment]
  anim_type: image.AnimationType = base.ANIM_TYPE_OPTION,  # type: ignore[assignment]
  duration: float | None = base.ANIM_DURATION_OPTION,  # type: ignore[assignment]
  frames: int | None = base.ANIM_FRAMES_OPTION,  # type: ignore[assignment]
  fps: float | None = base.ANIM_FPS_OPTION,  # type: ignore[assignment]
  loop: int = base.ANIM_LOOP_OPTION,  # type: ignore[assignment]
  max_iter: int | None = base.MAX_ITERATIONS_OPTION,  # type: ignore[assignment]
  save_frames: bool = base.ANIM_SAVE_FRAMES_OPTION,  # type: ignore[assignment]
) -> None:
  # we intend passing config, so we add the options here...
  ctx.obj = dataclasses.replace(ctx.obj, max_iter=max_iter)
  config: base.TranZoomConfig = ctx.obj
  timestamp: int = timer.Now()
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
  render: image.RenderParameters
  out: image.ImageOutputConfig
  render, out = base.MakeRenderParameters(params, config)
  zoom_params: image.ZoomParameters = image.ZoomParameters(
    tp=anim_type,
    img=params,
    render=render,
    mag=gmpy2.mpq(dest_magnification_10),
    n_frames=frames,
    duration=round(duration * image.VIDEO_DURATION_STORE_SCALE),
    loop=loop,
  )
  all_frames: list[frame.Frame] = zoom_params.Frames()  # last thing that gould go boom!
  # we should be good to go, all options check out; log and warn if needed
  config.console.print(
    f'\n{params.width}x{params.height} {render.escaped_pal.value!r} '
    f'{frm.fractal.value.capitalize()!r} [magenta]10^{float(zoom_params.mag):.4f} magnitude ZOOM[/]'
  )
  config.console.print(f'{zoom_params} ... {all_frames[-1]}')
  config.console.print(
    f'{human.HumanizedSeconds(duration)} long, at {fps:.2f} FPS, with {frames} frames, '
    f'{100.0 * float(zoom_params.scalar_magnification_per_step):.4f}%/step...\n'
  )
  if zoom_params.scalar_magnification_per_step > image.THRESHOLD_JUMPY_ZOOM_PER_FRAME:
    config.console.print(
      '[red]Warning: the zoom per frame is high: 10^(mag/(frames-1)) = '
      f'10^({float(zoom_params.mag):.4f}/{zoom_params.n_steps}) = '
      f'{100.0 * float(zoom_params.scalar_magnification_per_step):.4f}%/step. '
      'The resulting animation may look jumpy! Please consider increasing the number of frames '
      'or reducing the total magnification.[/]\n'
    )
  # DB
  tm: int = timer.Now()
  with config.OpenDB() as db:
    # main zoom loop, go for frames iterations, producing the image and then zooming in the frame
    img: image.Image | None = None
    img_path: pathlib.Path | None = None
    img_data: bytes
    data_hash: str
    all_img_bytes: list[bytes] = []
    all_hash: list[str] = []
    with timer.Timer(emit_log=False) as tmr:
      for i, frm in enumerate(all_frames):
        config.console.print(f'[yellow]Frame {i + 1} / {frames}[/]')
        # we have the frame, now feed it to the producer
        params, img, img_data, data_hash, img_path = db.CoreComputeImage(
          dataclasses.replace(params, frm=frm, depth=frame.MIN_ITER),  # send frm, mark as sentinel
          render,
          out,
          add_serial=i + 1,
          tm=tm,
          max_threads=config.max_threads,
          iterm=config.iterm,
          print_comm=config.console.print,
          require_img_obj=True,
          force=config.img_force_redo,
        )
        # check we got something
        if not img or not img_path:
          raise base.Error('No image produced for frame! should never happen; report bug')
        # save the image to disk if requested
        if save_frames:
          img_path.write_bytes(img_data)
          config.console.print(f'Saved to "{img_path}"\n')
        all_img_bytes.append(img_data)
        all_hash.append(data_hash)
      # check we got something; also appease type checker
      if not img:
        raise base.Error('No image produced for animation! should never happen; report bug')
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
    meta: dict[str, str] = image.MakeImageMeta(img, render, video_hash)  # using LAST FRAME!
    # add video-specific metadata
    meta[image.META_IMAGE_ANIMATION_KEY] = anim_type.value.lower()
    meta.update(
      # the extra animation keys
      {
        image.META_ZOOM_TYPE_KEY: zoom_params.tp.value,
        image.META_ZOOM_INITIAL_WIDTH_RE_KEY: str(all_frames[0].size[0]),
        image.META_ZOOM_INITIAL_HEIGHT_IM_KEY: str(all_frames[0].size[1]),
        image.META_ZOOM_MAGNITUDE_KEY: str(zoom_params.mag),
        image.META_ZOOM_FRAMES_KEY: str(zoom_params.n_frames),
        image.META_ZOOM_SECONDS_KEY: str(zoom_params.n_seconds),
        image.META_ZOOM_LOOP_KEY: str(zoom_params.loop),
        image.META_ZOOM_STEPS_KEY: str(zoom_params.n_steps),
        image.META_ZOOM_FPS_KEY: str(zoom_params.fps),
        image.META_ZOOM_MAGNITUDE_PER_STEP_KEY: str(zoom_params.mag_per_step),
        image.META_ZOOM_MAGNIFICATION_PER_STEP_KEY: str(zoom_params.scalar_magnification_per_step),
      }
    )
    # save the final animation
    if anim_type == image.AnimationType.GIF:
      image.WriteAnimatedGIF(
        all_img_bytes,
        video_path,
        zoom_params.img.width,
        zoom_params.img.height,
        frames,
        duration,
        meta=meta,
        loop=loop,
      )
    elif anim_type == image.AnimationType.MP4:
      image.WriteVideoMP4(
        all_img_bytes,
        video_path,
        zoom_params.img.width,
        zoom_params.img.height,
        frames,
        duration,
        meta=meta,
      )
    else:
      raise base.UsageError(f'Unsupported animation type: {anim_type}')
    # add to DB
    # db.AddZoomToDB(zoom, zoom_data)
    # done
    config.console.print(f'Success: {anim_type.value.upper()} {video_hash!r} in {tmr}')
    config.console.print(f'Saved {anim_type.value.upper()} to "{video_path}"\n')
    # iterm
    if config.iterm and anim_type != image.AnimationType.MP4:  # iTerm2 does not support MP4
      image.PrintITerm2(video_path.read_bytes())
      config.console.print()
