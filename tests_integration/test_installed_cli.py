# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0

"""Integration tests: build wheel, install into a fresh venv, run the installed CLI.

Why this exists (vs normal unit tests):
- Unit tests (CliRunner) validate CLI wiring while running from the source tree.
- This test validates *packaging*: the wheel builds, installs, and the console script works.

What we verify:
- `mandel --version` prints the expected version.
- `mandel gen` renders a Seahorse Tail image with deterministic output and verifies it
- `zoom --version` prints the expected version.
"""

from __future__ import annotations

import pathlib
import shutil
import tempfile

import pytest
from transcrypto.utils import base as tbase
from transcrypto.utils import config

import tranzoom
from tranzoom.cli import base
from tranzoom.core import image

_APP_NAME: str = 'tranzoom'  # this is the directory name, the package name
_APP_NAMES: set[str] = {'tranz'}  # this is the console scripts names


@pytest.mark.slow
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
  _MandelbrotSeahorseTailCall(cli_paths, data_dir)
  _JuliaSuzanaWaveCall(cli_paths, data_dir)


def _MandelbrotSeahorseTailCall(cli_paths: dict[str, pathlib.Path], data_dir: pathlib.Path) -> None:
  """Call the installed CLI to render the Seahorse Tail image, check the output file and metadata.

  Should be 100% equivalent to the `scripts/make_examples.sh` line to "Render Seahorse Tail".
  """
  try:
    with tempfile.TemporaryDirectory() as tmp_dir:
      # render a Seahorse Tail image
      r = tbase.Run(
        # call the console script directly to test the installed CLI
        [
          str(cli_paths['tranz']),
          '--no-date',  # --no-date makes the filename deterministic (hash-only)
          '--out',  # --out directs output to tmp_dir so we can assert on the exact file produced
          tmp_dir,
          '--set',
          'imaginary',
          'image',
          'mandel',
          ' -0.7436499',
          '0.13188204',
          '0.00073801',
        ]
      )
      assert r.returncode == 0, f'tranz image mandel failed:\n{r.stderr}'
      # we check that the image is the same by trusting the 20-character hash in the file name;
      # the hash is from the internal representation and should only depend on our implementation;
      # resist the temptation of checking the PNG because PIL behaves differently across platforms
      # and Python versions, and we don't want to be debugging PIL differences in this test
      output_image: pathlib.Path = (
        pathlib.Path(tmp_dir) / f'mandel-{base.SEAHORSE_TAIL_HASH[:20]}.png'
      )
      assert output_image.exists(), f'Expected output image not found: {output_image}'
      # check the image data
      w, h, hsh, info = image.GetBasicDataFromPNG(output_image.read_bytes())
      assert w == h == 1024, f'Expected image dimensions 1024x1024, got {w}x{h}'
      assert hsh == base.SEAHORSE_TAIL_HASH
      assert '.' in info.pop(image.META_VERSION_KEY)  # type: ignore[operator]  # make agnostic
      assert 'UTC' in info.pop(image.META_DATETIME_KEY)  # type: ignore[operator]  # make agnostic
      assert info == {
        'tranzoom:frame:fractal': 'mandelbrot',
        'tranzoom:frame:center_re': '-7436499/10000000',
        'tranzoom:frame:center_im': '3297051/25000000',
        'tranzoom:frame:width_re': '73801/100000000',
        'tranzoom:frame:height_im': '73801/100000000',
        'tranzoom:frame:top_re': '-148803781/200000000',
        'tranzoom:frame:top_im': '26450209/200000000',
        'tranzoom:frame:bottom_re': '-148656179/200000000',
        'tranzoom:frame:bottom_im': '26302607/200000000',
        'tranzoom:frame:magnification': '3387.487974417691',
        'tranzoom:frame:magnification_order': '3.529877762139788',
        'tranzoom:frame:precision': '140',
        'tranzoom:image:width': '1024',
        'tranzoom:image:height': '1024',
        'tranzoom:image:palette': 'blue-to-yellow-to-brown',
        'tranzoom:image:set_palette': 'grayscale',
        'tranzoom:image:color_set': 'imaginary',
        'tranzoom:image:hash': base.SEAHORSE_TAIL_HASH,
        'tranzoom:image:iter_depth:min': '36',
        'tranzoom:image:iter_depth:max': '1000',
        'tranzoom:image:iter_depth:search': '1000',
        'tranzoom:image:set_point:min': '2773383',
        'tranzoom:image:set_point:max': '14144995',
        'tranzoom:image:overlay': 'false',
        'tranzoom:image:exterior:cumulative_histogram_summary': (
          "[(36, 10978), (37, 44923), (38, 99382), ('...', 914445666), "
          '(996, 1048373), (997, 1048374), (999, 1048376)]'
        ),
        'tranzoom:image:exterior:histogram_summary': (
          "[(36, 10978), (37, 33945), (38, 54459), ('...', 948989), (996, 2), (997, 1), (999, 2)]"
        ),
        'tranzoom:image:exterior:pixel_count': '1048376',
        'tranzoom:image:interior:cumulative_histogram_summary': (
          "[(2773383, 1), (3024301, 2), (3110372, 3), ('...', 19497), "
          '(14071028, 198), (14132599, 199), (14144995, 200)]'
        ),
        'tranzoom:image:interior:histogram_summary': (
          "[(2773383, 1), (3024301, 1), (3110372, 1), ('...', 194), "
          '(14071028, 1), (14132599, 1), (14144995, 1)]'
        ),
        'tranzoom:image:interior:pixel_count': '200',
      }
  finally:
    shutil.rmtree(data_dir)  # remove created data to isolate the next CLI's read step


def _JuliaSuzanaWaveCall(cli_paths: dict[str, pathlib.Path], data_dir: pathlib.Path) -> None:
  """Call the installed CLI to render the Julia Suzana Wave image, check the output file / metadata.

  Should be 100% equivalent to the `scripts/make_examples.sh` line to "Render Julia Suzana Wave".
  """
  try:
    with tempfile.TemporaryDirectory() as tmp_dir:
      # render a Julia Suzana Wave image
      r = tbase.Run(
        # call the console script directly to test the installed CLI
        [
          str(cli_paths['tranz']),
          '--no-date',  # --no-date makes the filename deterministic (hash-only)
          '--out',  # --out directs output to tmp_dir so we can assert on the exact file produced
          tmp_dir,
          '--set',
          'max',
          '--palette',
          'electric-ocean',
          '--set-palette',
          'sunset',
          'image',
          '-s',
          '512',
          'julia',
          '13667/50000',
          '371/50000',
          ' -313420497/429687500',
          '0.6567',
          '0.00544',
          '0.004',
        ]
      )
      assert r.returncode == 0, f'tranz image mandel failed:\n{r.stderr}'
      # we check that the image is the same by trusting the 20-character hash in the file name;
      # the hash is from the internal representation and should only depend on our implementation;
      # resist the temptation of checking the PNG because PIL behaves differently across platforms
      # and Python versions, and we don't want to be debugging PIL differences in this test
      output_image: pathlib.Path = pathlib.Path(tmp_dir) / f'julia-{base.SUZANA_WAVE_HASH[:20]}.png'
      assert output_image.exists(), f'Expected output image not found: {output_image}'
      # check the image data
      w, h, hsh, info = image.GetBasicDataFromPNG(output_image.read_bytes())
      assert w == 512, f'Expected image dimensions 512x377, got {w}x{h}'
      assert h == 377, f'Expected image dimensions 512x377, got {w}x{h}'
      assert hsh == base.SUZANA_WAVE_HASH
      assert '.' in info.pop(image.META_VERSION_KEY)  # type: ignore[operator]  # make agnostic
      assert 'UTC' in info.pop(image.META_DATETIME_KEY)  # type: ignore[operator]  # make agnostic
      assert info == {
        'tranzoom:frame:fractal': 'julia',
        'tranzoom:frame:julia_re': '13667/50000',
        'tranzoom:frame:julia_im': '371/50000',
        'tranzoom:frame:center_re': '-313420497/429687500',
        'tranzoom:frame:center_im': '6567/10000',
        'tranzoom:frame:width_re': '17/3125',
        'tranzoom:frame:height_im': '1/250',
        'tranzoom:frame:top_re': '-314589247/429687500',
        'tranzoom:frame:top_im': '6587/10000',
        'tranzoom:frame:bottom_re': '-312251747/429687500',
        'tranzoom:frame:bottom_im': '6547/10000',
        'tranzoom:frame:magnification': '426.5973442458908',
        'tranzoom:frame:magnification_order': '2.630018147449685',
        'tranzoom:frame:precision': '140',
        'tranzoom:image:width': '512',
        'tranzoom:image:height': '377',
        'tranzoom:image:palette': 'electric-ocean',
        'tranzoom:image:set_palette': 'sunset',
        'tranzoom:image:color_set': 'max',
        'tranzoom:image:hash': 'd7b19b0f1783bb38127d2948140e2379c19656ff4923b7244f25da7fbf322a2a',
        'tranzoom:image:iter_depth:min': '43',
        'tranzoom:image:iter_depth:max': '1819',
        'tranzoom:image:iter_depth:search': '1819',
        'tranzoom:image:set_point:min': '1',
        'tranzoom:image:set_point:max': '100000000',
        'tranzoom:image:overlay': 'false',
        'tranzoom:image:exterior:cumulative_histogram_summary': (
          "[(43, 4194), (44, 15827), (45, 25830), ('...', 86502348), (1792, 106708), "
          '(1798, 106709), (1813, 106710)]'
        ),
        'tranzoom:image:exterior:histogram_summary': (
          "[(43, 4194), (44, 11633), (45, 10003), ('...', 80877), (1792, 1), (1798, 1), (1813, 1)]"
        ),
        'tranzoom:image:exterior:pixel_count': '106710',
        'tranzoom:image:interior:cumulative_histogram_summary': (
          "[(1, 6741), (47, 6742), (122, 6743), ('...', 3609455247), "
          '(99949558, 85448), (99995934, 85449), (100000000, 86314)]'
        ),
        'tranzoom:image:interior:histogram_summary': (
          "[(1, 6741), (47, 1), (122, 1), ('...', 78704), (99949558, 1), "
          '(99995934, 1), (100000000, 865)]'
        ),
        'tranzoom:image:interior:pixel_count': '86314',
      }
  finally:
    shutil.rmtree(data_dir)  # remove created data to isolate the next CLI's read step
