# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: mycli.py."""

from __future__ import annotations

from unittest import mock

import click
import pytest
import typer
from click import testing as click_testing
from transcrypto.utils import config as app_config
from transcrypto.utils import logging as cli_logging
from typer import testing

from tranzoom import zoom


@pytest.fixture(autouse=True)
def reset_cli() -> None:
  """Reset CLI singleton before each test."""
  cli_logging.ResetConsole()
  app_config.ResetConfig()


def CallCLI(args: list[str]) -> click_testing.Result:
  """Call the CLI with args.

  Args:
      args (list[str]): CLI arguments.

  Returns:
      click_testing.Result: CLI result.

  """
  return testing.CliRunner().invoke(zoom.app, args)


def PrintedValue(console_mock: mock.Mock) -> object:
  """Return first argument passed to console.print(...).

  Args:
      console_mock (mock.Mock): console mock.

  Returns:
      object: first argument passed to console.print(...).

  """
  # console.print is a Mock; .call_args is (args, kwargs)
  args, _kwargs = console_mock.print.call_args
  return args[0] if args else None


def test_version_flag() -> None:
  """Test."""
  result: click_testing.Result = CallCLI(['--version'])
  assert result.exit_code == 0
  assert '.' in result.stdout


def test_version_flag_raises_exit() -> None:
  """Test version flag raises typer.Exit with exit code 0."""
  ctx = mock.Mock(spec=click.Context)
  with pytest.raises(typer.Exit) as exc_info:
    zoom.Main(
      ctx=ctx,
      version=True,
      verbose=0,
      color=None,
      img_width=1000,
      img_height=1000,
      img_output_path=None,
      img_use_date=True,
    )
  assert exc_info.value.exit_code == 0


def test_run_function() -> None:
  """Test Run function calls app."""
  with mock.patch.object(zoom, 'app') as app_mock:
    zoom.Run()
    app_mock.assert_called_once()


def test_version_flag_ignores_extra_args() -> None:
  """Test."""
  result: click_testing.Result = CallCLI(['--version', 'image'])
  assert result.exit_code == 0
  assert '.' in result.stdout


def test_markdown_command_generates_docs() -> None:
  """Test markdown command generates documentation."""
  result: click_testing.Result = CallCLI(['markdown'])
  assert result.exit_code == 0, result.output
  # Verify it contains markdown-like content
  assert 'zoom' in result.stdout
  assert '#' in result.stdout  # markdown headers
  assert '<!--' in result.stdout  # top comment
  assert 'image' in result.stdout and 'zoom' in result.stdout  # verify it includes subcommands
