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

from . import __version__


@dataclasses.dataclass(kw_only=True, slots=True, frozen=True)
class TranZoomAIConfig(base.TranZoomConfig):
  """TranZoom AI context, storing the configuration."""

  model: str
  spec_tokens: int | None
  seed: int | None
  context: int
  temperature: float
  gpu: float
  gpu_layers: int
  fp16: bool
  use_mmap: bool
  flash: bool
  kv_cache: int | None
  timeout: float


# CLI app setup, this is an important object and can be imported elsewhere and called
app = typer.Typer(
  add_completion=True,
  no_args_is_help=True,
  help='TranZoom will do things!',  # keep in sync with Main() app.callback help
  # TODO: add epilog and actual help
)


def Run() -> None:
  """Run the CLI."""
  app()


@app.callback(
  invoke_without_command=True,
  help='TranZoom will do things!',  # keep in sync with app help
  # TODO: add actual help
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
  img_output_path: pathlib.Path | None = base.IMAGE_PATH_OUTPUT_OPTION,  # type: ignore[assignment]
  img_path_prefix: str = base.IMAGE_PREFIX_OPTION,  # type: ignore[assignment]
  img_use_date: bool = base.IMAGE_INCLUDE_DATE_OPTION,  # type: ignore[assignment]
  img_use_hash: bool = base.IMAGE_INCLUDE_HASH_OPTION,  # type: ignore[assignment]
  max_threads: int | None = base.MAX_THREADS_OPTION,  # type: ignore[assignment]
  # AI parameters from transai:
  model: str = transai.MODEL_OPTION,  # type: ignore[assignment]
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
  ctx.obj = TranZoomAIConfig(
    console=console,
    verbose=verbose,
    color=color,
    appconfig=app_config.InitConfig('tranzoom', 'config.bin'),
    img_width=512,  # fixed!
    img_height=512,  # and square!
    img_output_path=None if img_output_path is None else img_output_path.expanduser().resolve(),
    img_path_prefix=img_path_prefix,
    img_use_date=img_use_date,
    img_use_hash=img_use_hash,
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
  )
  # even though this is a convenient place to print(), beware that this runs even when
  # a subcommand is invoked; so prefer logging.debug/info/warning/error instead of print();
  # for example, if you run `markdown` subcommand, this will still print and spoil the output


@app.command(
  'markdown',
  help='Emit Markdown docs for the CLI (see README.md section "Versioning and releases").',
  epilog=('Example:\n\n\n\n$ poetry run zoom markdown > zoom.md\n\n<<saves CLI doc>>'),
)
@clibase.CLIErrorGuard
def Markdown(*, ctx: click.Context) -> None:  # documentation is help/epilog/args # noqa: D103
  config: TranZoomAIConfig = ctx.obj
  config.console.print(clibase.GenerateTyperHelpMarkdown(app, prog_name='zoom'))


# Import CLI modules to register their commands with the app
from tranzoom.cli import aicommand  # pyright: ignore[reportUnusedImport] # noqa: E402, F401
