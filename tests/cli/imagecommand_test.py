# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: mycli.py."""

from __future__ import annotations

from unittest import mock

import pytest
from click import testing as click_testing
from transcrypto.utils import config as app_config
from transcrypto.utils import logging as cli_logging

from tests import zoom_test


@pytest.fixture(autouse=True)
def reset_cli() -> None:
  """Reset CLI singleton before each test."""
  cli_logging.ResetConsole()
  app_config.ResetConfig()


@pytest.mark.parametrize(
  ('min_', 'max_'),
  [
    (1, 0),
    (10, 9),
    (0, -1),
  ],
)
@mock.patch('transcrypto.utils.saferandom.secrets.randbelow')
@mock.patch('transcrypto.utils.logging.rich_console.Console')
def test_random_num_rejects_invalid_range(
  console_factory_mock: mock.Mock,
  randbelow_mock: mock.Mock,
  min_: int,
  max_: int,
) -> None:
  """Test.

  Didactic notes:
  - When max < min, your command raises typer.BadParameter.
  - CliRunner captures that and returns a non-zero exit code.
  - In this failure path, randbelow should never be called and we should not print anything.
  """
  console_factory_mock.return_value = mock.Mock()
  result: click_testing.Result = zoom_test.CallCLI(
    ['random', 'num', '--min', str(min_), '--max', str(max_)],
  )
  assert result.exit_code != 0
  randbelow_mock.assert_not_called()


# -------------------------------------------------------------------------------------------------
# random str
# -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
  ('length', 'choices', 'expected'),
  [
    # simplest case: 1 character
    pytest.param(1, ['A'], 'A', id='only As'),
    # multiple characters: join of choices in order
    pytest.param(4, ['a', 'b', 'c', 'd'], 'abcd', id='a to d'),  # <== you can name test cases!!
    # length 8
    pytest.param(8, list('ABCDEFGH'), 'ABCDEFGH', id='A to H'),
  ],
)
@mock.patch('tranzoom.core.example.secrets.choice')
@mock.patch('transcrypto.utils.logging.rich_console.Console')
def test_random_str_default_alphabet_prints_expected(
  console_factory_mock: mock.Mock,
  choice_mock: mock.Mock,
  length: int,
  choices: list[str],
  expected: str,
) -> None:
  """Test.

  Didactic notes:
  - RandomStr uses secrets.choice(chars) inside a generator expression.
  - We patch secrets.choice and provide a side_effect list so each call returns a known char.
  - We still run through the CLI to verify command registration and argument parsing.
  """
  console = mock.Mock()
  console_factory_mock.return_value = console
  # Each call to secrets.choice returns the next item from choices
  choice_mock.side_effect = choices
  result: click_testing.Result = zoom_test.CallCLI(['random', 'str', '--length', str(length)])
  assert result.exit_code == 0, result.output
  # We should call choice exactly 'length' times
  assert choice_mock.call_count == length
  # For default alphabet, RandomStr uses ascii_letters + digits
  # We don't need to replicate that exact string here; instead we assert:
  # - choice was called with a string
  # - and it's the same object each time (the same alphabet)
  first_call_arg = choice_mock.call_args_list[0][0][0]
  assert isinstance(first_call_arg, str)
  for call in choice_mock.call_args_list:
    assert call[0][0] == first_call_arg
  console.print.assert_called_once()
  zoom_test.AssertRandomStrPrintedValue(zoom_test.PrintedValue(console), expected)
