# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0

"""Integration tests: build wheel, install into a fresh venv, run the installed CLI.

Why this exists (vs normal unit tests):
- Unit tests (CliRunner) validate CLI wiring while running from the source tree.
- This test validates *packaging*: the wheel builds, installs, and the console script works.

What we verify:
- `zoom --version` prints the expected version.
- `zoom image` renders a Seahorse Tail image with deterministic output and verifies it
"""

from __future__ import annotations

import pathlib
import shutil
import tempfile

import pytest
from transcrypto.utils import base, config

import tranzoom

_APP_NAME: str = 'tranzoom'  # this is the directory name, the package name
_APP_NAMES: set[str] = {'zoom'}  # this is the console scripts names


@pytest.mark.integration
def test_installed_cli_smoke(tmp_path: pathlib.Path) -> None:
  """Build wheel, install into a clean venv, run the installed CLIs."""
  repo_root: pathlib.Path = pathlib.Path(__file__).resolve().parents[1]
  expected_version: str = tranzoom.__version__
  vpy, bin_dir = config.EnsureAndInstallWheel(repo_root, tmp_path, expected_version, _APP_NAMES)
  cli_paths: dict[str, pathlib.Path] = config.EnsureConsoleScriptsPrintExpectedVersion(
    vpy, bin_dir, expected_version, _APP_NAMES
  )
  # basic command smoke tests
  data_dir: pathlib.Path = config.CallGetConfigDirFromVEnv(vpy, _APP_NAME)
  _SeahorseTailCall(cli_paths, data_dir)


def _SeahorseTailCall(cli_paths: dict[str, pathlib.Path], data_dir: pathlib.Path) -> None:
  try:
    with tempfile.TemporaryDirectory() as tmp_dir:
      # render a Seahorse Tail image; --no-date makes the filename deterministic (hash-only),
      # --out directs output to tmp_dir so we can assert on the exact file produced.
      r = base.Run(
        # call the console script directly to test the installed CLI
        [
          str(cli_paths['zoom']),
          '-w',
          '512',
          '-h',
          '512',
          '--no-date',
          '--out',
          tmp_dir,
          'image',
          ' -0.7436499',
          '0.13188204',
          '0.00073801',
        ]
      )
      assert r.returncode == 0, f'zoom image failed:\n{r.stderr}'
      # we check that the image is the same by trusting the 20-character hash in the file name;
      # the hash is from the internal representation and should only depend on our implementation;
      # resist the temptation of checking the PNG because PIL behaves differently across platforms
      # and Python versions, and we don't want to be debugging PIL differences in this test
      output_image: pathlib.Path = pathlib.Path(tmp_dir) / 'mandel-2537af0ab52a4ec846d1.png'
      assert output_image.exists(), f'Expected output image not found: {output_image}'
  finally:
    shutil.rmtree(data_dir)  # remove created data to isolate the next CLI's read step
