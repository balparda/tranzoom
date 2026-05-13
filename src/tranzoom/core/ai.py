# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""AI core logic."""

from __future__ import annotations

import pathlib
from collections import abc
from typing import cast

import gmpy2
from transai.core import ai, lms
from transcrypto.utils import base as tbase
from transcrypto.utils import human, timer

from tranzoom.core import fractal, frame, image, queries

# TODO: add model options!
_WIDTH: int = 512  # square frames only!
_MEMORY_SIZE: int = 3  # number of iterations the LLM will remember
_MODEL_ID: str = 'qwen3-vl-32b-instruct@q8_0'  # TODO: option
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
  img_output_path: pathlib.Path | None,
  img_use_date: bool,
  img_use_hash: bool,
  img_path_prefix: str,
  max_threads: int | None,
  *,
  max_steps: int = 0,
  iterm: bool = False,
  print_comm: abc.Callable[[str], None] = print,
) -> None:
  """Execute main loop for AI-guided Mandelbrot zoom search.

  Args:
    frm: The initial frame for the Mandelbrot zoom search.
    img_output_path: Optional path to save the rendered images; if None, images will not
        be saved to disk.
    img_use_date: Whether to include the current date in the image filename when saving.
    img_use_hash: Whether to include the image hash in the filename when saving.
    img_path_prefix: A prefix to add to the image filename when saving.
    max_threads: Optional maximum number of threads to use for rendering; if None, use all
        available CPU cores.
    max_steps: Maximum number of zoom steps to run; 0 means run until manually stopped (Ctrl+C);
        default is 0 (unlimited, run forever).
    iterm: Whether to print the image inline in iTerm2 using the iTerm2 inline image protocol;
        default is False.
    print_comm: A callable for printing messages; defaults to the built-in print function.

  """
  # capture the time and load model
  zoom_tm: int = timer.Now()
  print_comm(
    f'Will run for [bold]{max_steps or "[red]∞[/]"}[/] step(s). '
    'Press [bold][red]Ctrl+C[/][/] to stop at any time.'
  )
  print_comm(
    f'[yellow]Loading AI model [bold]{_MODEL_ID}[/]...[/] / {timer.TimeStr(zoom_tm)} ({zoom_tm})\n'
  )
  count: int = 1
  try:
    with lms.LMStudioWorker(free_resources=True) as worker:
      worker.LoadModel(
        ai.MakeAIModelConfig(
          model_id=_MODEL_ID,
          vision=True,
          temperature=0.33,  # TODO: option
          # all other fields will have sensible defaults; currently also supported are:
          # seed, context, gpu_ratio, gpu_layers, use_mmap, fp16, flash, spec_tokens, kv_cache
        )
      )
      # main loop: runs until max_steps is reached, or Ctrl+C is pressed
      json_chat: tbase.JSONDict | None = None
      img_data: bytes
      response: queries.ZoomSectorScoring
      full_path: pathlib.Path
      count = 0
      while True:
        count += 1
        # render the image for the current frame
        img_data, full_path = _ComputeMandelbrot(
          frm,
          count,
          zoom_tm,
          img_output_path,
          img_use_date,
          img_use_hash,
          img_path_prefix,
          max_threads,
          iterm=iterm,
          print_comm=print_comm,
        )
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
        print_comm('')
        print_comm('Press [bold][red]Ctrl+C[/][/] to stop at any time.')
        with timer.Timer(emit_log=False) as tmr:
          response, json_chat = worker.ModelCall(
            _MODEL_ID,
            queries.AI_SETUP_THIRDS_SCORING_PROMPT,
            queries.AI_IMAGE_THIRDS_SCORING_PROMPT,
            queries.ZoomSectorScoring,
            images=[img_data],
            chat_history=json_chat,
          )
        # save the image, adding the response evaluation as metadata on top of the image
        full_path.write_bytes(image.AddEvaluationMetaToImage(img_data, response.JSON()))
        # implement the move command
        frm = _MoveCenter(frm, response, tmr, print_comm=print_comm)
        # stop if we've reached the maximum number of steps
        if max_steps and count >= max_steps:
          print_comm('[yellow]Reached maximum zoom step(s), stopping.[/yellow]')
          break
  # we're out of the main loop
  except KeyboardInterrupt:
    print_comm(f'\n[yellow]Interrupted by user on step {count}.[/yellow]')
  print_comm(f'\nZoom session ended: {count - 1} step(s) completed, last frame: {frm}\n')


def _ComputeMandelbrot(
  frm: frame.Frame,
  count: int,
  zoom_tm: int,
  img_output_path: pathlib.Path | None,
  img_use_date: bool,
  img_use_hash: bool,
  img_path_prefix: str,
  max_threads: int | None,
  *,
  iterm: bool = False,
  print_comm: abc.Callable[[str], None] = print,
) -> tuple[bytes, pathlib.Path]:
  """Compute the Mandelbrot image for the given frame.

  Args:
    frm: The frame for which to compute the Mandelbrot image.
    count: The current zoom step count, used for logging and image naming.
    zoom_tm: The timestamp when the zoom session started, used for logging and image naming.
    img_output_path: Optional path to save the rendered image; if None, the image will not be
        saved to disk.
    img_use_date: Whether to include the current date in the image filename when saving.
    img_use_hash: Whether to include the image hash in the filename when saving.
    img_path_prefix: A prefix to add to the image filename when saving.
    max_threads: Optional maximum number of threads to use for rendering; if None, use all
        available CPU cores.
    iterm: Whether to print the image inline in iTerm2 using the iTerm2 inline image protocol;
        default is False.
    print_comm: A callable for printing messages; defaults to the built-in print function.

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
    img: image.Image = fractal.Mandelbrot(
      frm, _WIDTH, _WIDTH, max_iter=None, progress_bar=True, n_processes=max_threads
    )
    # get PNG and overlay info on top of it
    img_data, img_hash = img.AsPNG()
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
  print_comm(f'Saved to "{full_path}"')
  print_comm(
    f'\nMandelbrot zoom (#{count}) with frame {frm}, '
    f'precision {frm.precision} bits, {magnification_str} magnification\n'
    f'{img_hash!r} in {tmr}, escape range {img.escape_range}, will save as "{full_path}"'
  )
  if iterm:
    print_comm('')
    image.PrintITerm2(img_data)
  return (img_data, full_path)


def _MoveCenter(  # noqa: C901
  frm: frame.Frame,
  response: queries.ZoomSectorScoring,
  tmr: timer.Timer,
  *,
  print_comm: abc.Callable[[str], None] = print,
) -> frame.Frame:
  """Move the frame center according to the AI response.

  Args:
    frm: The current frame.
    response: The AI response containing the sector evaluations.
    tmr: The timer for the current operation.
    print_comm: A callable for printing messages; defaults to the built-in print function.

  Returns:
    frame.Frame: The new frame with the updated center.

  Raises:
    Error: If the AI response contains an invalid sector

  """
  # implement the move command: first the scale of the step
  center_mpq_re: gmpy2.mpq
  center_mpq_im: gmpy2.mpq
  center_mpq_re, center_mpq_im = frm.center
  frame_sz: gmpy2.mpq = frm.size[0]  # only works for square!
  direct_step: gmpy2.mpq = frame_sz * frame.DEFAULT_MPQ_STEP_DIRECT
  diagonal_step: gmpy2.mpq = frame_sz * frame.DEFAULT_MPQ_STEP_DIAGONAL
  # now move the center according to the direction, if requested
  best: queries.SectorEvaluation = response.BestEvaluation()
  direction: str = _DIRECTION_MAP[best.sector]
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
    raise Error(f'invalid direction: {direction!r}')
  print_comm(f'[yellow]MODEL: move [bold]{best.sector}/{direction}-wards[/][/] (in {tmr})')
  for sector_eval in sorted(response.sectors, key=lambda item: item.score, reverse=True):
    print_comm(
      f'#{sector_eval.sector}/[green]{_DIRECTION_MAP[sector_eval.sector]}[/]: '
      f'{sector_eval.score} - {sector_eval.reason}'
    )
  print_comm('')
  # build the new frame
  return frame.Frame.FromCenter(
    frame.Fractal.MANDELBROT, center_mpq_re, center_mpq_im, frame_sz / frame.DEFAULT_MPQ_ZOOM
  )
