# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""AI core logic."""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import pathlib
from collections import abc
from typing import cast

import gmpy2
from transai.core import ai as transai_ai
from transai.core import lms
from transcrypto.utils import base as tbase
from transcrypto.utils import timer

from tranzoom.core import frame, frdb, image, queries

DEFAULT_MEMORY_SIZE: int = 5  # default number of iterations the LLM will remember
MAX_MEMORY_SIZE: int = 30  # maximum number of iterations the LLM will remember
_DIRECTION_MAP: dict[int, str] = {
  1: 'NW',
  2: 'N',
  3: 'NE',
  4: 'W',
  5: 'C',
  6: 'E',
  7: 'SW',
  8: 'S',
  9: 'SE',
}


class Error(queries.Error):
  """Base AI exception."""


def ZoomLoop(  # noqa: C901, PLR0912, PLR0914, PLR0915
  db: frdb.FractalDatabase,
  params: frame.ComputationParameters,
  render: image.RenderParameters,
  out: image.ImageOutputConfig,
  max_threads: int | None,
  model: str = '',
  spec_tokens: int | None = None,
  seed: int | None = None,
  context: int = 0,
  temperature: float = 0.0,
  gpu: float = 0.0,
  gpu_layers: int = 0,
  fp16: bool = False,
  use_mmap: bool = False,
  flash: bool = False,
  kv_cache: int | None = None,
  timeout: float = 0.0,
  query: str | None = None,
  reason: bool = False,
  memory: int = 0,
  max_steps: int = 0,
  iterm: bool = False,
  target_weight: float = 0.0,
  *,
  print_comm: abc.Callable[[str], None],
  manual: bool = False,
) -> None:
  """Execute main loop for AI-guided or manually-guided fractal zoom search.

  When manual=False (default), an LLM vision model drives navigation; the AI-specific parameters
  (model, context, temperature, etc.) are used and required.  When manual=True, the user types a
  direction on the keyboard each step; all AI-specific parameters are ignored.

  Args:
    db (frdb.FractalDatabase): The fractal database to use.
    params (frame.ComputationParameters): The computation parameters for the fractal zoom search.
    render (image.RenderParameters): The render parameters for each zoom step, including color
        palettes and the overlay type (should be OverlayType.GRID to enable navigation grid).
    out (image.ImageOutputConfig): Output path configuration for file naming.
    max_threads (int | None): Optional maximum number of threads to use for rendering; if None,
        use all available CPU cores.
    model (str): The AI model identifier to use for the search; ignored when manual=True.
    spec_tokens (int | None): Optional number of tokens for the model specification; if None,
        use the model's default; ignored when manual=True.
    seed (int | None): Optional random seed for the model; if None, use a random seed; ignored
        when manual=True.
    context (int): The context window size (in tokens) for the model; ignored when manual=True.
    temperature (float): The sampling temperature for the model's responses; ignored when
        manual=True.
    gpu (float): The GPU usage ratio for the model (0.0 to 1.0); ignored when manual=True.
    gpu_layers (int): The number of model layers to offload to the GPU; ignored when manual=True.
    fp16 (bool): Whether to use FP16 precision for the model; ignored when manual=True.
    use_mmap (bool): Whether to use memory-mapped files for the model; ignored when manual=True.
    flash (bool): Whether to use flash attention for the model; ignored when manual=True.
    kv_cache (int | None): Optional size of the key-value cache; if None, use the model's
        default; ignored when manual=True.
    timeout (float): The timeout (in seconds) for model operations; ignored when manual=True.
    query (str | None): Optional query appended to the default prompt; if None, no extra query;
        ignored when manual=True.
    reason (bool): Whether to include the `reason` field in the AI output; ignored when
        manual=True.
    memory (int): Number of previous iterations the LLM remembers in chat history; 0 means no
        memory; ignored when manual=True.
    max_steps (int): Maximum number of zoom steps; 0 means run until Ctrl+C.
    iterm (bool): Whether to print the image inline in iTerm2 using the inline image protocol.
    target_weight (float): Weight (0.0-1.0) for target match score vs fractal score when picking
        the best sector; 0.0 = fractal only, 1.0 = target only; ignored when manual=True.
    print_comm (abc.Callable[[str], None]): A rich console callable for printing messages.
    manual (bool): If True, skip the AI model entirely and prompt the user for a direction
        each step (1-9, numpad layout); default is False (AI-guided mode).

  """
  # capture the time
  zoom_tm: int = timer.Now()
  if manual:
    print_comm(
      f'Run {params} for [bold]{max_steps or "[red]∞[/]"}[/] step(s). '
      'Press [bold][red]Ctrl+C[/][/] to stop at any time.'
    )
    print_comm(f'{timer.TimeStr(zoom_tm)} ({zoom_tm})')
  else:
    print_comm(
      f'Run {params} for [bold]{max_steps or "[red]∞[/]"}[/] step(s). LLM will '
      + ('include reason field. ' if reason else '[cyan]NOT[/] include reason field. ')
      + 'Press [bold][red]Ctrl+C[/][/] to stop at any time.'
    )
    print_comm(
      f'[yellow]Loading AI model [bold]{model}[/]...[/] / {timer.TimeStr(zoom_tm)} ({zoom_tm})'
    )
  # build AI prompts (skipped in manual mode)
  setup_query: str = ''
  image_query: str = ''
  if not manual:
    query = query.strip() if query else None
    setup_query, image_query = queries.BuildImageThirdsPrompts(params.frm, reason, query)
    logging.debug(f'AI setup query:\n{setup_query}\n')
  # use LMStudioWorker for AI mode; nullcontext (no-op) for manual mode
  ai_ctx: contextlib.AbstractContextManager[lms.LMStudioWorker | None] = (
    lms.LMStudioWorker(timeout=timeout, free_resources=True)
    if not manual
    else contextlib.nullcontext()
  )
  count: int = 1
  try:  # noqa: PLR1702
    with ai_ctx as worker:
      # load model (skipped in manual mode; worker is None when manual=True)
      model_config: transai_ai.AIModelConfig | None = None
      if not manual:
        assert worker is not None  # noqa: S101 (ai_ctx is LMStudioWorker when not manual)
        model_config = worker.LoadModel(
          transai_ai.MakeAIModelConfig(
            vision=True,
            model_id=model,
            seed=seed,
            context=context,
            temperature=temperature,
            gpu_ratio=gpu,
            gpu_layers=gpu_layers,
            use_mmap=use_mmap,
            fp16=fp16,
            flash=flash,
            spec_tokens=spec_tokens,
            kv_cache=kv_cache,
          )
        )[0]
      # main loop: runs until max_steps is reached, or Ctrl+C is pressed
      json_chat: tbase.JSONDict | None = None
      img_data: bytes
      response: queries.ZoomSectorScoring | queries.ZoomSectorCompleteScoring
      full_path: pathlib.Path
      tmr: timer.Timer
      count = 0
      while True:
        count += 1
        # render the image for the current frame
        _, img_data, _, full_path = frdb.CoreComputeImage(
          db, params, render, out, count, zoom_tm, max_threads, iterm, print_comm
        )
        print_comm('Press [bold][red]Ctrl+C[/][/] to stop at any time.')
        if not manual:
          assert worker is not None  # noqa: S101 (ai_ctx is LMStudioWorker when not manual)
          # wipe memory of iterations older than memory
          if json_chat is not None:
            messages: list[tbase.JSONDict] = cast('list[tbase.JSONDict]', json_chat['messages'])
            if not memory:
              json_chat = None  # no memory, start fresh every time
            elif len(messages) > (2 * memory + 1):  # +1 for the system prompt
              json_chat = {
                # the pattern is: first message is the system prompt,
                # then 'user' messages alternating with 'assistant' messages
                'messages': [messages[0], *messages[-2 * memory :]]
              }
          # get AI verdict
          with timer.Timer(emit_log=False) as tmr:
            response, json_chat = worker.ModelCall(
              model,
              setup_query,
              image_query,
              queries.ZoomSectorCompleteScoring if reason else queries.ZoomSectorScoring,
              images=[img_data],
              chat_history=json_chat,
            )
        else:
          # get user direction input: accept 1-9 only (numpad layout)
          direction: int = -1
          user_input: str = ''
          with timer.Timer(emit_log=False) as tmr:
            while not (1 <= direction <= 9):  # noqa: PLR2004
              try:
                user_input = input(
                  'Enter direction to zoom '
                  '(1-9, like numpad, where 5 is center, 8 is up/North, 6 is right/East, etc.): '
                ).strip()
                direction = int(user_input)
              except ValueError:
                print_comm(f'[red]Invalid input[/] [bold][yellow]{user_input!r}[/][/]')
          # build a fake response with the user direction as the "human LLM verdict"
          response = queries.ZoomSectorScoring(
            sectors=[
              queries.SectorEvaluation(
                sector=i,
                fractal_score=(100 if i == direction else 0),
                target_match_score=None,
              )
              for i in range(1, 10)
            ],
          )
        # save the image, adding the response evaluation as metadata on top of the image
        full_path.write_bytes(
          image.AddEvaluationMetaToImage(
            img_data,
            response.JSON(),
            model if not manual else image.META_LLM_MODEL_VALUE_HUMAN,
            temperature if not manual else 0.0,
            (model_config['seed'] or 0) if model_config is not None else 0,
            reason if not manual else False,
            memory if not manual else 0,
            setup_query if not manual else '',
            image_query if not manual else '',
            query if not manual else None,
            count,
          )
        )
        # implement the move command
        params = dataclasses.replace(
          params,
          frm=_MoveCenter(
            params.frm,
            query if not manual else None,
            response,
            tmr,
            target_weight if not manual else 0.0,
            print_comm,
          ),
        )
        # stop if we've reached the maximum number of steps
        if max_steps and count >= max_steps:
          print_comm('[yellow]Reached maximum zoom step(s), stopping.[/yellow]')
          break
  # we're out of the main loop
  except KeyboardInterrupt:
    print_comm(f'\n[yellow]Interrupted by user on step {count}.[/yellow]')
  print_comm(f'\nZoom session ended: {count - 1} step(s) completed, last frame: {params}\n')


def _MoveCenter(  # noqa: C901
  frm: frame.Frame,
  query: str | None,
  response: queries.ZoomSectorScoring | queries.ZoomSectorCompleteScoring,
  tmr: timer.Timer,
  target_weight: float,
  print_comm: abc.Callable[[str], None],
) -> frame.Frame:
  """Move the frame center according to the AI response.

  Args:
    frm (frame.Frame): The current frame.
    query (str | None): The optional search query used for targeted scoring.
    response (queries.ZoomSectorScoring | queries.ZoomSectorCompleteScoring): The AI response
        containing the sector evaluations.
    tmr (timer.Timer): The timer for the current operation.
    target_weight (float): The weight (0.0 to 1.0) to give to the target match score when
        determining the best sector; if 0.0, only the fractal score is used; if 1.0, only the
        target match score is used.
    print_comm (abc.Callable[[str], None]): A rich console callable for printing messages.

  Returns:
    frame.Frame: The new frame with the updated center.

  Raises:
    Error: If the AI response contains an invalid sector

  """
  # implement the move command: first the scale of the step
  center_mpq_re: gmpy2.mpq
  center_mpq_im: gmpy2.mpq
  frame_width: gmpy2.mpq
  frame_height: gmpy2.mpq
  center_mpq_re, center_mpq_im = frm.center
  frame_width, frame_height = frm.size
  width_step: gmpy2.mpq = frame_width * frame.DEFAULT_MPQ_STEP_DIRECT
  height_step: gmpy2.mpq = frame_height * frame.DEFAULT_MPQ_STEP_DIRECT
  w_diagonal_step: gmpy2.mpq = width_step * frame.DEFAULT_MPQ_STEP_DIAGONAL
  h_diagonal_step: gmpy2.mpq = height_step * frame.DEFAULT_MPQ_STEP_DIAGONAL
  # now move the center according to the direction, if requested
  best: queries.SectorCompleteEvaluation | queries.SectorEvaluation = response.BestEvaluation(
    target_weight=target_weight
  )
  direction: str = _DIRECTION_MAP[best.sector]
  if direction == 'C':
    pass  # no movement, zoom in place
  elif direction == 'N':
    center_mpq_im += height_step
  elif direction == 'NE':
    center_mpq_re += w_diagonal_step
    center_mpq_im += h_diagonal_step
  elif direction == 'E':
    center_mpq_re += width_step
  elif direction == 'SE':
    center_mpq_re += w_diagonal_step
    center_mpq_im -= h_diagonal_step
  elif direction == 'S':
    center_mpq_im -= height_step
  elif direction == 'SW':
    center_mpq_re -= w_diagonal_step
    center_mpq_im -= h_diagonal_step
  elif direction == 'W':
    center_mpq_re -= width_step
  elif direction == 'NW':
    center_mpq_re -= w_diagonal_step
    center_mpq_im += h_diagonal_step
  else:
    raise Error(f'invalid direction: {direction!r}')
  print_comm(f'[yellow]MODEL: move [bold]{best.sector}/{direction}-wards[/][/] (in {tmr})')
  for sector_eval in sorted(
    response.sectors, key=lambda s: s.FinalScore(target_weight=target_weight), reverse=True
  ):
    target_score: str = (
      '' if sector_eval.target_match_score is None else f'/{sector_eval.target_match_score}'
    )
    if sector_eval.target_match_score and query is None:
      raise Error(f'Match score given but no query; LLM scoring inconsistent!\n{response.JSON()}')
    reason: str = (
      sector_eval.reason if isinstance(sector_eval, queries.SectorCompleteEvaluation) else 'N/A'
    )
    print_comm(
      f'#{sector_eval.sector}/[green]{_DIRECTION_MAP[sector_eval.sector]}[/]: '
      f'{sector_eval.fractal_score}{target_score} - {reason}'
    )
  # build the new frame
  return frame.Frame.FromCenter(
    frm.fractal,
    center_mpq_re,
    center_mpq_im,
    frame_width / frame.DEFAULT_MPQ_ZOOM,
    height=frame_height / frame.DEFAULT_MPQ_ZOOM,
    point_re=frm.point_re,
    point_im=frm.point_im,
  )
