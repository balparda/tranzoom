# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Mandelbrot zoom search with AI command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import dataclasses

import click
import typer
from transcrypto.cli import clibase

from tranzoom import tranz
from tranzoom.cli import base
from tranzoom.core import ai, frame

_MANUAL_QUERY_WEIGHT: float = 0.8  # how much to weight the manual query vs the fractal score


zoom_app = typer.Typer(
  no_args_is_help=True,
  help=(
    'Examples:\n\n\n\n'
    '# --- LLM-Guided Fractal Zoom ---\n'
    'poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" zoom ai\n'
    'poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 zoom ai '
    '" -0.7436499" "0.13188204" "0.00073801" --iterm -n 10\n'
    'poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" zoom ai "/path/to/image.png"\n\n'
    '# --- Human/Manual-Guided Fractal Zoom ---\n'
    'poetry run tranz zoom manual " -0.74303" "0.126433" "0.01611"\n'
    'poetry run tranz zoom manual "/path/to/image.png"'
  ),
)
tranz.app.add_typer(zoom_app, name='zoom')


@zoom_app.callback(invoke_without_command=True)
@clibase.CLIErrorGuard
def ZoomOptions(  # documentation is in help/epilog  # noqa: D103
  *,
  ctx: click.Context,
  # note that these are the zoom image options, with default of 512x512
  img_width: int = base.IMAGE_ZOOM_WIDTH_OPTION,  # type: ignore[assignment]
  img_height: int = base.IMAGE_ZOOM_HEIGHT_OPTION,  # type: ignore[assignment]
  max_steps: int = base.MAX_STEPS_OPTION,  # type: ignore[assignment]
) -> None:
  # store this command's options in the shared config so all sub-commands can read it
  if ctx.invoked_subcommand is not None and ctx.obj is not None:
    ctx.obj = dataclasses.replace(
      ctx.obj,
      img_width=img_width,
      img_height=img_height,
      max_steps=max_steps,
    )


@zoom_app.command(
  'ai',
  help='Use AI to search for an interest point.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" zoom ai\n\n'
    '<start with full set and zoom in using model Qwen 32>\n\n\n\n'
    '$ poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 '
    'zoom ai " -0.7436499" "0.13188204" "0.00073801" --iterm -n 10\n\n'
    '<zoom in using model Qwen 32 with higher temperature 0.7, '
    'start from "Seahorse Tail", print iTerm2 images, stop after 10 steps>\n\n\n\n'
    '$ poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" zoom ai "/path/to/image.png"\n\n'
    '<gets the same frame used in "/path/to/image.png" and starts zoom there>'
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
    frame.Fractal.MANDELBROT, center_re, center_im, f_width, f_height, config.console.print
  )
  # we have a valid frame, let's start the AI search loop
  ai.ZoomLoop(
    frm,
    config.img_width,
    config.img_height,
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix,
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
    '$ poetry run tranz zoom manual " -0.7436499" "0.13188204" "0.00073801" --iterm\n\n'
    '<zoom in manually, start from "Seahorse Tail", print iTerm2 images>\n\n\n\n'
    '$ poetry run tranz zoom manual "/path/to/image.png"\n\n'
    '<gets the same frame used in "/path/to/image.png" and starts zoom there>'
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
    frame.Fractal.MANDELBROT, center_re, center_im, f_width, f_height, config.console.print
  )
  # we have a valid frame, let's start the AI search loop
  ai.ManualLoop(
    frm,
    config.img_width,
    config.img_height,
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix,
    config.max_threads,
    config.max_steps,
    config.iterm,
    config.console.print,
  )
