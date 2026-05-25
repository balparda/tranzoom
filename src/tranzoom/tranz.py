# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Entry point for the TranZoom Mandelbrot zoom renderer."""

from __future__ import annotations

import dataclasses
import pathlib

import click
import typer
from rich import console as rich_console
from transai import transai
from transcrypto.cli import clibase
from transcrypto.utils import config as app_config
from transcrypto.utils import logging as cli_logging

from tranzoom.cli import base
from tranzoom.core import frame, palette

from . import __app__, __version__

# CLI app setup, this is an important object and can be imported elsewhere and called
app = typer.Typer(
  add_completion=True,
  no_args_is_help=True,
  # keep in sync with Main() app.callback help
  help=f'{__app__}: Fractal (Mandelbrot/Julia) image and zoom generator, with LLM-powered features',
  epilog=(
    'Examples:\n\n\n\n'
    '# --- Mandelbrot Image Generation ---\n\n'
    'poetry run tranz image mandel\n\n'
    'poetry run tranz image -w 512 -h 512 mandel " -0.74303" "0.126433" "0.01611"  '
    '# note the space because of the "-"\n\n\n\n'
    '# --- Julia Set Image Generation ---\n\n'
    'poetry run tranz image julia\n\n'
    'poetry run tranz -s 1024 image julia "13667/50000" "371/50000" '
    '" -313420497/429687500" "0.6567" "0.00544" "0.004"\n\n'
    'poetry run tranz image julia "/path/to/julia_point_image.png" "" '
    '"/path/to/frame_image.png"\n\n\n\n'
    '# --- TranZoom Fractal Image Data Reading / Visualization ---\n\n'
    'poetry run tranz image read /path/to/image.png\n\n\n\n'
    '# --- LLM-Guided Fractal Zoom ---\n\n'
    'poetry run tranz zoom ai\n\n'
    'poetry run tranz -m "qwen3-vl-32b-instruct@q8_0" -x 0.7 zoom -n 10 ai '
    '" -0.7436499" "0.13188204" "0.00073801"\n\n'
    'poetry run tranz --iterm zoom ai "/path/to/image.png"\n\n'
    'poetry run tranz --iterm zoom -s 700 --fractal julia ai\n\n\n\n'
    '# --- Human/Manual-Guided Fractal Zoom ---\n\n'
    'poetry run tranz --iterm zoom manual " -0.74303" "0.126433" "0.01611"\n\n'
    'poetry run tranz zoom manual "/path/to/image.png"\n\n'
    'poetry run tranz --iterm zoom -s 700 --fractal julia manual\n\n\n\n'
    '# --- Auto Fractal Zoom: Make Video ---\n\n'
    'poetry run tranz zoom -s 256 auto --fps 10 --duration 2\n\n'
    'poetry run tranz zoom auto " -5578776469/7500000000" "8244620127/62500000000" '
    '"0.00073801" "0.00073801" "2.1" --fps 10 --duration 15\n\n\n\n'
    '# --- Get/Set Config Values ---\n\n'
    'poetry run tranz config get\n\n'
    'poetry run tranz config set use_db true\n\n'
    'poetry run tranz config set foo bar  # (example made up key)\n\n\n\n'
    '# --- Markdown Help ---\n\n'
    'poetry run tranz markdown > tranz.md'
  ),
)


def Run() -> None:
  """Run the CLI."""
  app()


@app.callback(
  invoke_without_command=True,
  # keep in sync with app help
  help=f'{__app__}: Fractal (Mandelbrot/Julia) image and zoom generator, with LLM-powered features',
)  # have only one; this is the "constructor"
@clibase.CLIErrorGuard
def Main(  # documentation is help/epilog/args # noqa: D103
  *,
  ctx: click.Context,  # global context
  version: bool = typer.Option(False, '--version', help='Show version and exit.'),
  verbose: int = typer.Option(
    0,
    '-v',
    '--verbose',
    count=True,
    help='Verbosity (nothing=ERROR, -v=WARNING, -vv=INFO, -vvv=DEBUG).',
    min=0,
    max=3,
  ),
  color: bool | None = typer.Option(
    None,
    '--color/--no-color',
    help=(
      'Force enable/disable colored output (respects NO_COLOR env var if not provided). '
      'Defaults to having colors.'  # state default because None default means docs don't show it
    ),
  ),
  db: bool | None = base.USE_DB_OPTION,  # type: ignore[assignment]
  db_path: pathlib.Path | None = base.DB_PATH_OPTION,  # type: ignore[assignment]
  db_compress: bool | None = base.USE_DB_COMPRESSION_OPTION,  # type: ignore[assignment]
  img_output_path: pathlib.Path | None = base.IMAGE_PATH_OUTPUT_OPTION,  # type: ignore[assignment]
  img_path_prefix: str | None = base.IMAGE_PREFIX_OPTION,  # type: ignore[assignment]
  img_use_date: bool = base.IMAGE_INCLUDE_DATE_OPTION,  # type: ignore[assignment]
  img_use_hash: bool = base.IMAGE_INCLUDE_HASH_OPTION,  # type: ignore[assignment]
  img_force_redo: bool = base.IMAGE_FORCE_REDO_OPTION,  # type: ignore[assignment]
  pal: palette.Palette = base.PALETTE_OPTION,  # type: ignore[assignment]
  set_pal: palette.Palette = base.SET_PALETTE_OPTION,  # type: ignore[assignment]
  set_points: frame.SetHighlightAlgorithm | None = base.COLOR_SET_POINTS_OPTION,  # type: ignore[assignment]
  max_threads: int | None = base.MAX_THREADS_OPTION,  # type: ignore[assignment]
  # AI parameters from transai (EXCEPT model which is overridden to be a vision model!):
  model: str = base.MODEL_OPTION,  # type: ignore[assignment]
  spec_tokens: int | None = transai.SPEC_TOKENS_OPTION,  # type: ignore[assignment]
  seed: int | None = transai.SEED_OPTION,  # type: ignore[assignment]
  context: int = transai.CONTEXT_OPTION,  # type: ignore[assignment]
  temperature: float = transai.TEMPERATURE_OPTION,  # type: ignore[assignment]
  gpu: float = transai.GPU_OPTION,  # type: ignore[assignment]
  gpu_layers: int = transai.GPU_LAYERS_OPTION,  # type: ignore[assignment]
  fp16: bool = transai.FP16_OPTION,  # type: ignore[assignment]
  use_mmap: bool = transai.USE_MMAP_OPTION,  # type: ignore[assignment]
  flash: bool = transai.FLASH_OPTION,  # type: ignore[assignment]
  kv_cache: int | None = transai.KV_CACHE_OPTION,  # type: ignore[assignment]
  timeout: float = transai.TIMEOUT_OPTION,  # type: ignore[assignment]
  # MacOS/iTerm2 image printing
  iterm: bool = base.IMAGE_PRINT_ITERM_OPTION,  # type: ignore[assignment]
) -> None:
  if version:
    typer.echo(__version__)
    raise typer.Exit(0)
  console: rich_console.Console
  console, verbose, color = cli_logging.InitLogging(
    verbose,
    color=color,
    include_process=False,  # decide if you want process names in logs
    soft_wrap=False,  # decide if you want soft wrapping of long lines
  )
  # create context with the arguments we received
  appconfig: app_config.AppConfig = app_config.InitConfig(  # this always has the path
    __app__, 'config.bin', fixed_dir=None if db_path is None else db_path.expanduser().resolve()
  )
  tzc: base.TranZoomConfig = base.TranZoomConfig(
    console=console,
    verbose=verbose,
    color=color,
    appconfig=appconfig,
    img_output_path=None if img_output_path is None else img_output_path.expanduser().resolve(),
    img_path_prefix=img_path_prefix,
    img_use_date=img_use_date,
    img_use_hash=img_use_hash,
    img_force_redo=img_force_redo,
    db_read_only=False,  # sentinel only: will load from config below!
    db_compress=False,  # sentinel only: will load from config below!
    pal=pal,
    set_pal=set_pal,
    set_points=set_points,
    max_threads=max_threads,
    model=model,
    spec_tokens=spec_tokens,
    seed=seed,
    context=context,
    temperature=temperature,
    gpu=gpu,
    gpu_layers=gpu_layers,
    fp16=fp16,
    use_mmap=use_mmap,
    flash=flash,
    kv_cache=kv_cache,
    timeout=timeout,
    iterm=iterm,
  )
  # open config and update the config values
  cnf: base.ConfigType = tzc.GetConfig()
  ctx.obj = dataclasses.replace(
    tzc,
    # config values should have "None" to mean override the config!
    db_read_only=(not cnf['use_db']) if db is None else db,  # INVERT!
    db_compress=cnf['db_compression'] if db_compress is None else db_compress,
  )
  # even though this is a convenient place to print(), beware that this runs even when
  # a subcommand is invoked; so prefer logging.debug/info/warning/error instead of print();
  # for example, if you run `markdown` subcommand, this will still print and spoil the output


# Import CLI modules to register their commands with the app -- keep import order
from tranzoom.cli import (  # noqa: E402, I001
  imagecommand,  # pyright: ignore[reportUnusedImport] # noqa: F401
  zoomcommand,  # pyright: ignore[reportUnusedImport] # noqa: F401
  configcommand,  # pyright: ignore[reportUnusedImport] # noqa: F401
)


@app.command(
  'markdown',
  help='Emit Markdown docs for the CLI (see README.md section "Versioning and releases").',
  epilog=('Example:\n\n\n\n$ poetry run tranz markdown > tranz.md\n\n<<saves CLI doc>>'),
)
@clibase.CLIErrorGuard
def Markdown(*, ctx: click.Context) -> None:  # documentation is help/epilog/args # noqa: D103
  config: base.TranZoomConfig = ctx.obj
  config.console.print(clibase.GenerateTyperHelpMarkdown(app, prog_name='tranz'))
