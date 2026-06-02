# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Fractal zoom search with AI command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import dataclasses
import logging
import pathlib
import tempfile
from collections import abc
from typing import NoReturn

import click
import gmpy2
import tqdm
import typer
from transcrypto.cli import clibase
from transcrypto.core import hashes
from transcrypto.utils import human, timer

from tranzoom import tranz
from tranzoom.cli import base
from tranzoom.core import ai, fractal, frame, frdb, image

_MANUAL_QUERY_WEIGHT: float = 0.8  # how much to weight the manual query vs the fractal score
_N_FRAMES_PER_DB_SAVE: int = 5  # how many frames to compute before saving to DB

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
  save_frames: bool = base.ANIM_SAVE_FRAMES_OPTION,  # type: ignore[assignment]
) -> None:
  # we intend passing config, so we add the options here...
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
  # TODO: split this monster method
  # build parameters
  n_frames_actually_computed: int = 0
  frm: frame.Frame = base.MakeFrameFromConfig(config, center_re, center_im, f_width, f_height)
  params: frame.ComputationParameters = base.MakeComputationParameters(frm, config)
  render: image.RenderParameters
  out: image.ImageOutputConfig
  render, out = base.MakeRenderParameters(params, config)
  zoom_params: image.ZoomParameters = image.ZoomParameters(
    tp=anim_type,
    img=params,  # zoom is created with the sentinel value (if on AUTO) and does NOT update!
    render=render,  # notice this render does not have prev/next markers!
    mag=gmpy2.mpq(dest_magnification_10),
    n_frames=frames,
    duration=round(duration * image.VIDEO_DURATION_STORE_SCALE),
    loop=loop,
  )
  all_frames: list[frame.Frame]
  all_markers: list[tuple[int, frame.Frame]]
  all_depth: list[tuple[int, frame.Frame]]
  all_frames, all_markers, all_depth = zoom_params.Frames()  # last thing that could go boom!
  d_all_markers: dict[int, frame.Frame] = dict(all_markers)  # for quick lookup
  idx: int
  j: int
  logging.debug(f'Marker frames: {[idx for idx, _ in all_markers]}')
  # we should be good to go, all options check out; log and warn if needed
  config.console.print(
    f'\n{params.width} x {params.height} {render.escaped_pal.value!r} '
    f'{frm.fractal.value.capitalize()!r} [magenta]10^{float(zoom_params.mag):.4f} magnitude ZOOM[/]'
    f', {human.HumanizedSeconds(float(zoom_params.n_seconds))} long, at {fps:.2f} FPS, '
    f'with {zoom_params.n_frames} frames ({len(all_markers)} markers, '
    f'{100.0 * len(all_markers) / zoom_params.n_frames:.2f}%, and {len(all_depth)} depth frames, '
    f'{100.0 * len(all_depth) / zoom_params.n_frames:.2f}%), '
    f'{100.0 * float(zoom_params.scalar_magnification_per_step):.4f}%/step...'
  )
  config.console.print(f'[yellow]ZOOM:[/] {zoom_params} ... {all_frames[-1]}\n')
  if zoom_params.scalar_magnification_per_step > image.THRESHOLD_JUMPY_ZOOM_PER_FRAME:
    config.console.print(
      '[red]Warning: the zoom per frame is high: 10^(mag/(frames-1)) = '
      f'10^({float(zoom_params.mag):.4f}/{zoom_params.n_steps}) = '
      f'{100.0 * float(zoom_params.scalar_magnification_per_step):.4f}%/step. '
      'The resulting animation may look jumpy! Please consider increasing the number of frames '
      'or reducing the total magnification.[/]\n'
    )
  gif_sz: int
  mp4_sz: int
  gif_sz, mp4_sz = zoom_params.animation_sz_bytes()
  if max(gif_sz, mp4_sz) > frame.THRESHOLD_LARGE_ANIMATION_BYTES:
    config.console.print(
      f'[red]Warning: large animation file estimate: '
      f'GIF ~{human.HumanizedBytes(gif_sz)}, MP4 ~{human.HumanizedBytes(mp4_sz)}[/]\n'
    )
  # create path callback missing only the hash
  full_path: abc.Callable[[str], pathlib.Path] = lambda h: image.MakeImagePath(
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix or base.DEFAULT_IMAGE_PREFIX[frm.fractal],
    h,
    tm=timestamp,
    suffix=zoom_params.tp.value.lower(),
  )

  def _SaveLogAndITerm(img_p: pathlib.Path, img_sz: int) -> None:
    """To be called before return.

    Args:
      img_p (pathlib.Path): The path to the saved image.
      img_sz (int): The size of the saved image in bytes.

    """
    # log
    config.console.print(
      f'Saved {zoom_params.tp.value.upper()} to {str(img_p)!r}, {human.HumanizedBytes(img_sz)}\n'
    )
    # iterm
    if config.iterm and zoom_params.tp != image.AnimationType.MP4:  # iTerm2 does not support MP4
      image.PrintITerm2(img_p.read_bytes())
      config.console.print()

  # DB
  img: image.Image
  did_comp: bool
  depth_tmr: timer.Timer | None = None
  all_img_obj: dict[int, image.Image] = {}  # to keep images if not streaming
  all_params: dict[int, frame.ComputationParameters] = {}
  with config.OpenDB() as db:
    streaming: bool = db.is_read_write
    video_hash: str
    cp: frdb.ComputationData | None
    video_path: pathlib.Path
    # warn on large memory usage
    zoom_mem: int = zoom_params.comp_memory_sz_bytes
    if not streaming and zoom_mem > frame.THRESHOLD_LARGE_ZOOM_MEMORY_BYTES:
      config.console.print(
        f'[red]Warning: large zoom render memory estimate: ~{human.HumanizedBytes(zoom_mem)}[/]\n'
      )
    # see if we have a cache of this zoom
    zoom_data: frdb.ZoomData | None = db.FindZoom(zoom_params)
    if zoom_data:
      video_hash = zoom_data['data_hash'] or ''
      old_path: pathlib.Path | None = (
        pathlib.Path(zoom_data['rendered_path']) if zoom_data['rendered_path'] else None
      )
      if video_hash and old_path and old_path.exists() and old_path.is_file():
        # we do have the video!
        config.console.print(
          f'[red]DB render[/], {video_hash!r}@{timer.TimeStr(zoom_data["tm"])} -> "{old_path}"\n'
        )
        video_path = full_path(video_hash)
        if video_path != old_path:
          video_data: bytes = old_path.read_bytes()
          video_path.write_bytes(video_data)
        # log and shortcircuit
        config.console.print(f'Success: {zoom_params.tp.value.upper()} {video_hash!r} from disk')
        _SaveLogAndITerm(video_path, video_path.stat().st_size)
        return
    # produce the depth computations for all the depth frames: this will save us a lot of trouble
    max_iter: int
    stats: image.FractalStats
    depth_computations: dict[int, tuple[frame.Frame, int, int, image.FractalStats]] = {}
    if zoom_data is None or not streaming:
      n_threads: int = frame.ConcurrenceToUse(config.max_threads)
      config.console.print(f'[yellow]Making {len(all_depth)} depth computations...[/]')
      with timer.Timer(emit_log=False) as depth_tmr:
        for idx, frm in tqdm.tqdm(
          all_depth,
          desc='Depth',
          unit='fr',
          dynamic_ncols=True,
          smoothing=0.1,
          colour='yellow',
        ):
          params = dataclasses.replace(params, frm=frm, depth=frame.MIN_ITER)
          max_iter, stats = fractal.FractalAdaptiveIterations(
            params.frm,
            set_points=params.set_points,
            progress_bar=False,
            n_processes=n_threads,
            print_comm=config.console.print,
          )
          depth_computations[idx] = (frm, max_iter, max_iter, stats)
        # we have them, now we can smooth them and replace them into the dict of proposed depths
        jagged_depths: list[int] = [depth_computations[idx][1] for idx, _ in all_depth]
        logging.debug(f'Raw depths for depth frames: {jagged_depths}')
        smoothed_depths: list[int] = frame.SmoothDepths(jagged_depths)
        del jagged_depths
        logging.debug(f'Smoothed depths for depth frames: {smoothed_depths}')
        for j, (idx, _) in enumerate(all_depth):
          frm, max_iter, _, stats = depth_computations[idx]
          depth_computations[idx] = (frm, max_iter, smoothed_depths[j], stats)
        del smoothed_depths
        # this is our first milestone; add to DB; commit
        if streaming:
          db.AddZoomToDB(
            zoom_params,
            timestamp,
            None,
            None,
            all_frames,
            all_markers,
            [(i, *depth_computations[i]) for i in sorted(depth_computations)],
          )
          db.Save()
      # depth computations done, log
      config.console.print(f'{len(all_depth)} depth computations done in {depth_tmr}\n')
    else:
      # we already have the zoom data in the DB, so load it
      for dfd in zoom_data['depths']:
        df: frame.Frame | None = db.FindFrame(dfd['frm'])[0]
        if not df:
          raise base.Error(f'Depth frame {dfd["idx"]} references frame {dfd["frm"]} not in DB')
        depth_computations[dfd['idx']] = (
          df,
          dfd['orig_depth'],
          dfd['smooth_depth'],
          image.FractalStats.FromJson(dfd['stats']),
        )
      # depth computations loaded, sanity check and log
      if set(depth_computations) != (depth_set := {idx for idx, _ in all_depth}):
        raise base.Error(
          'Depth computations in DB do not match the expected depth frames for this zoom: '
          f'{set(depth_computations.keys())} vs {depth_set}; bug! report!'
        )
      config.console.print(f'{len(all_depth)} depth computations loaded from disk\n')
    # from DB or computed, now we have the depths
    sorted_depth_keys: list[int] = sorted(depth_computations)

    def _DepthAndStatsForFrame(i: int) -> tuple[int, image.FractalStats]:
      """Get the depth/stats for a Frame index, interpolating from depth_computations.

      Args:
        i (int): The index of the frame in the zoom sequence.

      Returns:
        tuple[int, image.FractalStats]: A tuple containing the interpolated max iteration depth and
            fractal statistics for the frame at index i.

      """
      if i in depth_computations:
        return (depth_computations[i][2], depth_computations[i][3])
      # interpolate: find the two bracketing keys in depth_computations
      lo_idx: int = sorted_depth_keys[0]
      hi_idx: int = sorted_depth_keys[-1]
      for k in sorted_depth_keys:
        if k <= i:
          lo_idx = k
        else:
          hi_idx = k
          break
      # linearly interpolate max_iter between the two bracketing depths
      lo_depth: int = depth_computations[lo_idx][2]
      hi_depth: int = depth_computations[hi_idx][2]
      t: float = (i - lo_idx) / (hi_idx - lo_idx) if hi_idx != lo_idx else 0.0
      interpolated_depth: int = round(lo_depth + t * (hi_depth - lo_depth))
      # interpolate each FractalStats field independently
      lo_stats: image.FractalStats = depth_computations[lo_idx][3]
      hi_stats: image.FractalStats = depth_computations[hi_idx][3]
      t_mpfr: gmpy2.mpfr = gmpy2.mpfr(t)
      interpolated_stats: image.FractalStats = image.FractalStats(
        n_px=round(lo_stats.n_px + t * (hi_stats.n_px - lo_stats.n_px)),
        n_interior=round(lo_stats.n_interior + t * (hi_stats.n_interior - lo_stats.n_interior)),
        max_lo=lo_stats.max_lo + t_mpfr * (hi_stats.max_lo - lo_stats.max_lo),
        max_hi=lo_stats.max_hi + t_mpfr * (hi_stats.max_hi - lo_stats.max_hi),
        min_lo=lo_stats.min_lo + t_mpfr * (hi_stats.min_lo - lo_stats.min_lo),
        min_hi=lo_stats.min_hi + t_mpfr * (hi_stats.min_hi - lo_stats.min_hi),
        ang_lo=lo_stats.ang_lo + t_mpfr * (hi_stats.ang_lo - lo_stats.ang_lo),
        ang_hi=lo_stats.ang_hi + t_mpfr * (hi_stats.ang_hi - lo_stats.ang_hi),
        imag_lo=lo_stats.imag_lo + t_mpfr * (hi_stats.imag_lo - lo_stats.imag_lo),
        imag_hi=lo_stats.imag_hi + t_mpfr * (hi_stats.imag_hi - lo_stats.imag_hi),
      )
      return (interpolated_depth, interpolated_stats)

    # produce the frames
    total_depth: int = sum(_DepthAndStatsForFrame(j)[0] for j in range(len(all_frames)))
    cmp_bar: tqdm.tqdm[NoReturn] = tqdm.tqdm(
      total=total_depth,
      desc='Iter',
      unit='it',
      dynamic_ncols=True,
      smoothing=0.1,
      colour='magenta',
    )
    with timer.Timer(emit_log=False) as frames_tmr:
      for idx, frm in enumerate(all_frames):
        max_iter, stats = _DepthAndStatsForFrame(idx)
        params = dataclasses.replace(params, frm=frm, depth=max_iter)
        # log
        log_color: str = (
          '[magenta]Marker '
          if idx in d_all_markers
          else ('[cyan]Depth ' if idx in depth_computations else '[yellow]')
        )
        config.console.print(
          f'{log_color}Frame {idx + 1} / {zoom_params.n_frames}[/] - depth {max_iter}'
        )
        # if we are streaming it is super worth it to check before loading!
        if streaming:
          params, _, cp = db.FindComputation(params)
          if cp and cp['raw_data_path']:
            all_params[idx] = params
            config.console.print('Computation in DB cache\n')
            cmp_bar.update(max_iter)  # update progress bar with the depth of this frame
            continue
        # we really need to compute: feed frame to the producer
        params, img, did_comp = db.DoComputation(
          params,  # send frm
          max_threads=config.max_threads,
          stats=stats,
          print_comm=config.console.print,
          force=config.img_force_redo,
        )
        n_frames_actually_computed += bool(did_comp)  # count only actually computed frames
        # save
        all_params[idx] = params
        if not streaming:
          all_img_obj[idx] = img
        # DB checkpoint
        if (
          streaming
          and n_frames_actually_computed
          and not n_frames_actually_computed % _N_FRAMES_PER_DB_SAVE
        ):
          config.console.print('\n[bright_blue](DB checkpoint)[/]')
          db.Save()  # commit to disk every N computations
        config.console.print()
        cmp_bar.update(max_iter)  # update progress bar with the depth of this frame
    # we have all frames; if we're using DB and have done computations, make sure it is all saved
    cmp_bar.close()
    if streaming and n_frames_actually_computed:
      db.Save()
      config.console.print('\n[bright_blue](DB save)[/]\n')
    # we should have all images either in memory or in DB; so now we we rely on _SmartImage()

    def _SmartImage(i: int) -> image.Image:
      """Get the Image object for frame i, either from memory (not streaming) or DB (streaming).

      Args:
        i (int): The index of the frame in the zoom sequence.

      Returns:
        image.Image: The Image object for the frame at index i.

      Raises:
        base.Error: If the image data for frame i is not found in the DB when streaming

      """
      if not streaming:
        return all_img_obj[i]  # noqa: F821
      img_obj: image.Image | None = db.LoadImageData(f'img_{all_params[i].sha}.Data')
      if not img_obj:
        raise base.Error(f'Image data for frame {i} not found in DB; bug; report!')
      return img_obj

    # build ZoomColorNorm from the marker images: anchors color normalization so the same
    # escape-iteration value maps to a consistent palette position across the whole animation,
    # eliminating wild per-frame palette shifts (one color anchor per MAGNITUDE_PER_FRAME_MARKER
    # zoom decades, i.e., one marker every 10x zoom by default)
    zoom_norm: image.Image.ZoomColorNorm = image.Image.ZoomColorNorm.FromSortedMarkers(
      (i, _SmartImage(i)) for i, _ in all_markers
    )  # use the original all_markers b/c it is sorted
    config.console.print(
      f'[yellow]ZOOM:[/] [green]Color norm[/]: built from {len(all_markers)} marker frames\n'
    )
    # render the final animation, first to a temporary path because we do not have the hash yet...
    with tempfile.TemporaryDirectory() as tmpdir, timer.Timer(emit_log=False) as render_tmr:
      # make the rendering progress bar
      config.console.print(f'[yellow]Render:[/] {render}')
      p_bar: tqdm.tqdm[NoReturn] = tqdm.tqdm(
        total=zoom_params.n_frames,
        desc='Render',
        unit='fr',
        dynamic_ncols=True,
        smoothing=0.1,
        colour='yellow',
      )
      # keep the last frame, for later metadata
      last_img: image.Image = img  # pyright: ignore[reportPossiblyUnboundVariable]
      del img  # pyright: ignore[reportPossiblyUnboundVariable]
      try:

        def _StreamingRenderFrame(i: int) -> bytes:
          """Render a single frame, returning the image data as bytes. Only one in memory at a time.

          Args:
            i (int): The index of the frame in the zoom sequence.

          Returns:
            bytes: The rendered image data for the frame at index i.

          """
          img_data: bytes
          data_hash: str
          img_path: pathlib.Path
          p: int
          n: int
          zn: image.Image.FrameColorNorm
          # render
          p, n, zn = zoom_norm.ForFrame(i)
          img_data, data_hash, img_path, _ = db.DoRender(
            _SmartImage(i),  # get the Image object for this frame
            dataclasses.replace(render, prev_marker=all_frames[p], next_marker=all_frames[n]),
            out,
            add_serial=i + 1,
            tm=timestamp,
            iterm=False,  # disable, we want silence
            print_comm=config.console.print,
            force=config.img_force_redo,
            zoom_norm=zn,
            silent=True,  # we will have a progress bar
            no_meta=True,  # do not include metadata for individual frames
          )
          # save hash
          all_hash[i] = data_hash
          # save per-frame-normalized image to disk if requested (for individual frame inspection)
          if save_frames:
            img_path.write_bytes(img_data)
            config.console.print(f'Saved frame {i + 1} to {str(img_path)!r}')
          # update progress bar, return data
          if p_bar:
            p_bar.update(1)
          return img_data

        all_hash: dict[int, str] = {}
        tmp_path: pathlib.Path = pathlib.Path(tmpdir) / f'temp_video.{zoom_params.tp.value.lower()}'
        if zoom_params.tp == image.AnimationType.GIF:
          image.WriteAnimatedGIF(
            (_StreamingRenderFrame(i) for i in range(zoom_params.n_frames)),  # generator! memory!
            tmp_path,
            zoom_params.img.width,
            zoom_params.img.height,
            zoom_params.n_frames,
            float(zoom_params.n_seconds),
            loop=zoom_params.loop,
          )
        elif zoom_params.tp == image.AnimationType.MP4:
          image.WriteVideoMP4(
            (_StreamingRenderFrame(i) for i in range(zoom_params.n_frames)),  # generator! memory!
            tmp_path,
            zoom_params.img.width,
            zoom_params.img.height,
            zoom_params.n_frames,
            float(zoom_params.n_seconds),
          )
        else:
          raise base.UsageError(f'Unsupported animation type: {zoom_params.tp}')
      finally:
        # we are done, close the progress bar, free memory
        p_bar.close()
      del all_img_obj  # this should help free all generated images from memory
      # we can finally compute the hash
      video_hash = hashes.Hash256(
        # stable if the image data and order does not change
        ('|'.join(all_hash[i] for i in range(zoom_params.n_frames))).encode('ascii')
      ).hex()
      # create metadata
      meta: dict[str, str] = image.MakeImageMeta(last_img, render, video_hash)  # use dest. frame
      del last_img
      # add video-specific metadata
      meta[image.META_IMAGE_ANIMATION_KEY] = zoom_params.tp.value.lower()
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
          image.META_ZOOM_MAGNIFICATION_PER_STEP_KEY: str(
            zoom_params.scalar_magnification_per_step
          ),
          image.META_ZOOM_MARKER_INDEX_LIST_KEY: str([idx for idx, _ in all_markers]),
          image.META_ZOOM_DEPTH_FRAMES_LIST_KEY: str(
            # we include pre- and post-smoothing depths for all depth frames
            [
              (idx, depth_computations[idx][1], depth_computations[idx][2])
              for idx in sorted_depth_keys
            ]
          ),
          image.META_ZOOM_HASH_KEY: zoom_params.sha,
        }
      )
      # move the file!
      video_path = full_path(video_hash)
      if zoom_params.tp == image.AnimationType.GIF:
        image.ReWriteAnimatedGIFMeta(tmp_path, video_path, meta)
      elif zoom_params.tp == image.AnimationType.MP4:
        image.ReWriteVideoMP4Meta(tmp_path, video_path, meta)
    # closed temporary directory, video is saved in final destination with final metadata
    config.console.print('[yellow]Render:[/] [green]DONE[/]\n')
    # we just freed the temporary directory; add to DB
    db.AddZoomToDB(
      zoom_params,
      timestamp,
      video_hash,
      str(video_path),
      all_frames,
      all_markers,
      [(idx, *depth_computations[idx]) for idx in sorted_depth_keys],
    )
  # done, close DB, final log and iTerm2
  config.console.print(
    f'Success: {zoom_params.tp.value.upper()} {video_hash!r} in '
    f'{depth_tmr or "-"} (depth) + {frames_tmr} (frames) + {render_tmr} (render)'
  )
  _SaveLogAndITerm(video_path, video_path.stat().st_size)
