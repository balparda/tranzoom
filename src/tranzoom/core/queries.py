# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Queries for AI processing."""

from __future__ import annotations

import json
from typing import Literal

import pydantic
from transcrypto.utils import base as tbase

from tranzoom.core import fractal


class Error(fractal.Error):
  """Base AI exception."""


####################################################################################################
# Current AI Queries and Data
####################################################################################################


def BuildImageThirdsPrompts(target_search: str | None = None) -> tuple[str, str]:
  """Build the AI setup and image prompts for the thirds scoring method.

  Args:
    target_search: Optional string describing the targeted search query;
        if None, targeted search is inactive

  Returns:
    A tuple of (setup_prompt, image_prompt)

  """
  setup_text: str
  image_text: str
  if target_search:
    query: str = json.dumps(target_search.strip())
    setup_text = TARGET_THIRDS_SETUP.replace('<<<TARGETED_QUERY>>>', query)
    image_text = TARGET_THIRDS_IMAGE.replace('<<<TARGETED_QUERY>>>', query)
  else:
    setup_text = 'Targeted search is NOT active. `target_match_score` is null for all sectors.'
    image_text = setup_text
  return (
    AI_SETUP_THIRDS_SCORING_PROMPT.replace('<<<TARGETED_BLOCK>>>', setup_text.strip()),
    AI_IMAGE_THIRDS_SCORING_PROMPT.replace('<<<TARGETED_BLOCK>>>', image_text.strip()),
  )


AI_SETUP_THIRDS_SCORING_PROMPT: str = """
Evaluate Mandelbrot Set images for an automated zoom search.

Each image is divided by white grid lines into 9 equal sectors.
Each sector in the image is marked in clear green text with its sector number.

Score each sector from 0 to 100 for how promising it is as the next zoom target in `fractal_score`.
Return one short reason for each sector in `reason`.

Score `fractal_score` high when a sector has:
- dense visible fractal complexity that is not just endless repetition of the same pattern;
- fine detail at multiple scales;
- sharp, intricate boundaries;
- interesting shapes or visual novelty;
- enough structure to make a beautiful zoom target.

Score `fractal_score` low when a sector is dominated by:
- smooth color bands;
- large empty or featureless areas;
- large black or solid-color regions;
- detail limited to only a small edge or corner;
- the central eye of an infinite spiral or infinite recursion.

Calibration of `fractal_score` scores:
- 85 to 100: exceptional; only for the best 1 or 2 sectors in this image.
- 70 to 84: strong; rich structure, but not the very best.
- 50 to 69: good; clear structure with some smooth area.
- 30 to 49: weak/moderate; partial structure or large smooth areas.
- 0 to 29: poor; mostly smooth, empty, solid, or featureless.

Rules for `fractal_score` scoring:
- Score only what is visibly inside each sector.
- Use the full score range.
- Avoid score compression.
- Do not favor the center or the previous direction.
- Usually fewer than three sectors should score above 70.
- A sector with more than one third smooth/empty area should usually score below 60.
- A sector with more than half smooth/empty area should usually score below 40.

<<<TARGETED_BLOCK>>>

Reasoning rules:
- Use plain visual descriptions only: dense detail, fine texture, sharp boundary, smooth area, dark area, empty area, edge detail.
- Avoid naming specific Mandelbrot structures unless they are unmistakable.
- Fractals are often just infinite recursion of the same pattern: stay away from the vanishing point of infinite recursions.
- `fractal_score` scores are relative within the image: normally only the best 1 or 2 sectors should score 90+.
""".strip()  # noqa: E501

TARGET_THIRDS_SETUP: str = """
Targeted search is active, and the search target is:
<<<TARGETED_QUERY>>>

For each sector you will also assign a `target_match_score` from 0 to 100 for how well the sector visibly matches the search target.

Rules for `target_match_score`:
- Score only visible match to the target search, ignoring general fractal quality.
- Clear, unmistakable matches should score 85 or above.
- Partial or ambiguous matches should score below 50.
- Sectors with no visible match should score 0.
- Exact or strong matches should be rare; do not give high target scores broadly.
- Smooth, empty, solid, black, or featureless sectors should usually score 0.
- Any score above 30 must be visibly justified by the target search.
""".strip()  # noqa: E501

AI_IMAGE_THIRDS_SCORING_PROMPT: str = """
Inspect the Mandelbrot image divided into 9 sectors with white grid lines and identified by green text labels.

For each sector, assign a 0 to 100 score in `fractal_score` for next-zoom promise. Judge mainly by:
- visible fractal complexity;
- amount of fine detail;
- boundary intricacy;
- not falling into an infinite recursion vanishing point;
- visual beauty or novelty;
- how much of the sector is smooth, empty, black, or featureless.

Before returning `fractal_score`, compare sectors against the best sector in this image:
- best `fractal_score` sector: usually 85+;
- strong `fractal_score` alternatives: usually 10 to 20 points lower;
- partial detail with large smooth areas: usually 30 to 50 points lower;
- mostly smooth sectors: usually 50+ points lower.

<<<TARGETED_BLOCK>>>

Return exactly one `fractal_score`, one `target_match_score`, and one short `reason` for each sector.
""".strip()  # noqa: E501

TARGET_THIRDS_IMAGE: str = """
Targeted search is active, and the search target is:
<<<TARGETED_QUERY>>>

For each sector you will also assign a `target_match_score` from 0 to 100 for how well the sector visibly matches this search target.
Any `target_match_score` score above 30 should be easily justified and visibly match the target search.
""".strip()  # noqa: E501


class SectorEvaluation(pydantic.BaseModel):
  """Visual quality evaluation for one Mandelbrot image sector."""

  sector: int = pydantic.Field(
    ge=1,
    le=9,
    description=(
      'The sector being evaluated, from 1 to 9, '
      'starting from top-left and going left-to-right, top-to-bottom'
    ),
  )

  fractal_score: int = pydantic.Field(
    ge=0,
    le=100,
    description=('General fractal sector score, from 0 to 100, ignoring optional targeted search'),
  )

  target_match_score: int | None = pydantic.Field(
    default=None,
    ge=0,
    le=100,
    description=(
      'How well this sector visibly matches the optional targeted search, from 0 to 100; '
      'null when no targeted search is provided.'
    ),
  )

  reason: str = pydantic.Field(
    min_length=8,
    max_length=240,
    description=(
      'Brief reason for the score, '
      'based only on visible Mandelbrot structure and optional target match'
    ),
  )

  def FinalScore(self, *, target_weight: float = 0.8) -> int:
    """Calculate the final score for this sector, blending fractal_score and target_match_score.

    Args:
      target_weight: Weight assigned to `target_match_score` when targeted search is active;
          default is 0.8

    Returns:
      The final blended score for this sector.

    """
    # in the absence of a target match score, we just use the fractal score
    if self.target_match_score is None:
      return self.fractal_score
    # we have a target match score, so we blend it with the fractal score
    blended: int = round(
      (1.0 - target_weight) * self.fractal_score + target_weight * self.target_match_score
    )
    # prevent very weak fractal regions from winning only because of a vague target match
    if self.fractal_score < 30:  # noqa: PLR2004
      blended = min(blended, 45)
    return blended


class ZoomSectorScoring(pydantic.BaseModel):
  """Scores for all 9 Mandelbrot zoom sectors."""

  sectors: list[SectorEvaluation] = pydantic.Field(
    min_length=9,
    max_length=9,
    description='Exactly one evaluation for each sector, from 1 to 9',
  )

  @pydantic.model_validator(mode='after')
  def ValidateSectors(self) -> ZoomSectorScoring:
    """Validate that sectors contain exactly one evaluation for each sector.

    Returns:
      The same ZoomSectorScoring instance if validation passes.

    Raises:
      ValueError: If the sectors do not contain exactly one evaluation for each of the 9 sectors.

    """
    if len(self.sectors) != 9:  # noqa: PLR2004
      raise ValueError('sectors should be exactly 9 and must not contain duplicates')
    if (sect := {item.sector for item in self.sectors}) != set(range(1, 10)):
      raise ValueError(f'exactly one evaluation for each sector from 1 to 9, got {sorted(sect)}')
    return self

  def BestEvaluation(self, *, target_weight: float = 0.8) -> SectorEvaluation:
    """Get the sector evaluation with the highest final score.

    If targeted search is inactive, this uses `fractal_score`.
    If targeted search is active, this blends `fractal_score` and
    `target_match_score`, giving more weight to the target match.

    Args:
      target_weight: Weight assigned to `target_match_score` when targeted search is active;
          default is 0.8

    Returns:
      The SectorEvaluation with the highest final score.

    Raises:
      Error: If target_weight is not between 0.0 and 1.0

    """
    if not (0.0 <= target_weight <= 1.0):
      raise Error(f'target_weight must be between 0.0 and 1.0, got {target_weight}')
    return max(self.sectors, key=lambda s: s.FinalScore(target_weight=target_weight))

  def JSON(self) -> tbase.JSONDict:
    """Get a JSON-serializable dict representation of this ZoomSectorScoring.

    Returns:
      A dict with a "sectors" key containing a list of dicts for each sector evaluation.

    """
    return {'sectors': [item.model_dump() for item in self.sectors]}

  @staticmethod
  def FromJSON(json_dict: tbase.JSONDict) -> ZoomSectorScoring:
    """Create a ZoomSectorScoring instance from a JSON dict.

    Args:
      json_dict: A dict with a "sectors" key containing a list of dicts for each sector evaluation.

    Returns:
      A ZoomSectorScoring instance created from the JSON dict.

    Raises:
      Error: invalid JSON format or missing/invalid fields in the sector evaluations

    """
    if 'sectors' not in json_dict:
      raise Error('missing "sectors" key in JSON dict')
    if not isinstance(json_dict['sectors'], list):
      raise Error('"sectors" key must be a list of sector evaluations')
    sectors: list[SectorEvaluation] = []
    for item in json_dict['sectors']:
      if not isinstance(item, dict):
        raise Error('each sector evaluation must be a dict')
      try:
        sectors.append(SectorEvaluation.model_validate(item))
      except pydantic.ValidationError as err:
        raise Error(f'invalid sector evaluation: {err}') from err
    return ZoomSectorScoring(sectors=sectors)


####################################################################################################
# OLD or OBSOLETE AI Queries and Data - for reference
####################################################################################################

__AI_SETUP_CARDINAL_PROMPT: str = """
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

__AI_IMAGE_CARDINAL_PROMPT: str = """
Given this current frame and image, pick the zoom direction that will take us closer to the most beautiful point "X".
""".strip()  # noqa: E501


class __ZoomMovementCommand(pydantic.BaseModel):  # pyright: ignore[reportUnusedClass]
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


####################################################################################################

__AI_SETUP_THIRDS_PROMPT: str = """
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

__AI_IMAGE_THIRDS_PROMPT: str = """
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

type __ZoomSector = Literal['NW', 'N', 'NE', 'W', 'C', 'E', 'SW', 'S', 'SE']
__FRAME_SECTORS: set[str] = {'NW', 'N', 'NE', 'W', 'C', 'E', 'SW', 'S', 'SE'}


class __ZoomSectorChoice(pydantic.BaseModel):  # pyright: ignore[reportUnusedClass]
  """Zoom sector choice."""

  target_sector: __ZoomSector = pydantic.Field(
    description=(
      'The chosen sector containing the best zoom target. '
      'Use "C" for the center sector; '
      'otherwise use one of "NW", "N", "NE", "W", "E", "SW", "S", "SE".'
    )
  )


####################################################################################################
