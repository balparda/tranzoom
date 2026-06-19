# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Queries for AI processing."""

from __future__ import annotations

import abc as abstract
import json
from typing import Literal, Self, final

import pydantic
from transcrypto.utils import base as tbase

from tranzoom.core import frame, frdb


class Error(frdb.Error):
  """Base AI exception."""


####################################################################################################
# Current AI Queries and Data
####################################################################################################


def BuildImageThirdsPrompts(
  frm: frame.Frame, reason: bool, target_search: str | None = None
) -> tuple[str, str]:
  """Build the AI setup and image prompts for the thirds scoring method.

  Args:
    frm (frame.Frame): The current frame for the fractal zoom search.
    reason (bool): Whether to include the reasoning field in the prompts
    target_search (str | None): Optional string describing the targeted search query;
        if None, targeted search is inactive; default is None

  Returns:
    tuple[str, str]: A tuple of (setup_prompt, image_prompt)

  """
  # make targeted search blocks
  query_setup_text: str
  query_image_text: str
  if target_search:
    query: str = json.dumps(target_search.strip())
    query_setup_text = TARGET_THIRDS_SETUP.replace('<<<TARGETED_QUERY>>>', query)
    query_image_text = TARGET_THIRDS_IMAGE.replace('<<<TARGETED_QUERY>>>', query)
  else:
    query_setup_text = (
      'Targeted search is NOT active. `target_match_score` is null for all sectors.'
    )
    query_image_text = query_setup_text
  # put these into the main text
  setup_text: str = AI_SETUP_THIRDS_SCORING_PROMPT.replace(
    '<<<TARGETED_BLOCK>>>', query_setup_text.strip()
  )
  image_text: str = AI_IMAGE_THIRDS_SCORING_PROMPT.replace(
    '<<<TARGETED_BLOCK>>>', query_image_text.strip()
  )
  # add the reasoning field
  if reason:
    setup_text = setup_text.replace(
      '<<<REASON_BLOCK_1>>>', 'Return one short reason for each sector in the `reason` field.'
    )
    image_text = image_text.replace(
      '<<<REASON_BLOCK_2>>>',
      (
        'Return exactly one `fractal_score`, one `target_match_score`, '
        'and one short `reason` for each sector.'
      ),
    )
  else:
    setup_text = setup_text.replace('<<<REASON_BLOCK_1>>>', '')
    image_text = image_text.replace(
      '<<<REASON_BLOCK_2>>>',
      'Return exactly one `fractal_score` and one `target_match_score` for each sector.',
    )
  # replace fractal type
  fractal_type_str: str = frm.fractal.value.capitalize()
  setup_text = setup_text.replace('<<<FRACTAL_TYPE>>>', fractal_type_str)
  image_text = image_text.replace('<<<FRACTAL_TYPE>>>', fractal_type_str)
  return (setup_text.strip(), image_text.strip())


AI_SETUP_THIRDS_SCORING_PROMPT: str = """
Evaluate <<<FRACTAL_TYPE>>> Set images for an automated zoom search.

Each image is divided by white grid lines into 9 equal sectors.
Each sector in the image is marked in clear green text with its sector number.

Score each sector from 0 to 100 for how promising it is as the next zoom target in `fractal_score`.
<<<REASON_BLOCK_1>>>

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
- Silently compare all sectors against the best visible sector before assigning final scores.
- Use plain visual descriptions only: dense detail, fine texture, sharp boundary, smooth area, dark area, empty area, edge detail.
- Avoid naming specific <<<FRACTAL_TYPE>>> structures unless they are unmistakable.
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
Inspect the <<<FRACTAL_TYPE>>> image divided into 9 sectors with white grid lines and identified by green text labels.

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

<<<REASON_BLOCK_2>>>
""".strip()  # noqa: E501

TARGET_THIRDS_IMAGE: str = """
Targeted search is active, and the search target is:
<<<TARGETED_QUERY>>>

For each sector you will also assign a `target_match_score` from 0 to 100 for how well the sector visibly matches this search target.
Any `target_match_score` score above 30 should be easily justified and visibly match the target search.
""".strip()  # noqa: E501


class ImageScore(pydantic.BaseModel, abstract.ABC):
  """A sector score."""

  sector: int
  fractal_score: int
  target_match_score: int | None

  @final
  def FinalScore(self, *, target_weight: float = 0.8) -> int:
    """Calculate the final score for this sector, blending fractal_score and target_match_score.

    Args:
      target_weight (float): Weight assigned to `target_match_score` when targeted search is
          active; default is 0.8

    Returns:
      int: The final blended score for this sector.

    Raises:
      Error: on error

    """
    if not (0.0 <= target_weight <= 1.0):
      raise Error(f'target_weight must be between 0.0 and 1.0, got {target_weight}')
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


class SectorEvaluation(ImageScore):
  """Visual quality evaluation for one fractal image sector."""

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


class SectorCompleteEvaluation(SectorEvaluation):
  """Visual quality evaluation for one fractal image sector."""

  reason: str = pydantic.Field(
    min_length=8,
    max_length=240,
    description=(
      'Brief reason for the score, '
      'based only on visible fractal structure and optional target match'
    ),
  )


class ImageScores[ScoreT: ImageScore](pydantic.BaseModel, abstract.ABC):
  """A collection of sector scores to make a whole image score."""

  sectors: list[ScoreT]

  @final
  def _PrivateValidateSectors(self) -> Self:
    """Validate that sectors contain exactly one evaluation for each sector.

    Returns:
      Self: The same ImageScores instance if validation passes.

    Raises:
      ValueError: If the sectors do not contain exactly one evaluation for each of the 9 sectors.

    """
    if len(self.sectors) != 9:  # noqa: PLR2004
      raise ValueError('sectors should be exactly 9 and must not contain duplicates')
    if (sect := {item.sector for item in self.sectors}) != set(range(1, 10)):
      raise ValueError(f'exactly one evaluation for each sector from 1 to 9, got {sorted(sect)}')
    return self

  @final
  def BestEvaluation(self, *, target_weight: float = 0.8) -> ScoreT:
    """Sector evaluation with the highest final score.

    If targeted search is inactive, this uses `fractal_score`.
    If targeted search is active, this blends `fractal_score` and
    `target_match_score`, giving more weight to the target match.

    Args:
      target_weight (float): Weight assigned to `target_match_score` when targeted search is
          active; default is 0.8

    Returns:
      ScoreT: The sector evaluation with the highest final score.

    Raises:
      Error: If target_weight is not between 0.0 and 1.0

    """
    if not (0.0 <= target_weight <= 1.0):
      raise Error(f'target_weight must be between 0.0 and 1.0, got {target_weight}')
    return max(self.sectors, key=lambda s: s.FinalScore(target_weight=target_weight))

  @final
  def JSON(self) -> tbase.JSONDict:
    """JSON-serializable dict representation of this scoring object.

    Returns:
      tbase.JSONDict: A dict with a "sectors" key containing a list of dicts for each sector
          evaluation.

    """
    return {'sectors': [item.model_dump() for item in self.sectors]}

  @classmethod
  def FromJSON(cls, json_dict: tbase.JSONDict) -> Self:
    """Create a scoring object instance from a JSON dict.

    Args:
      json_dict (tbase.JSONDict): A dict with a "sectors" key containing a list of dicts for each
          sector evaluation.

    Returns:
      Self: A scoring object instance created from the JSON dict.

    """
    return cls.model_validate(json_dict)


class ZoomSectorScoring(ImageScores[SectorEvaluation]):
  """Scores for all 9 fractal sectors."""

  sectors: list[SectorEvaluation] = pydantic.Field(
    min_length=9,
    max_length=9,
    description='Exactly one evaluation for each sector, from 1 to 9',
  )

  @pydantic.model_validator(mode='after')
  def ValidateSectors(self) -> Self:
    """Validate that sectors contain exactly one evaluation for each sector.

    Returns:
      Self: The same ZoomSectorScoring instance if validation passes.

    """
    return self._PrivateValidateSectors()


class ZoomSectorCompleteScoring(ImageScores[SectorCompleteEvaluation]):
  """Scores for all 9 fractal sectors."""

  sectors: list[SectorCompleteEvaluation] = pydantic.Field(
    min_length=9,
    max_length=9,
    description='Exactly one evaluation for each sector, from 1 to 9',
  )

  @pydantic.model_validator(mode='after')
  def ValidateSectors(self) -> Self:
    """Validate that sectors contain exactly one evaluation for each sector.

    Returns:
      Self: The same ZoomSectorCompleteScoring instance if validation passes.

    """
    return self._PrivateValidateSectors()


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
