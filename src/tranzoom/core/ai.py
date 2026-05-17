# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""AI core logic."""

from __future__ import annotations

import logging
import pathlib
from collections import abc
from typing import cast

import gmpy2
from transai.core import ai as transai_ai
from transai.core import lms
from transcrypto.utils import base as tbase
from transcrypto.utils import human, timer

from tranzoom.core import fractal, frame, image, palette, queries

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


def ZoomLoop(
  frm: frame.Frame,
  width: int,
  height: int,
  img_output_path: pathlib.Path | None,
  img_use_date: bool,
  img_use_hash: bool,
  img_path_prefix: str,
  pal: palette.Palette,
  set_pal: palette.Palette,
  color_set_points: bool,
  max_threads: int | None,
  model: str,
  spec_tokens: int | None,
  seed: int | None,
  context: int,
  temperature: float,
  gpu: float,
  gpu_layers: int,
  fp16: bool,
  use_mmap: bool,
  flash: bool,
  kv_cache: int | None,
  timeout: float,
  query: str | None,
  reason: bool,
  memory: int,
  max_steps: int,
  iterm: bool,
  target_weight: float,
  print_comm: abc.Callable[[str], None],
) -> None:
  """Execute main loop for AI-guided fractal zoom search.

  Args:
    frm: The initial frame for the fractal zoom search.
    width: The width of the image to render.
    height: The height of the image to render.
    img_output_path: Optional path to save the rendered images; if None, images will be
        saved to current working directory.
    img_use_date: Whether to include the current date in the image filename when saving.
    img_use_hash: Whether to include the image hash in the filename when saving.
    img_path_prefix: A prefix to add to the image filename when saving.
    pal: The color palette to use for rendering the image.
    set_pal: The color palette to use for interior Set points.
    color_set_points: If True, color the interior Set points with `set_pal` instead of black.
    max_threads: Optional maximum number of threads to use for rendering; if None, use all
        available CPU cores.
    model: The AI model identifier to use for the search.
    spec_tokens: Optional number of tokens to use for the model's specification; if None,
        use the model's default.
    seed: Optional random seed for the model; if None, use a random seed.
    context: The context window size (in tokens) for the model.
    temperature: The sampling temperature for the model's responses.
    gpu: The GPU usage ratio for the model (0.0 to 1.0).
    gpu_layers: The number of layers of the model to offload to the GPU.
    fp16: Whether to use FP16 precision for the model; default is False.
    use_mmap: Whether to use memory-mapped files for the model; default is False.
    flash: Whether to use flash attention for the model; default is False.
    kv_cache: Optional size of the key-value cache for the model; if None, use the model's default.
    timeout: The timeout (in seconds) for model operations.
    query: Optional query to be added to the default prompt; if None, no additional query.
    reason: Whether to include the `reason` field in the AI output.
    memory: The number of previous iterations the LLM will remember in its chat history;
        0 means no memory.
    max_steps: Maximum number of zoom steps to run; 0 means run until manually stopped (Ctrl+C)
    iterm: Whether to print the image inline in iTerm2 using the iTerm2 inline image protocol.
    target_weight: The weight (0.0 to 1.0) to give to the target match score when determining the
        best sector; if 0.0, only the fractal score is used; if 1.0, only the target match
        score is used.
    print_comm: A rich console callable for printing messages.

  """
  # capture the time and load model
  zoom_tm: int = timer.Now()
  print_comm(
    f'Will run {width} x {height} for [bold]{max_steps or "[red]∞[/]"}[/] step(s). LLM will '
    + ('include reason field. ' if reason else '[cyan]NOT[/] include reason field. ')
    + 'Press [bold][red]Ctrl+C[/][/] to stop at any time.'
  )
  print_comm(
    f'[yellow]Loading AI model [bold]{model}[/]...[/] / {timer.TimeStr(zoom_tm)} ({zoom_tm})\n'
  )
  # make queries
  setup_query: str
  image_query: str
  query = query.strip() if query else None
  setup_query, image_query = queries.BuildImageThirdsPrompts(frm, reason, query)
  logging.debug(f'AI setup query:\n{setup_query}\n')
  logging.debug(f'AI image query:\n{image_query}\n')
  # start
  count: int = 1
  try:
    with lms.LMStudioWorker(timeout=timeout, free_resources=True) as worker:
      model_config: transai_ai.AIModelConfig = worker.LoadModel(
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
      count = 0
      while True:
        count += 1
        # render the image for the current frame
        img_data, full_path = _ComputeFractal(
          frm,
          width,
          height,
          count,
          zoom_tm,
          img_output_path,
          img_use_date,
          img_use_hash,
          img_path_prefix,
          pal,
          set_pal,
          color_set_points,
          max_threads,
          iterm,
          print_comm,
        )
        # wipe memory of iterations older than _MEMORY_SIZE
        if json_chat is not None:
          messages: list[tbase.JSONDict] = cast('list[tbase.JSONDict]', json_chat['messages'])
          if not memory:
            json_chat = None  # no memory, start fresh every time
          elif len(messages) > (2 * memory + 1):  # +1 for the system prompt
            json_chat = {
              # the pattern is: first message is the system prompt,
              # then a 'user' message alternating with 'assistant' messages
              'messages': [messages[0], *messages[-2 * memory :]]
            }
        # get AI verdict
        print_comm('')
        print_comm('Press [bold][red]Ctrl+C[/][/] to stop at any time.')
        with timer.Timer(emit_log=False) as tmr:
          response, json_chat = worker.ModelCall(
            model,
            setup_query,
            image_query,
            queries.ZoomSectorCompleteScoring if reason else queries.ZoomSectorScoring,
            images=[img_data],
            chat_history=json_chat,
          )
        # save the image, adding the response evaluation as metadata on top of the image
        full_path.write_bytes(
          image.AddEvaluationMetaToImage(
            img_data,
            response.JSON(),
            model,
            temperature,
            model_config['seed'] or 0,
            reason,
            memory,
            setup_query,
            image_query,
            query,
            count,
          )
        )
        # implement the move command
        frm = _MoveCenter(frm, query, response, tmr, target_weight, print_comm)
        # stop if we've reached the maximum number of steps
        if max_steps and count >= max_steps:
          print_comm('[yellow]Reached maximum zoom step(s), stopping.[/yellow]')
          break
  # we're out of the main loop
  except KeyboardInterrupt:
    print_comm(f'\n[yellow]Interrupted by user on step {count}.[/yellow]')
  print_comm(f'\nZoom session ended: {count - 1} step(s) completed, last frame: {frm}\n')


def ManualLoop(
  frm: frame.Frame,
  width: int,
  height: int,
  img_output_path: pathlib.Path | None,
  img_use_date: bool,
  img_use_hash: bool,
  img_path_prefix: str,
  pal: palette.Palette,
  set_pal: palette.Palette,
  color_set_points: bool,
  max_threads: int | None,
  max_steps: int,
  iterm: bool,
  print_comm: abc.Callable[[str], None],
) -> None:
  """Execute main loop for manually-guided fractal zoom search.

  Args:
    frm: The initial frame for the fractal zoom search.
    width: The width of the image to render.
    height: The height of the image to render.
    img_output_path: Optional path to save the rendered images; if None, images will be
        saved to current working directory.
    img_use_date: Whether to include the current date in the image filename when saving.
    img_use_hash: Whether to include the image hash in the filename when saving.
    img_path_prefix: A prefix to add to the image filename when saving.
    pal: The color palette to use for rendering the image.
    set_pal: The color palette to use for interior Set points.
    color_set_points: If True, color the interior Set points with `set_pal` instead of black.
    max_threads: Optional maximum number of threads to use for rendering; if None, use all
        available CPU cores.
    max_steps: Maximum number of zoom steps to run; 0 means run until manually stopped (Ctrl+C)
    iterm: Whether to print the image inline in iTerm2 using the iTerm2 inline image protocol.
    print_comm: A rich console callable for printing messages.

  """
  # capture the time and load model
  zoom_tm: int = timer.Now()
  print_comm(
    f'Will run {width} x {height} for [bold]{max_steps or "[red]∞[/]"}[/] step(s). '
    'Press [bold][red]Ctrl+C[/][/] to stop at any time.'
  )
  print_comm(f'{timer.TimeStr(zoom_tm)} ({zoom_tm})\n')
  # start
  count: int = 1
  try:
    # main loop: runs until max_steps is reached, or Ctrl+C is pressed
    img_data: bytes
    full_path: pathlib.Path
    response: queries.ZoomSectorScoring  # response here never needs the `reason` field b/c human!
    count = 0
    while True:
      count += 1
      # render the image for the current frame
      img_data, full_path = _ComputeFractal(
        frm,
        width,
        height,
        count,
        zoom_tm,
        img_output_path,
        img_use_date,
        img_use_hash,
        img_path_prefix,
        pal,
        set_pal,
        color_set_points,
        max_threads,
        iterm,
        print_comm,
      )
      # get AI verdict
      print_comm('')
      print_comm('Press [bold][red]Ctrl+C[/][/] to stop at any time.')
      # input direction from user: 1..9 only
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
          image.META_LLM_MODEL_VALUE_HUMAN,
          0.0,  # will be ignored
          0,  # will be ignored
          False,  # will be ignored
          0,  # will be ignored
          '',  # will be ignored
          '',  # will be ignored
          None,  # will be ignored
          count,
        )
      )
      # implement the move command
      frm = _MoveCenter(frm, None, response, tmr, 0.0, print_comm)
      # stop if we've reached the maximum number of steps
      if max_steps and count >= max_steps:
        print_comm('[yellow]Reached maximum zoom step(s), stopping.[/yellow]')
        break
  # we're out of the main loop
  except KeyboardInterrupt:
    print_comm(f'\n[yellow]Interrupted by user on step {count}.[/yellow]')
  print_comm(f'\nZoom session ended: {count - 1} step(s) completed, last frame: {frm}\n')


def _ComputeFractal(
  frm: frame.Frame,
  width: int,
  height: int,
  count: int,
  zoom_tm: int,
  img_output_path: pathlib.Path | None,
  img_use_date: bool,
  img_use_hash: bool,
  img_path_prefix: str,
  pal: palette.Palette,
  set_pal: palette.Palette,
  color_set_points: bool,
  max_threads: int | None,
  iterm: bool,
  print_comm: abc.Callable[[str], None],
) -> tuple[bytes, pathlib.Path]:
  """Compute the Mandelbrot or Julia image for the given frame.

  Args:
    frm: The frame for which to compute the Mandelbrot or Julia image.
    width: The width of the image to render.
    height: The height of the image to render.
    count: The current zoom step count, used for logging and image naming.
    zoom_tm: The timestamp when the zoom session started, used for logging and image naming.
    img_output_path: Optional path to save the rendered image; if None, the image will not be
        saved to disk.
    img_use_date: Whether to include the current date in the image filename when saving.
    img_use_hash: Whether to include the image hash in the filename when saving.
    img_path_prefix: A prefix to add to the image filename when saving.
    pal: The color palette to use for rendering the image.
    set_pal: The color palette to use for interior Set points.
    color_set_points: If True, color the interior Set points with `set_pal` instead of black.
    max_threads: Maximum number of threads to use for rendering.
    iterm: Whether to print the image inline in iTerm2 using the iTerm2 inline image protocol.
    print_comm: A rich console callable for printing messages.

  Returns:
    (bytes, pathlib.Path): A tuple with the PNG image bytes (minus the evaluation) and the
        intended save path (not yet saved!)

  """
  img_data: bytes
  img_hash: str
  magnification: gmpy2.mpfr
  magnitude: float
  # calculate magnification
  magnification, magnitude = frm.magnification
  magnification_str: str = (
    # beyond 10^21, use scientific notation
    human.HumanizedDecimal(float(magnification)) if magnitude < 21 else f'{magnification:e}'  # noqa: PLR2004
  )
  # render the image for the current frame
  with timer.Timer(emit_log=False) as tmr:
    img: image.Image = {
      frame.Fractal.MANDELBROT: fractal.Mandelbrot,
      frame.Fractal.JULIA: fractal.Julia,
    }[frm.fractal](
      frm,  # type: ignore[arg-type]  # we know this should be fine
      width,
      height,
      max_iter=None,
      progress_bar=True,
      n_processes=max_threads,
      print_comm=print_comm,
    )
    # get PNG and overlay info on top of it
    img_data, img_hash = img.AsPNG(pal=pal, set_pal=set_pal, color_set_points=color_set_points)
    img_data = image.DrawThirdsInfoOverlay(img_data)
  # log!
  full_path: pathlib.Path = image.MakeImagePath(
    img_output_path,
    img_use_date,
    img_use_hash,
    img_path_prefix,
    img_hash,
    tm=zoom_tm,
    add_serial=count,
  )
  print_comm(
    f'\n{frm.fractal.value.capitalize()} zoom (#{count}) '
    f'with frame {frm}, precision {img.precision} bits, {magnification_str} magnification\n'
    f'{img_hash!r} in {tmr}, escape range {img.escape_range}, will save as "{full_path}"'
  )
  if iterm:
    print_comm('')
    image.PrintITerm2(img_data)
  return (img_data, full_path)


def _MoveCenter(  # noqa: C901, PLR0912
  frm: frame.Frame,
  query: str | None,
  response: queries.ZoomSectorScoring | queries.ZoomSectorCompleteScoring,
  tmr: timer.Timer,
  target_weight: float,
  print_comm: abc.Callable[[str], None],
) -> frame.Frame:
  """Move the frame center according to the AI response.

  Args:
    frm: The current frame.
    query: The optional search query used for targeted scoring.
    response: The AI response containing the sector evaluations.
    tmr: The timer for the current operation.
    target_weight: The weight (0.0 to 1.0) to give to the target match score when determining the
        best sector; if 0.0, only the fractal score is used; if 1.0, only the
        target match score is used.
    print_comm: A rich console callable for printing messages.

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
  print_comm('')
  # build the new frame
  if isinstance(frm, frame.FrameAndPoint):
    return frame.FrameAndPoint.FromCenterAndPoint(
      frm.fractal,
      frm.point_re,
      frm.point_im,
      center_mpq_re,
      center_mpq_im,
      frame_width / frame.DEFAULT_MPQ_ZOOM,
      frame_height / frame.DEFAULT_MPQ_ZOOM,
    )
  return frame.Frame.FromCenter(
    frm.fractal,
    center_mpq_re,
    center_mpq_im,
    frame_width / frame.DEFAULT_MPQ_ZOOM,
    frame_height / frame.DEFAULT_MPQ_ZOOM,
  )
