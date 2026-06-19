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
from transcrypto.core import hashes
from transcrypto.utils import base as tbase

from tranzoom.cli import base
from tranzoom.core import image, pixels


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


def _TestAllFramesDataOrFail(db_dir: str, name: str) -> None:
  # open the raw data file by searching for the hash
  expect_frames: int
  expect_hash: str
  expect_frames, expect_hash = base.TEST_IMAGE_DATA_HASHES[name]
  db_path: pathlib.Path = pathlib.Path(db_dir)
  for _, _, files in db_path.walk():
    frame_hashes: list[str] = sorted(
      hashes.FileHash(db_path / f).hex() for f in files if f.endswith('.Data')
    )
    n_frames: int = len(frame_hashes)
    assert n_frames == expect_frames, f'{expect_frames=} data files (frames), found {n_frames}'
    hsh: str = hashes.Hash256(('|'.join(frame_hashes)).encode('ascii')).hex()
    assert hsh == expect_hash, f'{expect_hash=!r} data hash, found {hsh!r}'
    break
  else:
    # loop completed without finding the directory, fail the test
    pytest.fail('No data files found in output directory')


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
  'opt',
  [
    # 'python',
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
        '--db',
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
        '--i-pixels',
        '2',
        'auto',
        ' -0.7436499',
        '0.13188204',
        '227/193',
        '167/193',
        '131/43',
        '--fps',
        '1',
        '--duration',
        '31.7',
        '--i-frames',
        '1',
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
    for f in sorted(pathlib.Path(tmp_dir).glob('**/*')):
      if f.is_file():
        print(f'Found file: {str(f)!r}')  # noqa: T201
    assert output_image.exists(), f'Expected output image not found: {output_image}'
    # check the image data
    info: pixels.ObjInfo
    info, _ = pixels.GetBasicData(output_image.read_bytes())
    assert (info.width, info.height) == (159, 117), f'Got invalid dim {info.width} x {info.height}'
    assert info.data_hash == base.T_GIF_SEAHORSE_HASH
    _TestAllFramesDataOrFail(tmp_dir, 'seahorse')
    del info.meta[image.META_APP_VERSION_KEY]  # remove the version key from comparison
    assert info.meta == {
      'tranZoom:computation:color_set': 'imaginary',
      'tranZoom:computation:depth': '1001',
      'tranZoom:computation:hash': (
        '8959a40f5f11daf66ef83811df3bc1c7085e8b5f294e7645be5a05d77f1de6aa'
      ),
      'tranZoom:computation:height': '39',
      'tranZoom:computation:width': '53',
      'tranZoom:frame:bottom_im': '96699539508749/735394975000000',
      'tranZoom:frame:bottom_re': '-22081923550741/29715090000000',
      'tranZoom:frame:center_im': '3297051/25000000',
      'tranZoom:frame:center_re': '-7436499/10000000',
      'tranZoom:frame:fractal': 'mandelbrot',
      'tranZoom:frame:hash': '111f79761282cfa9d1fd563fe54e087c9546ff9e5d76839f9dd3e12150f92501',
      'tranZoom:frame:height_im': '22868/29415799',
      'tranZoom:frame:magnification_order': '3.4406377814165787',
      'tranZoom:frame:precision': '140',
      'tranZoom:frame:top_im': '97271239508749/735394975000000',
      'tranZoom:frame:top_re': '-22113323863241/29715090000000',
      'tranZoom:frame:width_re': '100481/95088288',
      'tranZoom:image:animation': 'gif',
      'tranZoom:image:exterior:bucket:max': '1526934',
      'tranZoom:image:exterior:bucket:min': '74526',
      'tranZoom:image:exterior:count': '2066',
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{74526: 1, 74542: 2, 74571: 3, ...: 2114154, 1502841: 2064, 1516324: 2065, 1526934: 2066}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{74526: 1, 74542: 1, 74571: 1, ...: 2060, 1502841: 1, 1516324: 1, 1526934: 1}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{36: 49, 37: 150, 38: 245, ...: 499652, 733: 2064, 740: 2065, 745: 2066}'
      ),
      'tranZoom:image:exterior:hist:linear': (
        '{36: 49, 37: 101, 38: 95, ...: 1818, 733: 1, 740: 1, 745: 1}'
      ),
      'tranZoom:image:exterior:n:max': '745',
      'tranZoom:image:exterior:n:min': '36',
      'tranZoom:image:exterior:nu:max': '0.9993714690208435',
      'tranZoom:image:exterior:nu:min': '0.0004996695788577199',
      'tranZoom:image:hash': base.T_GIF_SEAHORSE_HASH,
      'tranZoom:image:set:bucket:max': '252200860659',
      'tranZoom:image:set:bucket:min': '252200860659',
      'tranZoom:image:set:count': '1',
      'tranZoom:image:set:hist:bucket:cumulative': '{252200860659: 1}',
      'tranZoom:image:set:hist:bucket': '{252200860659: 1}',
      'tranZoom:image:set:hist:linear:cumulative': '{123144951: 1}',
      'tranZoom:image:set:hist:linear': '{123144951: 1}',
      'tranZoom:image:set:n:max': '123144951',
      'tranZoom:image:set:n:min': '123144951',
      'tranZoom:image:set:nu:max': '0.49376627802848816',
      'tranZoom:image:set:nu:min': '0.49376627802848816',
      'tranZoom:image:stats:imag_hi': '0.05734383622578064069611499703175854039165102',
      'tranZoom:image:stats:imag_lo': '0.05734383622578064069611499703175854039165102',
      'tranZoom:render:hash': 'e5ed9b7875faed4f26e63f27117eb8ba8f88d58f0f6189d3b0dc55e5c895f584',
      'tranZoom:render:i_pixels': '2',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'lava',
      'tranZoom:render:set_palette': 'toxic',
      'tranZoom:zoom:depth:frames': (
        '[(0, 1000, 1041), (3, 1000, 1099), (6, 1257, 1368), (9, 1831, 1932), (12, 3015, 2929), '
        '(15, 3738, 3641), (18, 5245, 3890), (21, 1720, 1954), (24, 1000, 1214), (27, 1000, 1059), '
        '(30, 1000, 1001)]'
      ),
      'tranZoom:zoom:frame:all_frames': '61',
      'tranZoom:zoom:frame:fps': '310/317',
      'tranZoom:zoom:frame:frames': '31',
      'tranZoom:zoom:frame:i_frames': '1',
      'tranZoom:zoom:frame:ifps': '620/317',
      'tranZoom:zoom:frame:initial:height_im': '167/193',
      'tranZoom:zoom:frame:initial:width_re': '227/193',
      'tranZoom:zoom:frame:loop': '0',
      'tranZoom:zoom:frame:magnification_per_step': '711246553814769/562949953421312',
      'tranZoom:zoom:frame:magnitude_per_step': '131/1290',
      'tranZoom:zoom:frame:magnitude': '131/43',
      'tranZoom:zoom:frame:seconds': '317/10',
      'tranZoom:zoom:frame:steps': '30',
      'tranZoom:zoom:hash': 'f9eb196b73a9aa2706f48eb5b5d1c08283ddecd06483c34200aefb745d76af6e',
      'tranZoom:zoom:marker:index': '[0, 10, 20, 30]',
      'tranZoom:zoom:type': 'gif',
    }


@pytest.mark.skip
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
        '--db',
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
        '--i-pixels',
        '3',
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
        '1',
        '--duration',
        '10.1',
        '--i-frames',
        '1',
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
    info: pixels.ObjInfo
    info, _ = pixels.GetBasicData(output_image.read_bytes())
    assert (info.width, info.height) == (124, 104), f'Got invalid dim {info.width} x {info.height}'
    assert info.data_hash == base.T_GIF_SEEDS_300_HASH
    _TestAllFramesDataOrFail(tmp_dir, 'seeds300')
    del info.meta[image.META_APP_VERSION_KEY]  # remove the version key from comparison
    assert info.meta == {
      'tranZoom:computation:color_set': 'none',
      'tranZoom:computation:depth': '9817',
      'tranZoom:computation:hash': (
        '6ca553ab67a091b1bddcce8f4db7a311ab5e1cd94abcc61da470b46b0a622e43'
      ),
      'tranZoom:computation:height': '26',
      'tranZoom:computation:width': '31',
      'tranZoom:frame:bottom_im': (
        '-39076868312110980191702347725471580174308659246384206881373036873133471556093711930514781'
        '208129519017167237492782588747943919099609022553874864048453839589614166615743523032371970'
        '646142813547380587361385814997196352447092589211200578956247749831235344967365795394865132'
        '710043531102162385303579802657550654259061581843947712027349768571476496984732083973319873'
        '147950527311878073030658942196392834743362663646193249079135105524178402116262052754638498'
        '808122090849367173165029172794598907025230286838388406335071572014983453092318654820337531'
        '571346188461896023595620460534191585884807675564913790931438980979191746125375071703824910'
        '361622804836045793788582300900180495465215588251067442814300778897402396940226192043770846'
        '984774140198467174986234261125047003572105245433633398287805194087902946377518142132743987'
        '387454170375700843448855806968745059113824020956072852301793335394759909805856214315793652'
        '13523555115316793679986794164675418901952321057473061476826370870437/568512055457722544988'
        '520442128591258746837770148953409348329811416455417881193359825462800108844909539987845197'
        '503566326081163040471474586954310133041106528258399435191212215752851729076746825426662942'
        '978916797014516898785794855317916025371258502437048845366802292693268855260280626126398539'
        '788936554294835438881360391351821782237641944981646897089930081377941870993089274435090254'
        '463135279103115863798079306489686450425394255434596582712265518188622000709200157336439154'
        '272719054402859817365367689490085467696189880371093750000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '00000000000000000000000000000000000000000000000'
      ),
      'tranZoom:frame:bottom_re': (
        '517028306786156748207905968515376602938414811736783171426704456764187592790793647068138619'
        '517587960750200227617613233314502656951887097774541207328253776965167550885036613450086127'
        '866119237521835464564220964333946548339622761619169469639326185818517610765785113810829951'
        '764158400737827690460443115003823839126687487714008377045978827874512551219170247390936714'
        '960268051449503530594476832804956983783067360603048586435320737095786173067738532877786650'
        '795137565021128327941387287829736989719609718289063694277181614037917435831475959804022475'
        '963478083127191660656145597128864261712236943408219005969412137212899702183582271134551613'
        '819315192148081414400782287622999553047606599545081737426193790767702403603148756054881896'
        '893760603159400183685354348850778514286502567315483740793989896321378898642186435492404602'
        '587837882679774428256484801349677063128946048740425101564244156605134157511347494212905778'
        '2957886164141096441979828566552033771430193601596696190149148700827/1432305121271803031553'
        '461707355267384518297616427902597904296411478080714462221374141224854849032740671408174688'
        '354358567881495274922544600220356018829178242511512601179202453613646001281899921548855353'
        '641075428696590686989724510057925587992893447666103656245728793573672500824825594510897297'
        '259522853209533630788990342132064436957415846647066397302760678958745694296576649345095934'
        '743597551809221184012592443040790403257442352405820841365333946694742671296291238854747634'
        '398848084823219206640487755066715180873870849609375000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '0000000000000000000000000000000000000000000000'
      ),
      'tranZoom:frame:center_im': (
        '-45308962242651415074935977011396927661365957855897079708592971604257615026323365837499592'
        '289363147051742124069409717446199862560834872190779195465969792302619277572998963235316641'
        '670939954888561414362014796590930949745991300294178720406678295213137333919392652851085347'
        '369348655477867143897857996625326253873738525516201676593960188313107410496081736711184898'
        '531748636396616104327120197340429878249875761946135367780756092678070943283873927366816912'
        '857249392571479387075934169516044073073207299290720930149839122100050371110750768930867445'
        '727297525048751834640544796002635328032740778350735933171961973171295248413057491520157784'
        '8399770363925784839040557686809517/6591800307406615244635435974713016610440352861022210109'
        '402714879035419653556991506477182217335284603887819737209039387651958875087240223136094075'
        '081201000729343769544562802882559614248147994430837570689618587493896484375000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000'
      ),
      'tranZoom:frame:center_re': (
        '285538099472939787286675780184362133800210109743945494992911451222746843500926869335827185'
        '449997362418699334200339620867561170042072027343532325438857074116884615073223091462958537'
        '231824127891337679111739059888029368087278724647736484597161472714659142532530001112712838'
        '065047567339917837862743135380791823825750950743495447670695395168589925329160074345544976'
        '627385655740529292321789962898823028165297748132328040587052140820721492744489869366392129'
        '350928785839288142612302119557940667379400037081408423872094697484146465750438708629663709'
        '117480845120140711120322265675414322508120758623470019110959700362861632263692036703632960'
        '2344606218392288635283937429076929/7910160368887938293562523169655619932528423433226652131'
        '283257854842503584268389807772618660802341524665383684650847265182350650104688267763312890'
        '097441200875212523453475363459071537097777593317005084827542304992675781250000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000'
      ),
      'tranZoom:frame:fractal': 'mandelbrot',
      'tranZoom:frame:hash': '64e1df0c8ba1d13fce3ac76bdd9021f400325c930163217c21c28f799bfeea9c',
      'tranZoom:frame:height_im': (
        '160483/86245339504435002170228572924903009424212147184369870983724665203823662500394606627'
        '464193446234879407996810770347693082244286703815982617024531190694651062067719367074640757'
        '458638435146605652093451213745803133350587341753592686422194344548826043888973531049538688'
        '15086719773321453708559853400679518284761'
      ),
      'tranZoom:frame:magnification_order': '299.0885135491683',
      'tranZoom:frame:precision': '1114',
      'tranZoom:frame:top_im': (
        '-39076868312110980191702347725471580174308659246384206881373036873133471556093711930514781'
        '208129519017167237492782588747943919099609022553874864048453839589614166615743523032371970'
        '646142813547380587361385814997196352447092589211200578956247749831235344967365795394865132'
        '710043531102162385303579802646971935371726223500899425312051078124543505502777810523447114'
        '228628114789260206351319165858546649952505373897328066398649612362672146388966554900125935'
        '006121618087688972442079154648865051679327845779818585737303742119963921842318654820337531'
        '571346188461896023595620460534191585884807675564913790931438980979191746125375071703824910'
        '361622804836045793788582300900180495465215588251067442814300778897402396940226192043770846'
        '984774140198467174986234261125047003572105245433633398287805194087902946377518142132743987'
        '387454170375700843448855806968745059113824020956072852301793335394759909805856214315793652'
        '13523555115316793679986794164675418901952321057473061476826370870437/568512055457722544988'
        '520442128591258746837770148953409348329811416455417881193359825462800108844909539987845197'
        '503566326081163040471474586954310133041106528258399435191212215752851729076746825426662942'
        '978916797014516898785794855317916025371258502437048845366802292693268855260280626126398539'
        '788936554294835438881360391351821782237641944981646897089930081377941870993089274435090254'
        '463135279103115863798079306489686450425394255434596582712265518188622000709200157336439154'
        '272719054402859817365367689490085467696189880371093750000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '00000000000000000000000000000000000000000000000'
      ),
      'tranZoom:frame:top_re': (
        '517028306786156748207905968515376602938414811736783171426704456764187592790793647068138619'
        '517587960750200227617613233314502656951887097774541207328253776965167550885036613450086127'
        '866119237521835464564220964333946548339622761619169469639326185818517610765785113810829951'
        '764158400737827690460443114971820516798222222568998442680027637970492429271850196865584346'
        '168253508323091265690699983596149830325499918022503956027482723718060120039608333421385918'
        '312576586433114084642136403251369946243688113266614182242526996728347123331475959804022475'
        '963478083127191660656145597128864261712236943408219005969412137212899702183582271134551613'
        '819315192148081414400782287622999553047606599545081737426193790767702403603148756054881896'
        '893760603159400183685354348850778514286502567315483740793989896321378898642186435492404602'
        '587837882679774428256484801349677063128946048740425101564244156605134157511347494212905778'
        '2957886164141096441979828566552033771430193601596696190149148700827/1432305121271803031553'
        '461707355267384518297616427902597904296411478080714462221374141224854849032740671408174688'
        '354358567881495274922544600220356018829178242511512601179202453613646001281899921548855353'
        '641075428696590686989724510057925587992893447666103656245728793573672500824825594510897297'
        '259522853209533630788990342132064436957415846647066397302760678958745694296576649345095934'
        '743597551809221184012592443040790403257442352405820841365333946694742671296291238854747634'
        '398848084823219206640487755066715180873870849609375000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '0000000000000000000000000000000000000000000000'
      ),
      'tranZoom:frame:width_re': (
        '80917/362143130980077913555530042982449948612923809137290746182721642343740616176859817061'
        '779203994458712436514034738059271976110248456329050493807595687483476124745708032911915876'
        '796364448022634938364490704570406904627493231630696533494242481651091316513372406194624280'
        '2883764194012570979895967021606543353526'
      ),
      'tranZoom:image:animation': 'gif',
      'tranZoom:image:exterior:bucket:max': '13459247',
      'tranZoom:image:exterior:bucket:min': '13207291',
      'tranZoom:image:exterior:count': '806',
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{13207291: 1, 13207591: 2, 13207977: 3, ...: 320834, 13434519: 804, 13445669: 805, '
        '13459247: 806}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{13207291: 1, 13207591: 1, 13207977: 1, ...: 800, 13434519: 1, 13445669: 1, 13459247: 1}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{6448: 1, 6449: 13, 6450: 28, ...: 49210, 6559: 804, 6565: 805, 6571: 806}'
      ),
      'tranZoom:image:exterior:hist:linear': (
        '{6448: 1, 6449: 12, 6450: 15, ...: 775, 6559: 1, 6565: 1, 6571: 1}'
      ),
      'tranZoom:image:exterior:n:max': '6571',
      'tranZoom:image:exterior:n:min': '6448',
      'tranZoom:image:exterior:nu:max': '0.9996468424797058',
      'tranZoom:image:exterior:nu:min': '0.0002610799274407327',
      'tranZoom:image:hash': base.T_GIF_SEEDS_300_HASH,
      'tranZoom:image:set:bucket:max': '0',
      'tranZoom:image:set:bucket:min': '0',
      'tranZoom:image:set:count': '0',
      'tranZoom:image:set:n:max': '0',
      'tranZoom:image:set:n:min': '0',
      'tranZoom:image:set:nu:max': '0.0',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:render:hash': '25389b1c9ca4c515a1a40711aff3bfeb638a43f0ff3152cef955c4875701324f',
      'tranZoom:render:i_pixels': '3',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'electric',
      'tranZoom:render:set_palette': 'none',
      'tranZoom:zoom:depth:frames': (
        '[(0, 9786, 9805), (3, 9828, 9823), (6, 9816, 9819), (9, 9813, 9817)]'
      ),
      'tranZoom:zoom:frame:all_frames': '19',
      'tranZoom:zoom:frame:fps': '100/101',
      'tranZoom:zoom:frame:frames': '10',
      'tranZoom:zoom:frame:i_frames': '1',
      'tranZoom:zoom:frame:ifps': '200/101',
      'tranZoom:zoom:frame:initial:height_im': (
        '127/61000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '0000000000000000000000000000000000'
      ),
      'tranZoom:zoom:frame:initial:width_re': (
        '1/4000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000'
      ),
      'tranZoom:zoom:frame:loop': '0',
      'tranZoom:zoom:frame:magnification_per_step': '5889669701941943/4503599627370496',
      'tranZoom:zoom:frame:magnitude_per_step': '43/369',
      'tranZoom:zoom:frame:magnitude': '43/41',
      'tranZoom:zoom:frame:seconds': '101/10',
      'tranZoom:zoom:frame:steps': '9',
      'tranZoom:zoom:hash': 'b14e515756b728bf45b4f6c721da0324c5cd2b58b5632c2c5afd878628043910',
      'tranZoom:zoom:marker:index': '[0, 9]',
      'tranZoom:zoom:type': 'gif',
    }


@pytest.mark.skip
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
        '--db',
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
        '--i-pixels',
        '1',
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
        '--i-frames',
        '2',
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
    info: pixels.ObjInfo
    info, _ = pixels.GetBasicData(output_image.read_bytes())
    assert (info.width, info.height) == (88, 118), f'Got invalid dim {info.width} x {info.height}'
    assert info.data_hash == base.T_GIF_JULIA_SUZANA_HASH
    _TestAllFramesDataOrFail(tmp_dir, 'suzana')
    del info.meta[image.META_APP_VERSION_KEY]  # remove the version key from comparison
    assert info.meta == {
      'tranZoom:computation:color_set': 'angle',
      'tranZoom:computation:depth': '1001',
      'tranZoom:computation:hash': (
        '24b288bbcb7b6241e38548b0857308f9aeb6224326e0ba058fe4d6fab12484eb'
      ),
      'tranZoom:computation:height': '59',
      'tranZoom:computation:width': '44',
      'tranZoom:frame:bottom_im': '5179335449/8019470000',
      'tranZoom:frame:bottom_re': '-1661670927454749/2303304179687500',
      'tranZoom:frame:center_im': '6567/10000',
      'tranZoom:frame:center_re': '-313420497/429687500',
      'tranZoom:frame:fractal': 'julia',
      'tranZoom:frame:hash': '0d051b96ced8c90c22901770196176361c068580839a040fe949b37106320eb4',
      'tranZoom:frame:height_im': '174101/8019470',
      'tranZoom:frame:julia_im': '371/50000',
      'tranZoom:frame:julia_re': '13667/50000',
      'tranZoom:frame:magnification_order': '2.0288466874405366',
      'tranZoom:frame:precision': '140',
      'tranZoom:frame:top_im': '5353436449/8019470000',
      'tranZoom:frame:top_re': '-1698458193079749/2303304179687500',
      'tranZoom:frame:width_re': '85614/5360417',
      'tranZoom:image:animation': 'gif',
      'tranZoom:image:exterior:bucket:max': '1886769',
      'tranZoom:image:exterior:bucket:min': '46915',
      'tranZoom:image:exterior:count': '724',
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{46915: 1, 47140: 2, 47153: 3, ...: 259768, 1271356: 722, 1491852: 723, 1886769: 724}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{46915: 1, 47140: 1, 47153: 1, ...: 718, 1271356: 1, 1491852: 1, 1886769: 1}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{22: 1, 23: 42, 24: 106, ...: 62065, 620: 722, 728: 723, 921: 724}'
      ),
      'tranZoom:image:exterior:hist:linear': (
        '{22: 1, 23: 41, 24: 64, ...: 615, 620: 1, 728: 1, 921: 1}'
      ),
      'tranZoom:image:exterior:n:max': '921',
      'tranZoom:image:exterior:n:min': '22',
      'tranZoom:image:exterior:nu:max': '0.9980702996253967',
      'tranZoom:image:exterior:nu:min': '0.0027492588851600885',
      'tranZoom:image:hash': base.T_GIF_JULIA_SUZANA_HASH,
      'tranZoom:image:set:bucket:max': '4398046509056',
      'tranZoom:image:set:bucket:min': '2048',
      'tranZoom:image:set:count': '1872',
      'tranZoom:image:set:hist:bucket:cumulative': (
        '{2048: 7, 11087: 8, 7220808613: 9, ...: 378037, 4398046508957: 1850, 4398046509051: 1851, '
        '4398046509056: 1872}'
      ),
      'tranZoom:image:set:hist:bucket': (
        '{2048: 7, 11087: 1, 7220808613: 1, ...: 1840, 4398046508957: 1, 4398046509051: 1, '
        '4398046509056: 21}'
      ),
      'tranZoom:image:set:hist:linear:cumulative': (
        '{1: 7, 5: 8, 3525785: 9, ...: 84277, 2147483638: 1848, 2147483646: 1851, 2147483647: 1872}'
      ),
      'tranZoom:image:set:hist:linear': (
        '{1: 7, 5: 1, 3525785: 1, ...: 1838, 2147483638: 1, 2147483646: 3, 2147483647: 21}'
      ),
      'tranZoom:image:set:n:max': '2147483647',
      'tranZoom:image:set:n:min': '1',
      'tranZoom:image:set:nu:max': '0.9980466961860657',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:image:stats:ang_hi': '0.73519948957591444695345637018854658157873099',
      'tranZoom:image:stats:ang_lo': '0.50658202515724162651223774275343995527044469',
      'tranZoom:render:hash': '5b5881924bb9d30d8aaec378d3053b0484bdf141e4ccfbe6143df82d67321c0b',
      'tranZoom:render:i_pixels': '1',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'sahara',
      'tranZoom:render:set_palette': 'iris',
      'tranZoom:zoom:depth:frames': (
        '[(0, 1000, 1001), (4, 1000, 1001), (8, 1000, 1001), (12, 1000, 1001), (16, 1000, 1001), '
        '(20, 1000, 1001)]'
      ),
      'tranZoom:zoom:frame:all_frames': '61',
      'tranZoom:zoom:frame:fps': '210/107',
      'tranZoom:zoom:frame:frames': '21',
      'tranZoom:zoom:frame:i_frames': '2',
      'tranZoom:zoom:frame:ifps': '630/107',
      'tranZoom:zoom:frame:initial:height_im': '227/193',
      'tranZoom:zoom:frame:initial:width_re': '167/193',
      'tranZoom:zoom:frame:loop': '0',
      'tranZoom:zoom:frame:magnification_per_step': '1374644600961205/1125899906842624',
      'tranZoom:zoom:frame:magnitude_per_step': '241/2780',
      'tranZoom:zoom:frame:magnitude': '241/139',
      'tranZoom:zoom:frame:seconds': '107/10',
      'tranZoom:zoom:frame:steps': '20',
      'tranZoom:zoom:hash': '621d6d2b88c7842bdc701b7e8d18533080f784d8c000f89742cdd0ee05f0f961',
      'tranZoom:zoom:marker:index': '[0, 20]',
      'tranZoom:zoom:type': 'gif',
    }


@pytest.mark.skip
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
        '--db',
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
        '--i-pixels',
        '1',
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
        '--i-frames',
        '3',
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
    info: pixels.ObjInfo
    info, _ = pixels.GetBasicData(output_image.read_bytes())
    assert (info.width, info.height) == (104, 134), f'Got invalid dim {info.width} x {info.height}'
    assert info.data_hash == base.T_GIF_JULIA_DRAGON_HASH
    _TestAllFramesDataOrFail(tmp_dir, 'dragon')
    del info.meta[image.META_APP_VERSION_KEY]  # remove the version key from comparison
    assert info.meta == {
      'tranZoom:computation:color_set': 'min',
      'tranZoom:computation:depth': '1001',
      'tranZoom:computation:hash': (
        'c878daaf63961fe371aa568b7ea577635a9758975a82d4f696e0ca0947ab144a'
      ),
      'tranZoom:computation:height': '67',
      'tranZoom:computation:width': '52',
      'tranZoom:frame:bottom_im': '-161359/196254',
      'tranZoom:frame:bottom_re': '115021/181246',
      'tranZoom:frame:center_im': '0',
      'tranZoom:frame:center_re': '0',
      'tranZoom:frame:fractal': 'julia',
      'tranZoom:frame:hash': 'ccd1eadcbab432486b16ab25fada135a857f24a954ba9e46618c7203a2daea7b',
      'tranZoom:frame:height_im': '161359/98127',
      'tranZoom:frame:julia_im': '6557/10000',
      'tranZoom:frame:julia_re': '-11/100',
      'tranZoom:frame:magnification_order': '0.13907590484916504',
      'tranZoom:frame:precision': '140',
      'tranZoom:frame:top_im': '161359/196254',
      'tranZoom:frame:top_re': '-115021/181246',
      'tranZoom:frame:width_re': '115021/90623',
      'tranZoom:image:animation': 'gif',
      'tranZoom:image:exterior:bucket:max': '492629',
      'tranZoom:image:exterior:bucket:min': '5899',
      'tranZoom:image:exterior:count': '1284',
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{5899: 2, 6010: 4, 6022: 6, ...: 403408, 426446: 1280, 467652: 1282, 492629: 1284}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{5899: 2, 6010: 2, 6022: 2, ...: 1272, 426446: 2, 467652: 2, 492629: 2}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{2: 10, 3: 210, 4: 426, ...: 55214, 208: 1280, 228: 1282, 240: 1284}'
      ),
      'tranZoom:image:exterior:hist:linear': (
        '{2: 10, 3: 200, 4: 216, ...: 852, 208: 2, 228: 2, 240: 2}'
      ),
      'tranZoom:image:exterior:n:max': '240',
      'tranZoom:image:exterior:n:min': '2',
      'tranZoom:image:exterior:nu:max': '0.9997831583023071',
      'tranZoom:image:exterior:nu:min': '0.0030895813833922148',
      'tranZoom:image:hash': base.T_GIF_JULIA_DRAGON_HASH,
      'tranZoom:image:set:bucket:max': '4398046509056',
      'tranZoom:image:set:bucket:min': '2048',
      'tranZoom:image:set:count': '2200',
      'tranZoom:image:set:hist:bucket:cumulative': (
        '{2048: 34, 34497338586: 36, 42052086890: 40, ...: 1189206, 4375342438586: 2190, '
        '4377405754921: 2192, 4398046509056: 2200}'
      ),
      'tranZoom:image:set:hist:bucket': (
        '{2048: 34, 34497338586: 2, 42052086890: 4, ...: 2148, 4375342438586: 2, 4377405754921: 2, '
        '4398046509056: 8}'
      ),
      'tranZoom:image:set:hist:linear:cumulative': (
        '{1: 34, 16844403: 36, 20533245: 40, ...: 1189206, 2136397675: 2190, 2137405153: 2192, '
        '2147483647: 2200}'
      ),
      'tranZoom:image:set:hist:linear': (
        '{1: 34, 16844403: 2, 20533245: 4, ...: 2148, 2136397675: 2, 2137405153: 2, 2147483647: 8}'
      ),
      'tranZoom:image:set:n:max': '2147483647',
      'tranZoom:image:set:n:min': '1',
      'tranZoom:image:set:nu:max': '0.9982959032058716',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:image:stats:min_hi': '0.082874941584400487748646457435133671445430575',
      'tranZoom:image:stats:min_lo': '3.6863012726222845779975027843355758506749315e-05',
      'tranZoom:render:hash': 'd692016a50498841ea7b5c2982f4cef2c3be3b2deec5b9f82cfc3a112f3c94f5',
      'tranZoom:render:i_pixels': '1',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'lava',
      'tranZoom:render:set_palette': 'electric',
      'tranZoom:zoom:depth:frames': '[(0, 1000, 1001), (7, 1000, 1001)]',
      'tranZoom:zoom:frame:all_frames': '29',
      'tranZoom:zoom:frame:fps': '80/41',
      'tranZoom:zoom:frame:frames': '8',
      'tranZoom:zoom:frame:i_frames': '3',
      'tranZoom:zoom:frame:ifps': '320/41',
      'tranZoom:zoom:frame:initial:height_im': '281/71',
      'tranZoom:zoom:frame:initial:width_re': '223/73',
      'tranZoom:zoom:frame:loop': '0',
      'tranZoom:zoom:frame:magnification_per_step': '2552828729256545/2251799813685248',
      'tranZoom:zoom:frame:magnitude_per_step': '37/679',
      'tranZoom:zoom:frame:magnitude': '37/97',
      'tranZoom:zoom:frame:seconds': '41/10',
      'tranZoom:zoom:frame:steps': '7',
      'tranZoom:zoom:hash': '8b1eac4479ba0f194e4ab174b614cd794e2c686054c015953ed63ba3b45e67a0',
      'tranZoom:zoom:marker:index': '[0, 7]',
      'tranZoom:zoom:type': 'gif',
    }


@pytest.mark.skip
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
        '--db',
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
        '--i-pixels',
        '1',
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
        '--i-frames',
        '3',
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
    info: pixels.ObjInfo
    info, _ = pixels.GetBasicData(output_image.read_bytes())
    assert (info.width, info.height) == (142, 110), f'Got invalid dim {info.width} x {info.height}'
    assert info.data_hash == base.T_GIF_JULIA_BLOB_HASH
    _TestAllFramesDataOrFail(tmp_dir, 'blob')
    del info.meta[image.META_APP_VERSION_KEY]  # remove the version key from comparison
    assert info.meta == {
      'tranZoom:computation:color_set': 'max',
      'tranZoom:computation:depth': '1001',
      'tranZoom:computation:hash': (
        '0b54b4db9635c88b4fed55f6cb9c05a59142bfbb98f949558eb44d8c45376085'
      ),
      'tranZoom:computation:height': '55',
      'tranZoom:computation:width': '71',
      'tranZoom:frame:bottom_im': '-115021/181246',
      'tranZoom:frame:bottom_re': '161359/196254',
      'tranZoom:frame:center_im': '0',
      'tranZoom:frame:center_re': '0',
      'tranZoom:frame:fractal': 'julia',
      'tranZoom:frame:hash': '35d6e37a25bb887fd83cfdb362b78a80969ba82a856c08024cf1e67dcf8805f4',
      'tranZoom:frame:height_im': '115021/90623',
      'tranZoom:frame:julia_im': '-531657/1000000',
      'tranZoom:frame:julia_re': '-240881/500000',
      'tranZoom:frame:magnification_order': '0.13907590484916504',
      'tranZoom:frame:precision': '140',
      'tranZoom:frame:top_im': '115021/181246',
      'tranZoom:frame:top_re': '-161359/196254',
      'tranZoom:frame:width_re': '161359/98127',
      'tranZoom:image:animation': 'gif',
      'tranZoom:image:exterior:bucket:max': '748986',
      'tranZoom:image:exterior:bucket:min': '6010',
      'tranZoom:image:exterior:count': '1478',
      'tranZoom:image:exterior:hist:bucket:cumulative': (
        '{6010: 2, 6108: 4, 6137: 6, ...: 537404, 119830: 1474, 143477: 1476, 748986: 1478}'
      ),
      'tranZoom:image:exterior:hist:bucket': (
        '{6010: 2, 6108: 2, 6137: 2, ...: 1466, 119830: 2, 143477: 2, 748986: 2}'
      ),
      'tranZoom:image:exterior:hist:linear:cumulative': (
        '{2: 6, 3: 234, 4: 494, ...: 41066, 58: 1474, 70: 1476, 365: 1478}'
      ),
      'tranZoom:image:exterior:hist:linear': (
        '{2: 6, 3: 228, 4: 260, ...: 978, 58: 2, 70: 2, 365: 2}'
      ),
      'tranZoom:image:exterior:n:max': '365',
      'tranZoom:image:exterior:n:min': '2',
      'tranZoom:image:exterior:nu:max': '0.9997887015342712',
      'tranZoom:image:exterior:nu:min': '0.001498788595199585',
      'tranZoom:image:hash': base.T_GIF_JULIA_BLOB_HASH,
      'tranZoom:image:set:bucket:max': '4398046509056',
      'tranZoom:image:set:bucket:min': '404761495',
      'tranZoom:image:set:count': '2427',
      'tranZoom:image:set:hist:bucket:cumulative': (
        '{404761495: 2, 706980550: 4, 44872488558: 6, ...: 1467047, 4188566751411: 2423, '
        '4204283012687: 2425, 4398046509056: 2427}'
      ),
      'tranZoom:image:set:hist:bucket': (
        '{404761495: 2, 706980550: 2, 44872488558: 2, ...: 2415, 4188566751411: 2, '
        '4204283012687: 2, 4398046509056: 2}'
      ),
      'tranZoom:image:set:hist:linear:cumulative': (
        '{197637: 2, 345205: 4, 21910394: 6, ...: 1467047, 2045198609: 2423, 2052872564: 2425, '
        '2147483647: 2427}'
      ),
      'tranZoom:image:set:hist:linear': (
        '{197637: 2, 345205: 2, 21910394: 2, ...: 2415, 2045198609: 2, 2052872564: 2, '
        '2147483647: 2}'
      ),
      'tranZoom:image:set:n:max': '2147483647',
      'tranZoom:image:set:n:min': '197637',
      'tranZoom:image:set:nu:max': '0.999273419380188',
      'tranZoom:image:set:nu:min': '0.0',
      'tranZoom:image:stats:max_hi': '1.9748028908146782087476064434619381192680041',
      'tranZoom:image:stats:max_lo': '0.26279710060872639895079446071425291716398127',
      'tranZoom:render:hash': 'bdfaebb0bd66c67a5a8b3fb19316040421d9fb2b86db4037abc67ddea6eaf20b',
      'tranZoom:render:i_pixels': '1',
      'tranZoom:render:mark_color': 'none',
      'tranZoom:render:mark_im': '0',
      'tranZoom:render:mark_re': '0',
      'tranZoom:render:mark_width': '1',
      'tranZoom:render:overlay': 'none',
      'tranZoom:render:palette': 'sahara',
      'tranZoom:render:set_palette': 'electric',
      'tranZoom:zoom:depth:frames': '[(0, 1000, 1001), (7, 1000, 1001)]',
      'tranZoom:zoom:frame:all_frames': '29',
      'tranZoom:zoom:frame:fps': '80/43',
      'tranZoom:zoom:frame:frames': '8',
      'tranZoom:zoom:frame:i_frames': '3',
      'tranZoom:zoom:frame:ifps': '320/43',
      'tranZoom:zoom:frame:initial:height_im': '223/73',
      'tranZoom:zoom:frame:initial:width_re': '281/71',
      'tranZoom:zoom:frame:loop': '0',
      'tranZoom:zoom:frame:magnification_per_step': '2552828729256545/2251799813685248',
      'tranZoom:zoom:frame:magnitude_per_step': '37/679',
      'tranZoom:zoom:frame:magnitude': '37/97',
      'tranZoom:zoom:frame:seconds': '43/10',
      'tranZoom:zoom:frame:steps': '7',
      'tranZoom:zoom:hash': '558e31a6c4f3ef7200e9b22b9eadb41a33a22fa15b4cf4fa8040184a619b58e5',
      'tranZoom:zoom:marker:index': '[0, 7]',
      'tranZoom:zoom:type': 'gif',
    }
