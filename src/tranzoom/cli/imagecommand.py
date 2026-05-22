# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""CLI: Fractal image utils command.

<https://en.wikipedia.org/wiki/Mandelbrot_set>
<https://en.wikipedia.org/wiki/Julia_set>

README.md has good examples for different zoom levels.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import click
import gmpy2
import typer
from transcrypto.cli import clibase

from tranzoom import tranz
from tranzoom.cli import base
from tranzoom.core import frame, image

image_app = typer.Typer(
  no_args_is_help=True,
  help=(
    'Examples:\n\n\n\n'
    '# --- Mandelbrot Set Image Generation ---\n'
    'poetry run tranz image mandel\n'
    'poetry run tranz image -w 512 -h 512 mandel " -0.74303" "0.126433" "0.01611"  '
    '# note the space because of the "-"\n\n'
    '# --- Julia Set Image Generation ---\n'
    'poetry run tranz image julia\n'
    'poetry run tranz -s 1024 image julia "13667/50000" "371/50000" '
    '" -313420497/429687500" "0.6567" "0.00544" "0.004"\n'
    'poetry run tranz image julia "/path/to/julia_point_image.png" "" '
    '"/path/to/frame_image.png"\n\n'
    '# --- TranZoom Fractal Image Data Reading / Visualization ---\n'
    'poetry run tranz image read /path/to/image.png'
  ),
)
tranz.app.add_typer(image_app, name='image')


@image_app.callback(invoke_without_command=True)
@clibase.CLIErrorGuard
def ImageOptions(  # documentation is in help/epilog  # noqa: D103
  *,
  ctx: click.Context,
  # note that these are the image options, with default of 1024x1024
  img_width: int = base.IMAGE_WIDTH_OPTION,  # type: ignore[assignment]
  img_height: int = base.IMAGE_HEIGHT_OPTION,  # type: ignore[assignment]
  img_size: int | None = base.IMAGE_SIZE_OPTION,  # type: ignore[assignment]
  max_iter: int | None = base.MAX_ITERATIONS_OPTION,  # type: ignore[assignment]
  mark_coords: str | None = base.MARK_COORDINATES_OPTION,  # type: ignore[assignment]
  mark_color: str = base.MARK_COLOR_OPTION,  # type: ignore[assignment]
  mark_width: int = base.MARK_WIDTH_OPTION,  # type: ignore[assignment]
) -> None:
  # store this command's options in the shared config so all sub-commands can read it
  if ctx.invoked_subcommand is not None and ctx.obj is not None:
    # check color so it won't raise plain KeyError
    col: str = mark_color.strip().upper()
    if col not in image.Color.__members__:
      raise click.ClickException(
        f'Invalid mark color {mark_color!r}; available colors: '
        + ', '.join(sorted(repr(c.name.lower()) for c in image.Color))
      )
    ctx.obj = dataclasses.replace(
      ctx.obj,
      img_width=img_width,
      img_height=img_height,
      img_size=img_size,
      max_iter=max_iter,
      mark_coords=mark_coords,
      mark_color=image.Color[col],
      mark_width=mark_width,
    )


@image_app.command(
  'mandel',
  help='Generate a Mandelbrot image.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run tranz image mandel\n\n'
    '1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...\n\n'
    '...\n\n'
    'Saved to "mandel-<date>-<hash>.png"\n\n\n\n'
    '$ poetry run tranz image -w 512 -h 512 mandel " -0.74303" "0.126433" "0.01611"  '
    '# note the space because of the "-"\n\n'
    '<saves Mandelbrot to disk with center -0.74303+0.126433j and width 0.01611>\n\n\n\n'
    '$ poetry run tranz image mandel "/path/to/image.png"\n\n'
    '<gets the same frame used in "/path/to/image.png" and saves a new image of it to disk>'
  ),
)
@clibase.CLIErrorGuard
def Mandel(  # documentation is help/epilog/args  # noqa: D103
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
  # we have the frame, now feed it to the producer
  base.ProduceFractalImage(frm, config)


@image_app.command(
  'julia',
  help='Generate a Julia image.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run tranz image julia\n\n'
    '1024x1024 Julia in frame [(0, 0) ± (9/5, 11/5) @ (13667/50000, 371/50000)] ...\n\n'
    '...\n\n'
    'Saved to "julia-<date>-<hash>.png"\n\n\n\n'
    '$ poetry run tranz -s 1024 image julia "13667/50000" "371/50000" '
    '" -313420497/429687500" "0.6567" "0.00544" "0.004"\n\n'
    '<saves 1024px Julia to disk with center -313420497/429687500+0.6567j '
    'and width 0.6567 by 0.004>\n\n\n\n'
    '$ poetry run tranz image julia "/path/to/julia_point_image.png" "" '
    '"/path/to/frame_image.png"\n\n'
    '<gets the same frame used in "frame_image.png" and saves a new image '
    'using "julia_point_image.png" Julia point>'
  ),
)
@clibase.CLIErrorGuard
def Julia(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  point_re: str = base.JULIA_RE_ARGUMENT,  # type: ignore[assignment]
  point_im: str = base.JULIA_IM_ARGUMENT,  # type: ignore[assignment]
  center_re: str = base.JULIA_CENTER_RE_ARGUMENT,  # type: ignore[assignment]
  center_im: str = base.JULIA_CENTER_IM_ARGUMENT,  # type: ignore[assignment]
  f_width: str = base.JULIA_WIDTH_ARGUMENT,  # type: ignore[assignment]
  f_height: str | None = base.JULIA_HEIGHT_ARGUMENT,  # type: ignore[assignment]
) -> None:
  # check sanity, create frame, and print info about the image we're going to generate
  config: base.TranZoomConfig = ctx.obj
  frm: frame.Frame = base.MakeFrameFromCLIArgs(  # remember: this will read from file too...
    frame.Fractal.JULIA, center_re, center_im, f_width, f_height, config.console.print
  )
  # load Julia point and make frame
  julia_re: gmpy2.mpq
  julia_im: gmpy2.mpq
  julia_re, julia_im = base.MakePointFromCLIArgs(point_re, point_im, config.console.print)
  frm = frame.Frame.FromCenter(
    frame.Fractal.JULIA,
    *frm.center,
    frm.size[0],
    height=frm.size[1],
    point_re=julia_re,
    point_im=julia_im,
  )
  # we have the frame, now feed it to the producer
  base.ProduceFractalImage(frm, config)


@image_app.command(
  'read',
  help='Read a TranZoom fractal image.',
  epilog=(
    'Examples:\n\n\n\n'
    '$ poetry run tranz image read /path/to/image.png\n\n'
    '1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2] ...\n\n'
    '...'
  ),
)
@clibase.CLIErrorGuard
def Read(  # documentation is help/epilog/args  # noqa: D103
  *,
  ctx: click.Context,
  image_path: pathlib.Path = base.IMAGE_PATH_INPUT_ARGUMENT,  # type: ignore[assignment]
) -> None:
  config: base.TranZoomConfig = ctx.obj
  # read image
  image_path = image_path.expanduser().resolve()
  image_data: bytes = image_path.read_bytes()
  w, h, png_hash, info = image.GetBasicDataFromImage(image_data)
  # print header
  config.console.print()
  config.console.print(f'[yellow]{str(image_path)!r}[/yellow]')
  config.console.print(f'[green]{w}x{h}[/green] (wxh) / [cyan]{png_hash}[/cyan]')
  config.console.print()
  # expand JSON, if needed
  if image.META_LLM_RESULT_JSON_KEY in info:
    info[image.META_LLM_RESULT_JSON_KEY] = json.loads(str(info[image.META_LLM_RESULT_JSON_KEY]))
  # print the metadata in a nice format
  config.console.print_json(data=info, indent=2)
  config.console.print()
  # iterm
  if config.iterm:
    image.PrintITerm2(image_data)
    config.console.print()
