# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Mandelbrot zoom search with AI command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import pathlib

import click
import gmpy2
import pydantic
from transai.core import ai, lms
from transcrypto.cli import clibase
from transcrypto.utils import base as tbase
from transcrypto.utils import human, timer

from tranzoom import zoom
from tranzoom.cli import base
from tranzoom.core import fractal, frame, image

_WIDTH: int = 512  # square frames only!
# wipe AI memory every N iterations to prevent it from getting too large and slowing down
_WIPE_MEMORY_INTERVAL: int = 1

_AI_SETUP_PROMPT: str = """
The image is from the Mandelbrot Set:
- The quadrants are divided by white lines that intersect at the center of the image.
- There are green circles marking possible target areas, and labeled in green text.

Find the most beautiful point "X" in the image, considering its abstract qualities;
search for an unique novel and beautiful interest point "X" for deep zooming and pick the green target area that is closest to "X":
- If the chosen point "X" is already near the center of the frame return `center_move: false`.
- If the chosen point "X" is off-center towards a target area, return `center_move: true` and a `move_cardinal_direction` indicating the direction to move the center of the image as one of the following cardinal directions: "N", "NE", "E", "SE", "S", "SW", "W", "NW".
""".strip()  # noqa: E501

# I forbid you from moving in the same direction more than twice in a row{last_direction}.
# After your choice, I will generate a new frame.{last_direction}

_AI_IMAGE_PROMPT: str = """
Given this current frame and image, pick the zoom direction that will take us closer to the most beautiful point "X".
""".strip()  # noqa: E501


class ZoomMovementCommand(pydantic.BaseModel):
  """Frame center zoom movement command."""

  center_move: bool = pydantic.Field(description='should the frame center move?')
  move_cardinal_direction: str | None = pydantic.Field(
    description=(
      'direction of movement for frame center; '
      'one of four primary Cardinal directions or four secondary Intercardinal directions; '
      'options are: "N", "NE", "E", "SE", "S", "SW", "W", "NW"; '
      'required if `center_move` is "true"'
    )
  )


@zoom.app.command(
  'ai',
  help='Use AI to search for an interest point.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run zoom ai\n\n'  # TODO: example
    ''
  ),
)
@clibase.CLIErrorGuard
def AI(  # documentation is help/epilog/args  # noqa: C901, D103, PLR0912, PLR0914, PLR0915
  *,
  ctx: click.Context,
  center_re: str = base.FRAME_CENTER_RE_OPTION,  # type: ignore[assignment]
  center_im: str = base.FRAME_CENTER_IM_OPTION,  # type: ignore[assignment]
  f_width: str = base.FRAME_WIDTH_OPTION,  # type: ignore[assignment]
  f_height: str | None = base.FRAME_HEIGHT_OPTION,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: base.TranZoomConfig = ctx.obj
  try:
    frm: frame.Frame = frame.Frame.FromCenter(
      frame.Fractal.MANDELBROT, center_re, center_im, f_width, f_height
    )
  except Exception as err:
    raise click.UsageError(
      f'Invalid coordinates: {center_re=}, {center_im=}, {f_width=}, {f_height=}'
    ) from err
  # we have a valid frame, let's start the AI search loop by loading the AI
  zoom_tm: int = timer.Now()
  config.console.print('Loading AI model...')  # TODO: add model options!
  with lms.LMStudioWorker(free_resources=True) as worker:
    worker.LoadModel(
      ai.MakeAIModelConfig(
        model_id='qwen3-vl-32b-instruct@q8_0',
        vision=True,
        temperature=0.9,  # only override the ones you care about!
        # all other fields will have sensible defaults; currently also supported are:
        # seed, context, gpu_ratio, gpu_layers, use_mmap, fp16, flash, spec_tokens, kv_cache
      )
    )
    # main loop
    json_chat: tbase.JSONDict | None = None
    direction: str | None = None
    img_data: bytes
    img_hash: str
    response: ZoomMovementCommand
    count: int = 0
    center_mpq_re: gmpy2.mpq
    center_mpq_im: gmpy2.mpq
    while True:
      count += 1
      # calculate magnification
      magnification, magnitude = frm.magnification
      magnification_str: str = (
        # beyond 10^21, human-readable formatting becomes ridiculous, so we use scientific notation
        human.HumanizedDecimal(float(magnification)) if magnitude < 21 else f'{magnification:e}'  # noqa: PLR2004
      )
      # render the image for the current frame
      with timer.Timer(emit_log=False) as tmr:
        img: image.Image = fractal.Mandelbrot(
          frm, _WIDTH, _WIDTH, max_iter=None, progress_bar=True, n_processes=config.max_threads
        )
        # get PNG and overlay info on top of it
        img_data, img_hash = img.AsPNG()
        img_data = image.DrawInfoOverlay(img_data)
      last_direction: str = 'Last move was ' + (
        'to zoom in place' if direction is None else f'towards "{direction}"'
      )
      # log!
      config.console.print(
        f'\n{last_direction}: Mandelbrot zoom (#{count}) with frame {frm}, '
        f'precision {frm.precision} bits, {magnification_str} magnification\n'
        f'{img_hash!r} in {tmr}, escape range {img.escape_range}'
      )
      # save image?
      full_path: pathlib.Path = image.MakeImagePath(
        config.img_output_path,
        config.img_use_date,
        config.img_use_hash,
        config.img_path_prefix,
        img_hash,
        tm=zoom_tm,
        add_serial=count,
      )
      full_path.write_bytes(img_data)
      config.console.print(f'Saved to "{full_path}"')
      # wipe memory?
      if not count % _WIPE_MEMORY_INTERVAL:
        json_chat = None  # wipe memory: json_chat is the context that gets passed to the model
        config.console.print('[red]' + '*' * 20 + ' WIPED MEMORY ' + '*' * 20 + '[/red]')
      # get AI verdict
      config.console.print()
      with timer.Timer(emit_log=False) as tmr:
        response, json_chat = worker.ModelCall(
          'qwen3-vl-32b-instruct@q8_0',
          _AI_SETUP_PROMPT,
          _AI_IMAGE_PROMPT + f'{last_direction}.',
          ZoomMovementCommand,
          images=[img_data],
          chat_history=json_chat,
        )
      # implement the move command: first the scale of the step
      center_mpq_re, center_mpq_im = frm.center
      frame_sz: gmpy2.mpq = frm.size[0]  # only works for square!
      direct_step: gmpy2.mpq = frame_sz * frame.DEFAULT_MPQ_STEP_DIRECT
      diagonal_step: gmpy2.mpq = frame_sz * frame.DEFAULT_MPQ_STEP_DIAGONAL
      # now move the center according to the direction, if requested
      if response.center_move:
        if not response.move_cardinal_direction:
          raise ValueError('move_cardinal_direction is required when center_move is true')
        direction = response.move_cardinal_direction.upper().strip()
        if direction == 'N':
          center_mpq_im += direct_step
        elif direction == 'NE':
          center_mpq_re += diagonal_step
          center_mpq_im += diagonal_step
        elif direction == 'E':
          center_mpq_re += direct_step
        elif direction == 'SE':
          center_mpq_re += diagonal_step
          center_mpq_im -= diagonal_step
        elif direction == 'S':
          center_mpq_im -= direct_step
        elif direction == 'SW':
          center_mpq_re -= diagonal_step
          center_mpq_im -= diagonal_step
        elif direction == 'W':
          center_mpq_re -= direct_step
        elif direction == 'NW':
          center_mpq_re -= diagonal_step
          center_mpq_im += diagonal_step
        else:
          raise ValueError(f'invalid direction: {response.move_cardinal_direction!r}')
        config.console.print(f'MODEL: move {direct_step} => {direction}-wards (in {tmr})')
      else:
        direction = None
        config.console.print(f'MODEL: zoom in place (in {tmr})')
      # build the new frame
      frm = frame.Frame.FromCenter(
        frame.Fractal.MANDELBROT, center_mpq_re, center_mpq_im, frame_sz / frame.DEFAULT_MPQ_ZOOM
      )
