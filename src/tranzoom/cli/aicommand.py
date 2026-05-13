# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Mandelbrot zoom search with AI command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import pathlib
from typing import Literal, cast

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
_MEMORY_SIZE: int = 3  # number of iterations the LLM will remember

_AI_SETUP_THIRDS_PROMPT: str = """
You are guiding an automated zoom through Mandelbrot set images.

The image is divided by white grid lines into 9 equal sectors:

  NW | N | NE
   W | C | E
  SW | S | SE

The center sector is C.

Your task is to choose the sector that contains the best next zoom target.

Evaluate sectors by visible fractal quality and long-term zoom promise.

Prefer sectors containing:
- dense fractal boundary activity;
- fine filaments, branching, dendrites, antennas, or lace-like structures;
- spirals, curls, embedded minibrots, bulbs, or repeated self-similar forms;
- sharp transitions between interior and exterior regions;
- rich detail at several visible scales;
- visually distinctive, asymmetric, or novel structures.

Avoid sectors dominated by:
- smooth color bands;
- large empty exterior regions;
- large black or solid-color interiors;
- featureless gradients;
- blurry, low-detail, or repetitive texture without structure.

Decision rules:
- Choose exactly one sector.
- Choose C only if the center sector contains the best visible target or is roughly tied with the best off-center sector.
- Choose an off-center sector only if it is clearly more promising than C.
- Do not choose a sector just because it is near an edge or corner.
- Do not choose a sector just because it continues the previous movement.
- The goal is not to zoom as fast as possible; the goal is to keep the zoom centered on the most beautiful and structurally rich Mandelbrot feature.

Movement rules:
- Valid sectors are exactly: NW, N, NE, W, C, E, SW, S, SE.
- Return the chosen sector in `target_sector`.
- Do not choose the same off-center direction more than twice in a row unless every other sector is clearly worse.
""".strip()  # noqa: E501

_AI_IMAGE_THIRDS_PROMPT: str = """
Inspect the current Mandelbrot image divided into 9 sectors.

Silently compare all sectors: NW, N, NE, W, C, E, SW, S, SE.

Choose the single sector containing the most promising next zoom target.

Use this priority order:
1. rich Mandelbrot boundary structure;
2. fine branching, spirals, minibrots, filaments, dendrites, or antennas;
3. multi-scale detail and visual novelty;
4. avoidance of empty smooth bands, flat black areas, and low-detail regions.

Return C if the center sector is best or roughly tied.
Return an off-center sector only if it is clearly more beautiful or more structurally promising than C.

Return only the structured command.
""".strip()  # noqa: E501


type ZoomSector = Literal['NW', 'N', 'NE', 'W', 'C', 'E', 'SW', 'S', 'SE']
_FRAME_SECTORS: set[str] = {'NW', 'N', 'NE', 'W', 'C', 'E', 'SW', 'S', 'SE'}


class ZoomSectorChoice(pydantic.BaseModel):
  """Zoom sector choice."""

  target_sector: ZoomSector = pydantic.Field(
    description=(
      'The chosen sector containing the best zoom target. '
      'Use "C" for the center sector; '
      'otherwise use one of "NW", "N", "NE", "W", "E", "SW", "S", "SE".'
    )
  )


_AI_SETUP_THIRDS_SCORING_PROMPT: str = """
Evaluate Mandelbrot Set images for an automated zoom search.

Each image frame is divided by white grid lines into 9 equal sectors:

  NW | N | NE
   W | C | E
  SW | S | SE

Score every sector from 0 to 10 according to how promising it is as the next zoom target.
Score based on visible Mandelbrot structure and long-term zoom promise.

High scores should go to sectors with:
- dense fractal boundary activity;
- fine filaments, branching, dendrites, antennas, or lace-like structures;
- spirals, curls, embedded minibrots, bulbs, or repeated self-similar forms;
- sharp transitions between interior and exterior regions;
- rich detail at several visible scales;
- visually distinctive, asymmetric, or novel structures.

Low scores should go to sectors dominated by:
- smooth color bands;
- large empty exterior regions;
- large black or solid-color interiors;
- featureless gradients;
- blurry, low-detail, or repetitive texture without clear structure.

Scoring calibration:
- 9 or 10: exceptional target; dense, beautiful, multi-scale fractal structure.
- 7 or 8: very strong target; rich boundary detail and interesting forms.
- 5 or 6: good target; meaningful structure but less exceptional.
- 3 or 4: moderate; some activity but not a standout.
- 2: weak; mostly smooth, sparse, or low-detail.
- 0 or 1: poor; empty, flat, black, or nearly featureless.

Important:
- Score all 9 sectors independently based on the sector's visible Mandelbrot structures.
- Do not give every sector similar scores unless the image truly warrants it.
- Do not favor the center sector automatically, score based on visible Mandelbrot structure.
- Do not favor the previous movement direction automatically, score based on visible Mandelbrot structure.
- Return a brief reason for each sector score.
""".strip()  # noqa: E501

_AI_IMAGE_THIRDS_SCORING_PROMPT: str = """
Inspect the current Mandelbrot Set image divided into 9 equal sectors:

  NW | N | NE
   W | C | E
  SW | S | SE

For each sector, assign a score from 0 to 10 based on:
1. density of Mandelbrot boundary detail;
2. fine branching, filaments, dendrites, antennas, spirals, curls, or minibrots;
3. sharp transitions and multi-scale structure;
4. novelty and visual beauty;
5. avoidance of empty smooth bands, flat black areas, and featureless regions;
6. how promising that sector is as the next zoom target.

Return exactly one score and one short reason for each sector.
""".strip()


class SectorEvaluation(pydantic.BaseModel):
  """Visual quality evaluation for one Mandelbrot image sector."""

  sector: ZoomSector = pydantic.Field(description='The sector being evaluated')

  score: int = pydantic.Field(
    ge=0,
    le=100,
    description=(
      'Visual promise score from 0 to 100; Higher means better for the next Mandelbrot zoom target'
    ),
  )

  reason: str = pydantic.Field(
    min_length=8,
    max_length=240,
    description=('Brief reason for the score, based only on visible Mandelbrot structure'),
  )


class ZoomSectorScoring(pydantic.BaseModel):
  """Scores for all 9 Mandelbrot zoom sectors."""

  sectors: list[SectorEvaluation] = pydantic.Field(
    min_length=9,
    max_length=9,
    description='Exactly one evaluation for each sector: NW, N, NE, W, C, E, SW, S, SE',
  )

  @pydantic.model_validator(mode='after')
  def ValidateSectors(self) -> ZoomSectorScoring:
    """Validate that sectors contain exactly one evaluation for each sector.

    Returns:
      The same ZoomSectorScoring instance if validation passes.

    Raises:
      Error: If the sectors do not contain exactly one evaluation for each of the 9 sectors.

    """
    if {item.sector for item in self.sectors} != _FRAME_SECTORS:
      raise fractal.Error(f'sectors must have exactly these sectors once: {sorted(_FRAME_SECTORS)}')
    if len(self.sectors) != len(_FRAME_SECTORS):
      raise fractal.Error('sectors must not contain duplicates')
    return self

  def BestEvaluation(self) -> SectorEvaluation:
    """Get the sector evaluation with the highest score.

    Returns:
     The SectorEvaluation with the highest score.

    """
    return max(self.sectors, key=lambda item: item.score)

  def BestSector(self) -> ZoomSector:
    """Get the sector with the highest score.

    Returns:
      The ZoomSector with the highest score.

    """
    return self.BestEvaluation().sector


_AI_SETUP_CARDINAL_PROMPT: str = """
The image is from the Mandelbrot Set:
- The quadrants are divided by white lines that intersect at the center of the image.
- There are green circles marking possible target areas, and labeled in green text.

Find the most beautiful point "X" in the image, considering its abstract qualities, uniqueness, novelty, beauty, and pick the green target area that is closest to it:
- If the chosen point "X" is already near the center of the frame return `center_move: false`.
- If the chosen point "X" is off-center towards a target area, return `center_move: true` and a `move_cardinal_direction` indicating the direction to move the center of the image as one of the following cardinal directions: "N", "NE", "E", "SE", "S", "SW", "W", "NW".

Do not move in the same direction more than twice in a row.
There is no preferred direction, so choose any direction based on where the most interesting features are in the image.
The goal is to find the most beautiful point "X" in the Mandelbrot set, which is often near near lots of activity.
Stay away from empty areas with no features or purely black regions.
Focus on finding the most interesting and beautiful point "X", not just zooming in a lot.
""".strip()  # noqa: E501

_AI_IMAGE_CARDINAL_PROMPT: str = """
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
    response: ZoomSectorScoring
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
        img_data = image.DrawThirdsInfoOverlay(img_data)
      last_direction: str = f'Last move was "{direction}": ' if direction is not None else ''
      # log!
      config.console.print(
        f'\n{last_direction}Mandelbrot zoom (#{count}) with frame {frm}, '
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
      # wipe memory of iterations older than _MEMORY_SIZE
      if json_chat is not None:
        messages: list[tbase.JSONDict] = cast('list[tbase.JSONDict]', json_chat['messages'])
        if len(messages) > (2 * _MEMORY_SIZE + 1):  # +1 for the system prompt
          json_chat = {
            # the pattern is: first message is the system prompt,
            # then a 'user' message alternating with 'assistant' messages
            'messages': [messages[0], *messages[-2 * _MEMORY_SIZE :]]
          }
      # get AI verdict
      config.console.print()
      with timer.Timer(emit_log=False) as tmr:
        response, json_chat = worker.ModelCall(
          'qwen3-vl-32b-instruct@q8_0',
          _AI_SETUP_THIRDS_SCORING_PROMPT,
          _AI_IMAGE_THIRDS_SCORING_PROMPT,
          ZoomSectorScoring,
          images=[img_data],
          chat_history=json_chat,
        )
      # implement the move command: first the scale of the step
      center_mpq_re, center_mpq_im = frm.center
      frame_sz: gmpy2.mpq = frm.size[0]  # only works for square!
      direct_step: gmpy2.mpq = frame_sz * frame.DEFAULT_MPQ_STEP_DIRECT
      diagonal_step: gmpy2.mpq = frame_sz * frame.DEFAULT_MPQ_STEP_DIAGONAL
      # now move the center according to the direction, if requested
      best: SectorEvaluation = response.BestEvaluation()
      import pdb

      pdb.set_trace()
      direction = best.sector.upper().strip()
      if direction == 'C':
        pass  # no movement, zoom in place
      elif direction == 'N':
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
        raise ValueError(f'invalid direction: {direction!r}')
      config.console.print(
        f'MODEL: move {direct_step} => {direction}-wards (in {tmr})\n{best.score}/{best.reason}'
      )
      # build the new frame
      frm = frame.Frame.FromCenter(
        frame.Fractal.MANDELBROT, center_mpq_re, center_mpq_im, frame_sz / frame.DEFAULT_MPQ_ZOOM
      )
