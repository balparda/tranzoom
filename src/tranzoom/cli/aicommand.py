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
    'start from "Seahorse Tail", print iTerm2 images, stop after 10 steps>'
  ),
)
@clibase.CLIErrorGuard
def AI(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_OPTION,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_OPTION,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_OPTION,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_OPTION,  # type: ignore[assignment]
  memory: int = base.MAX_CHAT_MEMORY_OPTION,  # type: ignore[assignment]
  max_steps: int = base.MAX_STEPS_OPTION,  # type: ignore[assignment]
  iterm: bool = base.IMAGE_PRINT_ITERM_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: zoom.TranZoomAIConfig = ctx.obj
  try:
    frm: frame.Frame = frame.Frame.FromCenter(
      frame.Fractal.MANDELBROT, center_re, center_im, f_width, f_height
    )
  except Exception as err:
    raise click.UsageError(
      f'Invalid coordinates: {center_re=}, {center_im=}, {f_width=}, {f_height=}'
    ) from err
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
    memory,
    max_steps,
    iterm,
    config.console.print,
  )
