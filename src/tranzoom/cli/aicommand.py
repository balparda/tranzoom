# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Mandelbrot zoom search with AI command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import click
from transcrypto.cli import clibase

from tranzoom import zoom
from tranzoom.cli import base
from tranzoom.core import ai, frame

_MANUAL_QUERY_WEIGHT: float = 0.8  # how much to weight the manual query vs the fractal score


@zoom.app.command(
  'ai',
  help='Use AI to search for an interest point.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run zoom -m "qwen3-vl-32b-instruct@q8_0" ai\n\n'
    '<start with full set and zoom in using model Qwen 32>\n\n\n\n'
    '$ poetry run zoom -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 '
    'ai " -0.7436499" "0.13188204" "0.00073801" --iterm -n 10\n\n'
    '<zoom in using model Qwen 32 with higher temperature 0.7, '
    'start from "Seahorse Tail", print iTerm2 images, stop after 10 steps>\n\n\n\n'
    '$ poetry run zoom -m "qwen3-vl-32b-instruct@q8_0" ai "/path/to/image.png"\n\n'
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
  max_steps: int = base.MAX_STEPS_OPTION,  # type: ignore[assignment]
  iterm: bool = base.IMAGE_PRINT_ITERM_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: zoom.TranZoomAIConfig = ctx.obj
  frm: frame.Frame = base.MakeFrameFromCLIArgs(
    frame.Fractal.MANDELBROT, center_re, center_im, f_width, f_height, config.console.print
  )
  # we have a valid frame, let's start the AI search loop
  ai.ZoomLoop(
    frm,
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
    max_steps,
    iterm,
    _MANUAL_QUERY_WEIGHT,
    config.console.print,
  )


@zoom.app.command(
  'manual',
  help='Manually navigate a Mandelbrot zoom search (no AI).',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run zoom manual\n\n'
    '<start with full set and zoom in manually>\n\n\n\n'
    '$ poetry run zoom manual " -0.7436499" "0.13188204" "0.00073801" --iterm\n\n'
    '<zoom in manually, start from "Seahorse Tail", print iTerm2 images>\n\n\n\n'
    '$ poetry run zoom manual "/path/to/image.png"\n\n'
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
  max_steps: int = base.MAX_STEPS_OPTION,  # type: ignore[assignment]
  iterm: bool = base.IMAGE_PRINT_ITERM_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: zoom.TranZoomAIConfig = ctx.obj
  frm: frame.Frame = base.MakeFrameFromCLIArgs(
    frame.Fractal.MANDELBROT, center_re, center_im, f_width, f_height, config.console.print
  )
  # we have a valid frame, let's start the AI search loop
  ai.ManualLoop(
    frm,
    config.img_output_path,
    config.img_use_date,
    config.img_use_hash,
    config.img_path_prefix,
    config.max_threads,
    max_steps,
    iterm,
    config.console.print,
  )
