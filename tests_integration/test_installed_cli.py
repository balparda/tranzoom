# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Integration tests: test the installed CLI from a wheel.

How to run locally: `make build`, then `make integration`

In CI: the wheel is built and installed by the workflow before running these tests.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess  # noqa: S404
import tempfile

import pytest
from transcrypto.utils import base as tbase

import tranzoom
from tranzoom.cli import base
from tranzoom.core import pixels


@pytest.fixture
def cli() -> pathlib.Path:
  """Find the installed console script; will raise if not found.

  Returns:
      pathlib.Path: path to the installed console script.

  """
  cli_path: str | None = shutil.which('tranz')
  if cli_path is None:
    pytest.fail('Console script "tranz" not found in PATH')
  return pathlib.Path(cli_path)


@pytest.mark.slow
@pytest.mark.integration
def test_version(cli: pathlib.Path) -> None:
  """Test the installed CLI from the current environment."""
  tbase.VersionCallCheck(cli, tranzoom.__version__)


@pytest.mark.slow
@pytest.mark.integration
def test_mandelbrot_seahorse_tail(cli: pathlib.Path) -> None:
  """Call the installed CLI to render the Seahorse Tail image, check the output file and metadata.

  Should be 100% equivalent to the `scripts/make_examples.sh` line to "Render Seahorse Tail".
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    # render a Seahorse Tail image
    r: subprocess.CompletedProcess[str] = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli),
        '--no-date',  # --no-date makes the filename deterministic (hash-only)
        '--db',
        '--force',
        '--opt',
        'cython',
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
    w: int
    h: int
    hsh: str
    info: tbase.JSONDict
    w, h, hsh, info = pixels.GetBasicDataFromImage(output_image.read_bytes())
    assert w == h == 1024, f'Expected image dimensions 1024x1024, got {w} x {h}'
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
      'tranZoom:image:set:n:min': '59557928',
      'tranZoom:image:set:n:max': '303761451',
      'tranZoom:image:set:nu:min': '0.005359342787414789',
      'tranZoom:image:set:nu:max': '0.9978883266448975',
      'tranZoom:image:set:bucket:min': '121974638155',
      'tranZoom:image:set:bucket:max': '622103451658',
      'tranZoom:image:set:hist:linear': (
        '{59557928: 1, 64946349: 1, 66794710: 1, ...: 194, 302173019: 1, '
        '303495239: 1, 303761451: 1}'
      ),
      'tranZoom:image:set:hist:linear:cumulative': (
        '{59557928: 1, 64946349: 2, 66794710: 3, ...: 19497, 302173019: 198, '
        '303495239: 199, 303761451: 200}'
      ),
      'tranZoom:image:set:hist:bucket': (
        '{121974638155: 1, 133010124615: 1, 136795567844: 1, ...: 194, '
        '618850344931: 1, 621558250452: 1, 622103451658: 1}'
      ),
      'tranZoom:image:set:hist:bucket:cumulative': (
        '{121974638155: 1, 133010124615: 2, 136795567844: 3, ...: 19497, '
        '618850344931: 198, 621558250452: 199, 622103451658: 200}'
      ),
      'tranZoom:image:stats:imag_lo': '0.027733821348360696858581004102225914175833148',
      'tranZoom:image:stats:imag_hi': '0.14144994797569664128062592939633699605100723',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'sahara',
      'tranZoom:render:set_palette': 'rgrayscale',
      'tranZoom:render:i_pixels': '0',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:hash': '9ccb42f3ee157bcd52a191e532cd531b7d4fd191ad2883b232ba979c13e96a09',
    }


@pytest.mark.slow
@pytest.mark.integration
def test_animated_seahorse_tail(cli: pathlib.Path) -> None:
  """Call the installed CLI to render the Seahorse Tail GIF image, check the GIF file and metadata.

  Should be 100% equivalent to `scripts/make_examples.sh` line to "Render Animated Seahorse Tail".
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    # render a Seahorse Tail Animated image
    r: subprocess.CompletedProcess[str] = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli),
        '--no-date',  # --no-date makes the filename deterministic (hash-only)
        '--db',  # DB makes this a streaming DB-rich generation
        '--opt',
        'cython',
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
        '5',
        '--duration',
        '4',
        '--i-frames',
        '1',
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
    w: int
    h: int
    hsh: str
    info: tbase.JSONDict
    w, h, hsh, info = pixels.GetBasicDataFromImage(output_image.read_bytes())
    assert w == h == 220, f'Expected image dimensions 220 x 220, got {w} x {h}'
    assert hsh == base.SEAHORSE_ANIMATED_HASH
    assert info == {
      'tranZoom:frame:fractal': 'mandelbrot',
      'tranZoom:frame:center_re': '-5578776469/7500000000',
      'tranZoom:frame:center_im': '8244620127/62500000000',
      'tranZoom:frame:top_re': '-22316212891/30000000000',
      'tranZoom:frame:top_im': '32987705633/250000000000',
      'tranZoom:frame:bottom_re': '-22313998861/30000000000',
      'tranZoom:frame:bottom_im': '32969255383/250000000000',
      'tranZoom:frame:width_re': '73801/1000000000',
      'tranZoom:frame:height_im': '73801/1000000000',
      'tranZoom:frame:magnification_order': '4.529877762139788',
      'tranZoom:frame:precision': '140',
      'tranZoom:frame:hash': 'a293633123a893f7fb5597b8ebdf444d1fca9ad1390e1940819dcf419c7edd0e',
      'tranZoom:computation:width': '220',
      'tranZoom:computation:height': '220',
      'tranZoom:computation:depth': '1105',
      'tranZoom:computation:color_set': 'none',
      'tranZoom:computation:hash': (
        'f7c110603e5498fe126427b74f078b6a944a370d1be9c363445fb299a105668c'
      ),
      'tranZoom:image:animation': 'gif',
      'tranZoom:image:hash': base.SEAHORSE_ANIMATED_HASH,
      'tranZoom:image:exterior:count': '48380',
      'tranZoom:image:exterior:n:min': '98',
      'tranZoom:image:exterior:n:max': '1087',
      'tranZoom:image:exterior:nu:min': '4.646779416361824e-06',
      'tranZoom:image:exterior:nu:max': '0.9999839663505554',
      'tranZoom:image:exterior:bucket:min': '202433',
      'tranZoom:image:exterior:bucket:max': '2227517',
      'tranZoom:image:exterior:hist:linear': (
        '{98: 2, 99: 6, 100: 5, ...: 48364, 1064: 1, 1084: 1, 1087: 1}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{98: 2, 99: 8, 100: 13, ...: 31403541, 1064: 48378, 1084: 48379, 1087: 48380}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{202433: 1, 202682: 1, 202820: 1, ...: 48374, 2179925: 1, 2220863: 1, 2227517: 1}'
      ),
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{202433: 1, 202682: 2, 202820: 3, ...: 1136884208, 2179925: 48378, '
        '2220863: 48379, 2227517: 48380}'
      ),
      'tranZoom:image:set:count': '20',
      'tranZoom:image:set:n:min': '2147483647',
      'tranZoom:image:set:n:max': '2147483647',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:image:set:nu:max': '0.0',
      'tranZoom:image:set:bucket:min': '4398046509056',
      'tranZoom:image:set:bucket:max': '4398046509056',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'sahara',
      'tranZoom:render:set_palette': 'none',
      'tranZoom:render:i_pixels': '0',
      'tranZoom:render:mark_color': 'red',
      'tranZoom:render:mark_re': '-5578776469/7500000000',
      'tranZoom:render:mark_im': '8244620127/62500000000',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:hash': 'b5467479fe084f34e58ccc671216eacb5da83dfb2b1200c0f811f923590598ad',
      'tranZoom:zoom:type': 'gif',
      'tranZoom:zoom:frame:initial:width_re': '73801/100000000',
      'tranZoom:zoom:frame:initial:height_im': '73801/100000000',
      'tranZoom:zoom:frame:magnitude': '1',
      'tranZoom:zoom:frame:frames': '20',
      'tranZoom:zoom:frame:i_frames': '1',
      'tranZoom:zoom:frame:all_frames': '39',
      'tranZoom:zoom:frame:seconds': '4',
      'tranZoom:zoom:frame:loop': '0',
      'tranZoom:zoom:frame:fps': '5',
      'tranZoom:zoom:frame:ifps': '10',
      'tranZoom:zoom:frame:steps': '19',
      'tranZoom:zoom:frame:magnitude_per_step': '1/19',
      'tranZoom:zoom:frame:magnification_per_step': '2541916954176431/2251799813685248',
      'tranZoom:zoom:marker:index': '[0, 19]',
      'tranZoom:zoom:depth:frames': (
        '[(0, 1000, 1001), (6, 1000, 1019), (13, 1000, 1034), (19, 1159, 1105)]'
      ),
      'tranZoom:zoom:hash': 'edef7da54fc24b114c90906ad7ab1fcaadcb234496dd1f6bcc6f2ac11ac4fda1',
    }


@pytest.mark.slow
@pytest.mark.integration
def test_julia_suzana_wave(cli: pathlib.Path) -> None:
  """Call the installed CLI to render the Julia Suzana Wave image, check the output file / metadata.

  Should be 100% equivalent to the `scripts/make_examples.sh` line to "Render Julia Suzana Wave".
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    # render a Julia Suzana Wave image
    r: subprocess.CompletedProcess[str] = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli),
        '--no-date',  # --no-date makes the filename deterministic (hash-only)
        '--db',
        '--force',
        '--opt',
        'cython',
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
        '--i-pixels',
        '1',
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
    w: int
    h: int
    hsh: str
    info: tbase.JSONDict
    w, h, hsh, info = pixels.GetBasicDataFromImage(output_image.read_bytes())
    assert w == 1024, f'Expected image dimensions 1024 x 754, got {w} x {h}'
    assert h == 754, f'Expected image dimensions 1024 x 754, got {w} x {h}'
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
      'tranZoom:computation:depth': '1000',
      'tranZoom:computation:color_set': 'max',
      'tranZoom:computation:hash': (
        'd2abc05d51981f2b3bc54958d5331369e77041d20a119a4236da124feb4e8e90'
      ),
      'tranZoom:image:animation': 'none',
      'tranZoom:image:hash': base.SUZANA_WAVE_HASH,
      'tranZoom:image:exterior:count': '106573',
      'tranZoom:image:exterior:n:min': '43',
      'tranZoom:image:exterior:n:max': '994',
      'tranZoom:image:exterior:nu:min': '5.752321158070117e-06',
      'tranZoom:image:exterior:nu:max': '0.9999896883964539',
      'tranZoom:image:exterior:bucket:min': '89879',
      'tranZoom:image:exterior:bucket:max': '2037662',
      'tranZoom:image:exterior:hist:linear': (
        '{43: 379, 44: 9212, 45: 11219, ...: 85759, 989: 2, 991: 1, 994: 1}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{43: 379, 44: 9591, 45: 20810, ...: 74305010, 989: 106571, 991: 106572, 994: 106573}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{89879: 5, 89880: 2, 89881: 2, ...: 106561, 2027341: 1, 2031483: 1, 2037662: 1}'
      ),
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{89879: 5, 89880: 7, 89881: 9, ...: 3333990510, 2027341: 106571, '
        '2031483: 106572, 2037662: 106573}'
      ),
      'tranZoom:image:set:count': '86451',
      'tranZoom:image:set:n:min': '1',
      'tranZoom:image:set:n:max': '2147483647',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:image:set:nu:max': '0.9999693632125854',
      'tranZoom:image:set:bucket:min': '2048',
      'tranZoom:image:set:bucket:max': '4398046509056',
      'tranZoom:image:set:hist:linear': (
        '{1: 1, 227414: 1, 454834: 1, ...: 85187, 2147251284: 1, 2147468473: 1, 2147483647: 1259}'
      ),
      'tranZoom:image:set:hist:linear:cumulative': (
        '{1: 1, 227414: 2, 454834: 3, ...: 3627575241, 2147251284: 85191, '
        '2147468473: 85192, 2147483647: 86451}'
      ),
      'tranZoom:image:set:hist:bucket': (
        '{2048: 1, 465745059: 1, 931501089: 1, ...: 85187, 4397570629803: 1, '
        '4398015433823: 1, 4398046509056: 1259}'
      ),
      'tranZoom:image:set:hist:bucket:cumulative': (
        '{2048: 1, 465745059: 2, 931501089: 3, ...: 3628696726, '
        '4397570629803: 85191, 4398015433823: 85192, 4398046509056: 86451}'
      ),
      'tranZoom:image:stats:max_lo': '1.0303269913803812829799720484633954828318221',
      'tranZoom:image:stats:max_hi': '2.0404855784383760342353483617573930562163787',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'electric',
      'tranZoom:render:set_palette': 'sunset',
      'tranZoom:render:i_pixels': '1',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:hash': '57e17bd485377f533971053c16d099905457daaa7c73b21b911d1c41a54e673b',
    }
