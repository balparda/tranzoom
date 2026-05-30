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
import tempfile

import pytest
from transcrypto.utils import base as tbase
from transcrypto.utils import config

import tranzoom
from tranzoom.cli import base
from tranzoom.core import image

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
  # _MandelbrotSeahorseTailCall(cli_paths)
  _AnimatedSeahorseTailCall(cli_paths)
  # _JuliaSuzanaWaveCall(cli_paths)


def _MandelbrotSeahorseTailCall(cli_paths: dict[str, pathlib.Path]) -> None:
  """Call the installed CLI to render the Seahorse Tail image, check the output file and metadata.

  Should be 100% equivalent to the `scripts/make_examples.sh` line to "Render Seahorse Tail".
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    # render a Seahorse Tail image
    r = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli_paths['tranz']),
        '--no-date',  # --no-date makes the filename deterministic (hash-only)
        '--no-db',
        '--force',
        '--out',  # --out directs output to tmp_dir so we can assert on the exact file produced
        tmp_dir,
        '--db-path',  # make sure DB will be in temp too!
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
    w, h, hsh, info = image.GetBasicDataFromImage(output_image.read_bytes())
    assert w == h == 1024, f'Expected image dimensions 1024x1024, got {w}x{h}'
    assert hsh == base.SEAHORSE_TAIL_HASH
    assert info == {
      'tranZoom:frame:fractal': 'mandelbrot',
      'tranZoom:frame:center_re': '-7436499/10000000',
      'tranZoom:frame:center_im': '3297051/25000000',
      'tranZoom:frame:width_re': '73801/100000000',
      'tranZoom:frame:height_im': '73801/100000000',
      'tranZoom:frame:top_re': '-148803781/200000000',
      'tranZoom:frame:top_im': '26450209/200000000',
      'tranZoom:frame:bottom_re': '-148656179/200000000',
      'tranZoom:frame:bottom_im': '26302607/200000000',
      'tranZoom:frame:magnification_order': '3.529877762139788',
      'tranZoom:frame:precision': '140',
      'tranZoom:frame:hash': 'dfaf6f8a553a24347bf23ab41baf4263121041caf9d551975dfe108e22a31e08',
      'tranZoom:computation:width': '1024',
      'tranZoom:computation:height': '1024',
      'tranZoom:computation:depth': '1000',
      'tranZoom:computation:color_set': 'imaginary',
      'tranZoom:computation:hash': (
        '5a8b09433a0e24301bf49a50d03bf71147f106fb6644f86132dd69bcf1a7a619'
      ),
      'tranZoom:image:animation': 'none',
      'tranZoom:image:hash': base.SEAHORSE_TAIL_HASH,
      'tranZoom:image:exterior:count': '1048376',
      'tranZoom:image:exterior:n:min': '37',
      'tranZoom:image:exterior:n:max': '1000',
      'tranZoom:image:exterior:nu:min': '4.950653078594769e-07',
      'tranZoom:image:exterior:nu:max': '0.9999997615814209',
      'tranZoom:image:exterior:bucket:min': '76329',
      'tranZoom:image:exterior:bucket:max': '2048632',
      'tranZoom:image:exterior:hist:linear': (
        '{37: 20310, 38: 47218, 39: 53027, ...: 927818, 997: 1, 999: 1, 1000: 1}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{37: 20310, 38: 67528, 39: 120555, ...: 914874853, 997: 1048374, '
        '999: 1048375, 1000: 1048376}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{76329: 1, 76332: 1, 76334: 1, ...: 1048370, 2043780: 1, 2047391: 1, 2048632: 1}'
      ),
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{76329: 1, 76332: 2, 76334: 3, ...: 254715394213, 2043780: 1048374, '
        '2047391: 1048375, 2048632: 1048376}'
      ),
      'tranZoom:image:set:count': '200',
      'tranZoom:image:set:n:min': '2773383',
      'tranZoom:image:set:n:max': '14144995',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:image:set:nu:max': '0.0',
      'tranZoom:image:set:bucket:min': '5679888384',
      'tranZoom:image:set:bucket:max': '28968949760',
      'tranZoom:image:set:hist:linear': (
        '{2773383: 1, 3024301: 1, 3110372: 1, ...: 194, 14071028: 1, 14132599: 1, 14144995: 1}'
      ),
      'tranZoom:image:set:hist:linear:cumulative': (
        '{2773383: 1, 3024301: 2, 3110372: 3, ...: 19497, 14071028: 198, 14132599: 199, '
        '14144995: 200}'
      ),
      'tranZoom:image:set:hist:bucket': (
        '{5679888384: 1, 6193768448: 1, 6370041856: 1, ...: 194, 28817465344: 1, '
        '28943562752: 1, 28968949760: 1}'
      ),
      'tranZoom:image:set:hist:bucket:cumulative': (
        '{5679888384: 1, 6193768448: 2, 6370041856: 3, ...: 19497, 28817465344: 198, '
        '28943562752: 199, 28968949760: 200}'
      ),
      'tranZoom:image:stats:imag_lo': '0.027733821348360696858581004102225914175833148',
      'tranZoom:image:stats:imag_hi': '0.14144994797569664128062592939633699605100723',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'sahara',
      'tranZoom:render:set_palette': 'rgrayscale',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:hash': 'd28c88818cb8926c7e151d2e9d475cad85223349d22acf382decc4fb61915029',
    }


def _AnimatedSeahorseTailCall(cli_paths: dict[str, pathlib.Path]) -> None:
  """Call the installed CLI to render the Seahorse Tail GIF image, check the GIF file and metadata.

  Should be 100% equivalent to `scripts/make_examples.sh` line to "Render Animated Seahorse Tail".
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    # render a Seahorse Tail Animated image
    r = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli_paths['tranz']),
        '--no-date',  # --no-date makes the filename deterministic (hash-only)
        '--no-db',
        '--force',
        '--out',  # --out directs output to tmp_dir so we can assert on the exact file produced
        tmp_dir,
        '--db-path',  # make sure DB will be in temp too!
        tmp_dir,
        'zoom',
        '-s',
        '220',
        '--mark',
        '(-5578776469/7500000000,8244620127/62500000000)',
        'auto',
        ' -5578776469/7500000000',
        '8244620127/62500000000',
        '0.00073801',
        '0.00073801',
        '1',
        '--fps',
        '10',
        '--duration',
        '4',
      ]
    )
    assert r.returncode == 0, f'tranz zoom auto failed:\n{r.stderr}'
    # we check that the image is the same by trusting the 20-character hash in the file name;
    # the hash is from the internal representation and should only depend on our implementation;
    # resist the temptation of checking the PNG because PIL behaves differently across platforms
    # and Python versions, and we don't want to be debugging PIL differences in this test
    output_image: pathlib.Path = (
      pathlib.Path(tmp_dir) / f'mandel-{base.SEAHORSE_ANIMATED_HASH[:20]}.gif'
    )
    assert output_image.exists(), f'Expected output gif not found: {output_image}'
    # check the image data
    w, h, hsh, info = image.GetBasicDataFromImage(output_image.read_bytes())
    assert w == h == 220, f'Expected image dimensions 220x220, got {w}x{h}'
    assert hsh == base.SEAHORSE_ANIMATED_HASH
    assert info == {
      'tranZoom:frame:fractal': 'mandelbrot',
      'tranZoom:frame:center_re': '-5578776469/7500000000',
      'tranZoom:frame:center_im': '8244620127/62500000000',
      'tranZoom:frame:top_re': '-9953460536484113/13380577500000000',
      'tranZoom:frame:top_im': '44139455176953337/334514437500000000',
      'tranZoom:frame:bottom_re': '-3317491012161371/4460192500000000',
      'tranZoom:frame:bottom_im': '44114767676953337/334514437500000000',
      'tranZoom:frame:width_re': '395/5352231',
      'tranZoom:frame:height_im': '395/5352231',
      'tranZoom:frame:magnification_order': '4.5298777621738715',
      'tranZoom:frame:precision': '140',
      'tranZoom:frame:hash': 'fb78ce2042c8e7f2cc0a314e0faf09ec9b3423131461a2ac250491f7a17ff83b',
      'tranZoom:computation:width': '220',
      'tranZoom:computation:height': '220',
      'tranZoom:computation:depth': '1518',
      'tranZoom:computation:color_set': 'none',
      'tranZoom:computation:hash': (
        'b78c5bc40b52633696533b9594f728d894fa44442f8a77150396a3c3b8c63cdd'
      ),
      'tranZoom:image:animation': 'gif',
      'tranZoom:image:hash': base.SEAHORSE_ANIMATED_HASH,
      'tranZoom:image:exterior:count': '48399',
      'tranZoom:image:exterior:n:min': '98',
      'tranZoom:image:exterior:n:max': '1400',
      'tranZoom:image:exterior:nu:min': '1.1549895134521648e-05',
      'tranZoom:image:exterior:nu:max': '0.9999839663505554',
      'tranZoom:image:exterior:bucket:min': '202433',
      'tranZoom:image:exterior:bucket:max': '2867813',
      'tranZoom:image:exterior:hist:linear': (
        '{98: 2, 99: 6, 100: 5, ...: 48383, 1317: 1, 1345: 1, 1400: 1}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{98: 2, 99: 8, 100: 13, ...: 32414206, 1317: 48397, 1345: 48398, 1400: 48399}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{202433: 1, 202682: 1, 202820: 1, ...: 48393, 2697670: 1, 2754588: 1, 2867813: 1}'
      ),
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{202433: 1, 202682: 2, 202820: 3, ...: 1137830172, 2697670: 48397, '
        '2754588: 48398, 2867813: 48399}'
      ),
      'tranZoom:image:set:count': '1',
      'tranZoom:image:set:n:min': '100000000',
      'tranZoom:image:set:n:max': '100000000',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:image:set:nu:max': '0.0',
      'tranZoom:image:set:bucket:min': '204800000000',
      'tranZoom:image:set:bucket:max': '204800000000',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'sahara',
      'tranZoom:render:set_palette': 'none',
      'tranZoom:render:mark_color': 'red',
      'tranZoom:render:mark_re': '-5578776469/7500000000',
      'tranZoom:render:mark_im': '8244620127/62500000000',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:hash': '09b7382e678896a44f9388aad39a0cdaa6afc71145af8727ddaefa3ffc2e55ac',
      'tranZoom:zoom:type': 'gif',
      'tranZoom:zoom:frame:initial:width_re': '73801/100000000',
      'tranZoom:zoom:frame:initial:height_im': '73801/100000000',
      'tranZoom:zoom:frame:magnitude': '1',
      'tranZoom:zoom:frame:frames': '40',
      'tranZoom:zoom:frame:seconds': '4',
      'tranZoom:zoom:frame:loop': '0',
      'tranZoom:zoom:frame:fps': '10',
      'tranZoom:zoom:frame:steps': '39',
      'tranZoom:zoom:frame:magnitude_per_step': '1/39',
      'tranZoom:zoom:frame:magnification_per_step': '4777501148913803/4503599627370496',
      'tranZoom:zoom:hash': '3410c539ffd85ccdd9f7dddfb6f65fe9e4330eb02624cff0d2aa70b102bb5beb',
    }


def _JuliaSuzanaWaveCall(cli_paths: dict[str, pathlib.Path]) -> None:
  """Call the installed CLI to render the Julia Suzana Wave image, check the output file / metadata.

  Should be 100% equivalent to the `scripts/make_examples.sh` line to "Render Julia Suzana Wave".
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    # render a Julia Suzana Wave image
    r = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli_paths['tranz']),
        '--no-date',  # --no-date makes the filename deterministic (hash-only)
        '--no-db',
        '--force',
        '--out',  # --out directs output to tmp_dir so we can assert on the exact file produced
        tmp_dir,
        '--db-path',  # make sure DB will be in temp too!
        tmp_dir,
        '--set',
        'max',
        '--palette',
        'electric',
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
    assert r.returncode == 0, f'tranz image julia failed:\n{r.stderr}'
    # we check that the image is the same by trusting the 20-character hash in the file name;
    # the hash is from the internal representation and should only depend on our implementation;
    # resist the temptation of checking the PNG because PIL behaves differently across platforms
    # and Python versions, and we don't want to be debugging PIL differences in this test
    output_image: pathlib.Path = pathlib.Path(tmp_dir) / f'julia-{base.SUZANA_WAVE_HASH[:20]}.png'
    assert output_image.exists(), f'Expected output image not found: {output_image}'
    # check the image data
    w, h, hsh, info = image.GetBasicDataFromImage(output_image.read_bytes())
    assert w == 512, f'Expected image dimensions 512x377, got {w}x{h}'
    assert h == 377, f'Expected image dimensions 512x377, got {w}x{h}'
    assert hsh == base.SUZANA_WAVE_HASH
    assert info == {
      'tranZoom:frame:fractal': 'julia',
      'tranZoom:frame:julia_re': '13667/50000',
      'tranZoom:frame:julia_im': '371/50000',
      'tranZoom:frame:center_re': '-313420497/429687500',
      'tranZoom:frame:center_im': '6567/10000',
      'tranZoom:frame:width_re': '17/3125',
      'tranZoom:frame:height_im': '1/250',
      'tranZoom:frame:top_re': '-314589247/429687500',
      'tranZoom:frame:top_im': '6587/10000',
      'tranZoom:frame:bottom_re': '-312251747/429687500',
      'tranZoom:frame:bottom_im': '6547/10000',
      'tranZoom:frame:magnification_order': '2.630018147449685',
      'tranZoom:frame:precision': '140',
      'tranZoom:frame:hash': '8faa5c419732c9444c77bfd61cad10e2a6a84681a541a2ef3a88b979fdca51e6',
      'tranZoom:computation:width': '512',
      'tranZoom:computation:height': '377',
      'tranZoom:computation:depth': '1819',
      'tranZoom:computation:color_set': 'max',
      'tranZoom:computation:hash': (
        '096853172953a47c23baee6382f164c720392ad7ecb0266d2edada47fc280081'
      ),
      'tranZoom:image:animation': 'none',
      'tranZoom:image:hash': base.SUZANA_WAVE_HASH,
      'tranZoom:image:exterior:count': '106710',
      'tranZoom:image:exterior:n:min': '43',
      'tranZoom:image:exterior:n:max': '1813',
      'tranZoom:image:exterior:nu:min': '5.752321158070117e-06',
      'tranZoom:image:exterior:nu:max': '0.9999896883964539',
      'tranZoom:image:exterior:bucket:min': '89879',
      'tranZoom:image:exterior:bucket:max': '3715024',
      'tranZoom:image:exterior:hist:linear': (
        '{43: 379, 44: 9212, 45: 11219, ...: 85897, 1792: 1, 1798: 1, 1813: 1}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{43: 379, 44: 9591, 45: 20810, ...: 87208500, 1792: 106708, 1798: 106709, 1813: 106710}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{89879: 5, 89880: 2, 89881: 2, ...: 106698, 3671955: 1, 3684029: 1, 3715024: 1}'
      ),
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{89879: 5, 89880: 7, 89881: 9, ...: 3348600053, 3671955: 106708, 3684029: 106709, '
        '3715024: 106710}'
      ),
      'tranZoom:image:set:count': '86314',
      'tranZoom:image:set:n:min': '1',
      'tranZoom:image:set:n:max': '100000000',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:image:set:nu:max': '0.0',
      'tranZoom:image:set:bucket:min': '2048',
      'tranZoom:image:set:bucket:max': '204800000000',
      'tranZoom:image:set:hist:linear': (
        '{1: 1, 9349: 1, 18697: 1, ...: 86021, 99957787: 1, 99960423: 1, 100000000: 288}'
      ),
      'tranZoom:image:set:hist:linear:cumulative': (
        '{1: 1, 9349: 2, 18697: 3, ...: 3679815476, 99957787: 86025, 99960423: 86026, '
        '100000000: 86314}'
      ),
      'tranZoom:image:set:hist:bucket': (
        '{2048: 1, 19146752: 1, 38291456: 1, ...: 86021, 204713547776: 1, '
        '204718946304: 1, 204800000000: 288}'
      ),
      'tranZoom:image:set:hist:bucket:cumulative': (
        '{2048: 1, 19146752: 2, 38291456: 3, ...: 3679815476, 204713547776: 86025, '
        '204718946304: 86026, 204800000000: 86314}'
      ),
      'tranZoom:image:stats:max_lo': '1.0303269913803812829799720484633954828318221',
      'tranZoom:image:stats:max_hi': '1.274341960143743658549164107217164534985235',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'electric',
      'tranZoom:render:set_palette': 'sunset',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:hash': '27958fa5ac62470c6aef718044291a41e5deab55ddbf82ebf5dc3d898cdd2bad',
    }
