# SPDX-FileCopyrightText: Copyright 2026 Daniel Balparda <balparda@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: mycli.py."""

from __future__ import annotations

import pathlib
from unittest import mock

import click
import pytest
import typer
from click import testing as click_testing
from transcrypto.utils import config as app_config
from transcrypto.utils import logging as cli_logging
from typer import testing

from mycli import mycli


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
  return testing.CliRunner().invoke(mycli.app, args)


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


def AssertRandomStrPrintedValue(printed: object, expected_prefix: str) -> None:
  """Assert RandomStr output matches CLI behavior.

  RandomStr prints the generated string plus a suffix that depends on whether color is enabled.
  We don't want tests to depend on NO_COLOR env var or rich console internals, so accept either.
  """
  assert isinstance(printed, str)
  assert printed.startswith(expected_prefix)
  suffix: str = printed[len(expected_prefix) :]
  assert suffix in {' - in color', ' - no colors'}


def test_version_flag() -> None:
  """Test."""
  result: click_testing.Result = CallCLI(['--version'])
  assert result.exit_code == 0
  assert result.stdout.strip() == '0.1.0'


def test_version_flag_raises_exit() -> None:
  """Test version flag raises typer.Exit with exit code 0."""
  ctx = mock.Mock(spec=click.Context)
  with pytest.raises(typer.Exit) as exc_info:
    mycli.Main(ctx=ctx, version=True, verbose=0, color=None, foo=1000, bar='str default')
  assert exc_info.value.exit_code == 0


def test_run_function() -> None:
  """Test Run function calls app."""
  with mock.patch.object(mycli, 'app') as app_mock:
    mycli.Run()
    app_mock.assert_called_once()


def test_version_flag_ignores_extra_args() -> None:
  """Test."""
  result: click_testing.Result = CallCLI(['--version', 'hello'])
  assert result.exit_code == 0
  assert result.stdout.strip() == '0.1.0'


def test_hello_default_name() -> None:
  """Test."""
  result: click_testing.Result = CallCLI(['hello'])
  assert result.exit_code == 0
  assert 'Hello, World!' in result.stdout


def test_hello_custom_name() -> None:
  """Test."""
  result: click_testing.Result = CallCLI(['hello', 'Ada'])
  assert result.exit_code == 0
  assert 'Hello, Ada!' in result.stdout


@mock.patch('transcrypto.utils.logging.rich_console.Console')
@mock.patch('transcrypto.utils.config.GetConfigDir')
@mock.patch('pathlib.Path.mkdir')
def test_config_path_prints_path(
  mkdir_mock: mock.Mock,
  get_config_path_mock: mock.Mock,
  console_factory_mock: mock.Mock,
) -> None:
  """Test config-path command prints the config path."""
  console = mock.Mock()
  console_factory_mock.return_value = console
  get_config_path_mock.return_value = pathlib.Path('/mock/config/mycli/config')
  result: click_testing.Result = CallCLI(['configpath'])
  assert result.exit_code == 0, result.output
  console.print.assert_called_once_with('/mock/config/mycli/config/mycli.bin')
  mkdir_mock.assert_called_once_with(parents=True, exist_ok=True)


def test_markdown_command_generates_docs() -> None:
  """Test markdown command generates documentation."""
  result: click_testing.Result = CallCLI(['markdown'])
  assert result.exit_code == 0, result.output
  # Verify it contains markdown-like content
  assert 'mycli' in result.stdout
  assert '#' in result.stdout  # markdown headers
  assert '<!--' in result.stdout  # top comment
  assert 'hello' in result.stdout and 'random' in result.stdout  # verify it includes subcommands
