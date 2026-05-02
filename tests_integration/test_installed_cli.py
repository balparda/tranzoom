# SPDX-FileCopyrightText: Copyright 2026 Daniel Balparda
# SPDX-License-Identifier: Apache-2.0

"""Integration tests: build wheel, install into a fresh venv, run the installed CLI.

Why this exists (vs normal unit tests):
- Unit tests (CliRunner) validate CLI wiring while running from the source tree.
- This test validates *packaging*: the wheel builds, installs, and the console script works.

What we verify:
- `mycli --version` prints the expected version.
- `mycli --no-color hello Ada` runs successfully and produces non-ANSI output.
"""

from __future__ import annotations

import pathlib
import shutil

import pytest
from transcrypto.utils import base, config

import mycli

_APP_NAME: str = 'mycli'  # this is the directory name, the package name  # TODO: change
_APP_NAMES: set[str] = {'mycli'}  # this is the console scripts names  # TODO: change


@pytest.mark.integration
def test_installed_cli_smoke(tmp_path: pathlib.Path) -> None:
  """Build wheel, install into a clean venv, run the installed CLIs."""
  repo_root: pathlib.Path = pathlib.Path(__file__).resolve().parents[1]
  expected_version: str = mycli.__version__
  vpy, bin_dir = config.EnsureAndInstallWheel(repo_root, tmp_path, expected_version, _APP_NAMES)
  cli_paths: dict[str, pathlib.Path] = config.EnsureConsoleScriptsPrintExpectedVersion(
    vpy, bin_dir, expected_version, _APP_NAMES
  )
  # basic command smoke tests
  data_dir: pathlib.Path = config.CallGetConfigDirFromVEnv(vpy, _APP_NAME)
  _hello_call(cli_paths, data_dir)  # TODO: change


def _hello_call(cli_paths: dict[str, pathlib.Path], data_dir: pathlib.Path) -> None:
  try:  # type: ignore[unreachable]
    # basic command smoke test; use --no-color to avoid ANSI codes in asserts.
    r = base.Run([str(cli_paths['mycli']), '--no-color', 'hello', 'Ada'])  # TODO: change
    assert 'Hello, Ada!' in r.stdout
    assert '\x1b[' not in r.stdout  # no ANSI escape sequences
    assert '\x1b[' not in r.stderr
  finally:
    shutil.rmtree(data_dir)  # remove created data to isolate the next CLI's read step
