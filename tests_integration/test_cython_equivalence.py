# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Integration tests: test Python/Cython equivalence.

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

from tranzoom.cli import base
from tranzoom.core import image


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
@pytest.mark.parametrize(
  'opt',
  [
    'python',
    'cython',
  ],
)
def test_python_cython_equivalence_seahorse(cli: pathlib.Path, opt: str) -> None:
  """Call the CLI to render the Mandelbrot Seahorse, check result matches dimensions & hash.

  poetry run tranz --no-db --force --palette "lava" --set imaginary --set-palette "toxic"
      --no-date --no-hash --prefix "test-mandel-z-auto-seahorse" -o tests/data/images
      zoom -s 53 auto " -0.7436499" "0.13188204" "227/193" "167/193" "131/43"
      --fps 2 --duration "22.7"
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    r: subprocess.CompletedProcess[str] = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli),
        '--no-db',
        '--force',
        '--opt',
        opt,
        '--palette',
        'lava',
        '--set',
        'imaginary',
        '--set-palette',
        'toxic',
        '--no-date',
        '--out',
        tmp_dir,
        '--db-path',
        tmp_dir,
        'zoom',
        '-s',
        '53',
        'auto',
        ' -0.7436499',
        '0.13188204',
        '227/193',
        '167/193',
        '131/43',
        '--fps',
        '2',
        '--duration',
        '22.7',
      ]
    )
    assert r.returncode == 0, f'tranz image failed:\n{r.stderr}'
    # we check that the image is the same by trusting the 20-character hash in the file name;
    # the hash is from the internal representation and should only depend on our implementation;
    # resist the temptation of checking the PNG because PIL behaves differently across platforms
    # and Python versions, and we don't want to be debugging PIL differences in this test
    output_image: pathlib.Path = (
      pathlib.Path(tmp_dir) / f'mandel-{base.T_GIF_SEAHORSE_HASH[:20]}.gif'
    )
    assert output_image.exists(), f'Expected output image not found: {output_image}'
    # check the image data
    w: int
    h: int
    hsh: str
    w, h, hsh, _ = image.GetBasicDataFromImage(output_image.read_bytes())
    assert (w, h) == (53, 39), f'Expected image dimensions 53x39, got {w} x {h}'
    assert hsh == base.T_GIF_SEAHORSE_HASH


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
  'opt',
  [
    'python',
    'cython',
  ],
)
def test_python_cython_equivalence_seeds300(cli: pathlib.Path, opt: str) -> None:
  """Call the CLI to render the Mandelbrot Seeds300, check result matches dimensions & hash.

  poetry run tranz --no-db --force --palette "electric" --no-date --no-hash
      --prefix "test-mandel-z-auto-seeds300" -o tests/data/images zoom -s 31
      auto "$CX300" "$CY300" "$W300" "$H300" "43/41" --fps 2 --duration 10.1
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    r: subprocess.CompletedProcess[str] = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli),
        '--no-db',
        '--force',
        '--opt',
        opt,
        '--palette',
        'electric',
        '--no-date',
        '--out',
        tmp_dir,
        '--db-path',
        tmp_dir,
        'zoom',
        '-s',
        '31',
        'auto',
        (
          '2855380994729397872866757801843621338002101097439454949929114512227468435009268693358271'
          '8544999736241869933420033962086756117004207202734353232543885707411688461507322309146295'
          '8537231824127891337679111739059888029368087278724647736484597161472714659142532530001112'
          '7128380650475673399178378627431353807918238257509507434954476706953951685899253291600743'
          '4554497662738565574052929232178996289882302816529774813232804058705214082072149274448986'
          '9366392129350928785839288142612302119557940667379400037081408423872094697484146465750438'
          '7086296637091174808451201407111203222656754143225081207586234700191109597003628616322636'
          '920367036329602344606218392288635283937429076929/791016036888793829356252316965561993252'
          '8423433226652131283257854842503584268389807772618660802341524665383684650847265182350650'
          '1046882677633128900974412008752125234534753634590715370977775933170050848275423049926757'
          '8125000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '000000000'
        ),
        (
          ' -45308962242651415074935977011396927661365957855897079708592971604257615026323365837499'
          '5922893631470517421240694097174461998625608348721907791954659697923026192775729989632353'
          '1664167093995488856141436201479659093094974599130029417872040667829521313733391939265285'
          '1085347369348655477867143897857996625326253873738525516201676593960188313107410496081736'
          '7111848985317486363966161043271201973404298782498757619461353677807560926780709432838739'
          '2736681691285724939257147938707593416951604407307320729929072093014983912210005037111075'
          '0768930867445727297525048751834640544796002635328032740778350735933171961973171295248413'
          '0574915201577848399770363925784839040557686809517/65918003074066152446354359747130166104'
          '4035286102221010940271487903541965355699150647718221733528460388781973720903938765195887'
          '5087240223136094075081201000729343769544562802882559614248147994430837570689618587493896'
          '4843750000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000'
        ),
        (
          '5/20000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000'
        ),
        (
          '127/610000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
          '0000000000000000000000000000000000000000'
        ),
        '43/41',
        '--fps',
        '2',
        '--duration',
        '10.1',
      ]
    )
    assert r.returncode == 0, f'tranz image failed:\n{r.stderr}'
    # we check that the image is the same by trusting the 20-character hash in the file name;
    # the hash is from the internal representation and should only depend on our implementation;
    # resist the temptation of checking the PNG because PIL behaves differently across platforms
    # and Python versions, and we don't want to be debugging PIL differences in this test
    output_image: pathlib.Path = (
      pathlib.Path(tmp_dir) / f'mandel-{base.T_GIF_SEEDS_300_HASH[:20]}.gif'
    )
    assert output_image.exists(), f'Expected output image not found: {output_image}'
    # check the image data
    w: int
    h: int
    hsh: str
    w, h, hsh, _ = image.GetBasicDataFromImage(output_image.read_bytes())
    assert (w, h) == (31, 26), f'Expected image dimensions 31x26, got {w} x {h}'
    assert hsh == base.T_GIF_SEEDS_300_HASH


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
  'opt',
  [
    'python',
    'cython',
  ],
)
def test_python_cython_equivalence_suzana(cli: pathlib.Path, opt: str) -> None:
  """Call the CLI to render the Julia Suzana, check result matches dimensions & hash.

  poetry run tranz --no-db --force --palette "sahara" --set angle --set-palette "iris"
      --no-date --no-hash --prefix "test-julia-z-auto-suzana" -o tests/data/images
      zoom -s 59 -f julia --julia-re "13667/50000" --julia-im "371/50000"
      auto " -313420497/429687500" "0.6567" "167/193" "227/193" "241/139" --fps 2 --duration "10.7"
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    r: subprocess.CompletedProcess[str] = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli),
        '--no-db',
        '--force',
        '--opt',
        opt,
        '--palette',
        'sahara',
        '--set',
        'angle',
        '--set-palette',
        'iris',
        '--no-date',
        '--out',
        tmp_dir,
        '--db-path',
        tmp_dir,
        'zoom',
        '-s',
        '59',
        '-f',
        'julia',
        '--julia-re',
        '13667/50000',
        '--julia-im',
        '371/50000',
        'auto',
        ' -313420497/429687500',
        '0.6567',
        '167/193',
        '227/193',
        '241/139',
        '--fps',
        '2',
        '--duration',
        '10.7',
      ]
    )
    assert r.returncode == 0, f'tranz image failed:\n{r.stderr}'
    # we check that the image is the same by trusting the 20-character hash in the file name;
    # the hash is from the internal representation and should only depend on our implementation;
    # resist the temptation of checking the PNG because PIL behaves differently across platforms
    # and Python versions, and we don't want to be debugging PIL differences in this test
    output_image: pathlib.Path = (
      pathlib.Path(tmp_dir) / f'julia-{base.T_GIF_JULIA_SUZANA_HASH[:20]}.gif'
    )
    assert output_image.exists(), f'Expected output image not found: {output_image}'
    # check the image data
    w: int
    h: int
    hsh: str
    w, h, hsh, _ = image.GetBasicDataFromImage(output_image.read_bytes())
    assert (w, h) == (44, 59), f'Expected image dimensions 44x59, got {w} x {h}'
    assert hsh == base.T_GIF_JULIA_SUZANA_HASH


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
  'opt',
  [
    'python',
    'cython',
  ],
)
def test_python_cython_equivalence_dragon(cli: pathlib.Path, opt: str) -> None:
  """Call the CLI to render the Julia Dragon, check result matches dimensions & hash.

  poetry run tranz --no-db --force --palette "lava" --set min --set-palette "electric"
      --no-date --no-hash --prefix "test-julia-z-auto-dragon" -o tests/data/images
      zoom -s 67 -f julia --julia-re " -0.11" --julia-im "0.6557"
      auto "0" "0" "223/73" "281/71" "37/97" --fps 2 --duration "4.1"
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    r: subprocess.CompletedProcess[str] = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli),
        '--no-db',
        '--force',
        '--opt',
        opt,
        '--palette',
        'lava',
        '--set',
        'min',
        '--set-palette',
        'electric',
        '--no-date',
        '--out',
        tmp_dir,
        '--db-path',
        tmp_dir,
        'zoom',
        '-s',
        '67',
        '-f',
        'julia',
        '--julia-re',
        ' -0.11',
        '--julia-im',
        '0.6557',
        'auto',
        '0',
        '0',
        '223/73',
        '281/71',
        '37/97',
        '--fps',
        '2',
        '--duration',
        '4.1',
      ]
    )
    assert r.returncode == 0, f'tranz image failed:\n{r.stderr}'
    # we check that the image is the same by trusting the 20-character hash in the file name;
    # the hash is from the internal representation and should only depend on our implementation;
    # resist the temptation of checking the PNG because PIL behaves differently across platforms
    # and Python versions, and we don't want to be debugging PIL differences in this test
    output_image: pathlib.Path = (
      pathlib.Path(tmp_dir) / f'julia-{base.T_GIF_JULIA_DRAGON_HASH[:20]}.gif'
    )
    assert output_image.exists(), f'Expected output image not found: {output_image}'
    # check the image data
    w: int
    h: int
    hsh: str
    w, h, hsh, _ = image.GetBasicDataFromImage(output_image.read_bytes())
    assert (w, h) == (52, 67), f'Expected image dimensions 52x67, got {w} x {h}'
    assert hsh == base.T_GIF_JULIA_DRAGON_HASH


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
  'opt',
  [
    'python',
    'cython',
  ],
)
def test_python_cython_equivalence_blob(cli: pathlib.Path, opt: str) -> None:
  """Call the CLI to render the Julia Blob, check result matches dimensions & hash.

  poetry run tranz --no-db --force --palette "sahara" --set max --set-palette "electric"
      --no-date --no-hash --prefix "test-julia-z-auto-blob" -o tests/data/images
      zoom -s 71 -f julia --julia-re " -0.481762" --julia-im " -0.531657"
      auto "0" "0" "281/71" "223/73" "37/97" --fps 2 --duration "4.3"
  """
  with tempfile.TemporaryDirectory() as tmp_dir:
    r: subprocess.CompletedProcess[str] = tbase.Run(
      # call the console script directly to test the installed CLI
      [
        str(cli),
        '--no-db',
        '--force',
        '--opt',
        opt,
        '--palette',
        'sahara',
        '--set',
        'max',
        '--set-palette',
        'electric',
        '--no-date',
        '--out',
        tmp_dir,
        '--db-path',
        tmp_dir,
        'zoom',
        '-s',
        '71',
        '-f',
        'julia',
        '--julia-re',
        ' -0.481762',
        '--julia-im',
        ' -0.531657',
        'auto',
        '0',
        '0',
        '281/71',
        '223/73',
        '37/97',
        '--fps',
        '2',
        '--duration',
        '4.3',
      ]
    )
    assert r.returncode == 0, f'tranz image failed:\n{r.stderr}'
    # we check that the image is the same by trusting the 20-character hash in the file name;
    # the hash is from the internal representation and should only depend on our implementation;
    # resist the temptation of checking the PNG because PIL behaves differently across platforms
    # and Python versions, and we don't want to be debugging PIL differences in this test
    output_image: pathlib.Path = (
      pathlib.Path(tmp_dir) / f'julia-{base.T_GIF_JULIA_BLOB_HASH[:20]}.gif'
    )
    assert output_image.exists(), f'Expected output image not found: {output_image}'
    # check the image data
    w: int
    h: int
    hsh: str
    w, h, hsh, _ = image.GetBasicDataFromImage(output_image.read_bytes())
    assert (w, h) == (71, 55), f'Expected image dimensions 71x55, got {w} x {h}'
    assert hsh == base.T_GIF_JULIA_BLOB_HASH
