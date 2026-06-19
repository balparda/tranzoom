# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: frame.py."""

from __future__ import annotations

import gmpy2
import pytest

from tranzoom.core import frame

# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
COMPUTATION_STR_1: str = (
  '{"depth":9999,"frm":{"bottom_im":"-1","bottom_re":"1","fractal":"mandelbrot",'
  '"point_im":"0","point_re":"0","top_im":"1","top_re":"-1"},"height":512,'
  '"set_points":null,"width":512}'
)
COMPUTATION_STR_2: str = (
  '{"depth":6666,"frm":{"bottom_im":"-1","bottom_re":"1","fractal":"julia"'
  ',"point_im":"1","point_re":"1","top_im":"1","top_re":"-1"},"height":1024,'
  '"set_points":"imaginary","width":1024}'
)
COMPUTATION_STR_3: str = (
  '{"depth":8888,"frm":{"bottom_im":"-17/19","bottom_re":"1/31","fractal":"julia",'
  '"point_im":"-11/19","point_re":"3/2","top_im":"13/7","top_re":"-11/23"},'
  '"height":2048,"set_points":"max","width":2048}'
)
# DO NOT "JUST FIX" THESE! If they are wrong, it means something will break in the DB!


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'frc',
    't_re',
    't_im',
    'b_re',
    'b_im',
    'p_re',
    'p_im',
    'w',
    'h',
    'd',
    's',
    'json1',
    'sha1',
    'json2',
    'sha2',
    'txt1',
    'txt2',
  ),
  [
    pytest.param(
      'mandelbrot',
      '-1',
      '1',
      '1',
      '-1',
      '0',
      '0',
      512,
      512,
      9999,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"bottom_im":"-1","bottom_re":"1","fractal":"mandelbrot","point_im":"0","point_re":"0",'
        '"top_im":"1","top_re":"-1"}'
      ),
      '22c8b5cfc5b0ce22051d1e20d4c27c280d989f0ba65b58243b1b8955a6cd3182',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      COMPUTATION_STR_1,  # re-used in image_test.py to make sure it is all tied together
      '86f5d287f590adfeafb2878412a8a4bb7b9b56b8f250e797b0cf680e7a1f180e',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '[MANDELBROT: (0, 0) ± 2]',
      '{[MANDELBROT: (0, 0) ± 2] : [512 × 512, 9999]}',  # noqa: RUF001
      id='Frame-ComputationParameters-1',
    ),
    pytest.param(
      'julia',
      '-1',
      '1',
      '1',
      '-1',
      '1',
      '1',
      1024,
      1024,
      6666,
      'imaginary',
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"bottom_im":"-1","bottom_re":"1","fractal":"julia","point_im":"1",'
        '"point_re":"1","top_im":"1","top_re":"-1"}'
      ),
      '9e78d5b39bd5b12566406c5936d78075229149b38fce058a1cb86207d834ceca',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      COMPUTATION_STR_2,  # re-used in image_test.py to make sure it is all tied together
      'ea7e24f96db025c8c3a5fe2a7df3bd008fc9ce1e645aa9bdc5751d964779b15b',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '[JULIA: (0, 0) ± 2 @ (1, 1)]',
      '{[JULIA: (0, 0) ± 2 @ (1, 1)] : [1024 × 1024, 6666] : imaginary}',  # noqa: RUF001
      id='Frame-ComputationParameters-2',
    ),
    pytest.param(
      'julia',
      '-11/23',
      '13/7',
      '1/31',
      '-17/19',
      '3/2',
      '-11/19',
      2048,
      2048,
      8888,
      'max',
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"bottom_im":"-17/19","bottom_re":"1/31","fractal":"julia",'
        '"point_im":"-11/19","point_re":"3/2","top_im":"13/7","top_re":"-11/23"}'
      ),
      'cbff4724b845e1bfbffcca0f4e83822231cc053705f76b987504d601270b67a9',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      COMPUTATION_STR_3,  # re-used in image_test.py to make sure it is all tied together
      '877b0d190c32be56d7ac6fc7e9daafc5fda739d2ec3550b67790cf261f3ef683',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '[JULIA: (-159/713, 64/133) ± (364/713, 366/133) @ (3/2, -11/19)]',
      (
        '{[JULIA: (-159/713, 64/133) ± (364/713, 366/133) @ (3/2, -11/19)] : '
        '[2048 × 2048, 8888] : max}'  # noqa: RUF001
      ),
      id='Frame-ComputationParameters-3',
    ),
  ],
)
def test_frame_hash_stability_and_serialization_consistency(
  frc: str,
  t_re: str,
  t_im: str,
  b_re: str,
  b_im: str,
  p_re: str,
  p_im: str,
  w: int,
  h: int,
  d: int,
  s: str | None,
  json1: str,
  sha1: str,
  json2: str,
  sha2: str,
  txt1: str,
  txt2: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  # Frame
  frm: frame.Frame = frame.Frame(
    fractal=frame.Fractal(frc),
    top_re=gmpy2.mpq(t_re),
    top_im=gmpy2.mpq(t_im),
    bottom_re=gmpy2.mpq(b_re),
    bottom_im=gmpy2.mpq(b_im),
    point_re=gmpy2.mpq(p_re),
    point_im=gmpy2.mpq(p_im),
  )
  data: str = frm.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert frm.sha == sha1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert frame.Frame.FromJson(frm.json, check_hash=sha1) == frm, 'BIG PROBLEM: breaking JSON! BUG!'
  assert str(frm) == txt1
  # ComputationParameters
  cp: frame.ComputationParameters = frame.ComputationParameters(
    frm=frm,
    width=w,
    height=h,
    depth=d,
    set_points=frame.SetHighlightAlgorithm(s) if s else None,
  )
  data = cp.binary.decode('utf-8')
  assert data == json2, 'BIG PROBLEM: breaking JSON! BUG!'
  assert cp.sha == sha2, 'BIG PROBLEM: breaking JSON! BUG!'
  assert frame.ComputationParameters.FromJson(cp.json, check_hash=sha2) == cp, 'BIG PROBLEM! BUG!'
  assert json1 in data, 'BIG PROBLEM: breaking input JSON! BUG!'
  assert str(cp) == txt2


@pytest.mark.parametrize(
  (
    'inp',
    'out',
  ),
  [
    # empty
    pytest.param(
      [],
      [],
      id='SmoothDepths-empty',
    ),
    # singular
    pytest.param(
      [1000],
      [1001],
      id='SmoothDepths-singular',
    ),
    pytest.param(
      [1001],
      [1001],
      id='SmoothDepths-singular-2',
    ),
    pytest.param(
      [1500],
      [1500],
      id='SmoothDepths-singular-3',
    ),
    # repeated values
    pytest.param(
      [1000, 1000],
      [1001, 1001],
      id='SmoothDepths-repeated-2',
    ),
    pytest.param(
      [1000, 1000, 1000, 1000],
      [1001, 1001, 1001, 1001],
      id='SmoothDepths-repeated-4',
    ),
    pytest.param(
      [1500, 1500, 1500, 1500, 1500, 1500],
      [1500, 1500, 1500, 1500, 1500, 1500],
      id='SmoothDepths-repeated-6',
    ),
    # steps
    pytest.param(
      [1000, 1000, 5000],
      [1210, 1312, 2706],
      id='SmoothDepths-steps-3',
    ),
    pytest.param(
      [5000, 1000, 1000],
      [2706, 1312, 1210],
      id='SmoothDepths-steps-3-reversed',
    ),
    pytest.param(
      [1000, 1000, 1000, 1000, 1000, 1000, 5000, 5000, 5000, 5000, 5000, 5000],
      [1001, 1001, 1001, 1001, 1117, 1422, 3733, 4752, 5001, 5001, 5001, 5001],
      id='SmoothDepths-steps-12',
    ),
    pytest.param(
      [5000, 5000, 5000, 5000, 5000, 5000, 1000, 1000, 1000, 1000, 1000, 1000],
      [5001, 5001, 5001, 5001, 4752, 3733, 1422, 1117, 1001, 1001, 1001, 1001],
      id='SmoothDepths-steps-12-reversed',
    ),
    # spikes
    pytest.param(
      [1000, 1000, 1000, 1000, 10000, 1000, 1000, 1000, 1000],
      [1001, 1001, 1001, 1001, 1001, 1001, 1001, 1001, 1001],
      id='SmoothDepths-spikes-9',
    ),
    pytest.param(
      [10000, 10000, 10000, 10000, 1000, 10000, 10000, 10000, 10000],
      [10001, 10001, 10001, 10000, 10000, 10000, 10001, 10001, 10001],
      id='SmoothDepths-spikes-9-reversed',
    ),
    pytest.param(
      [1000, 1000, 1000, 10000, 10000, 10000, 1000, 1000, 1000],
      [1001, 1156, 1633, 6499, 8182, 6499, 1633, 1156, 1001],
      id='SmoothDepths-spikes-9-mixed',
    ),
    pytest.param(
      [10000, 10000, 10000, 1000, 1000, 1000, 10000, 10000, 10000],
      [10001, 9180, 6499, 1633, 1297, 1633, 6499, 9180, 10001],
      id='SmoothDepths-spikes-9-mixed-reversed',
    ),
    pytest.param(
      [1000, 1000, 1000, 1500, 2500, 5000, 9000, 2000, 13000, 20000],
      [1001, 1052, 1146, 1634, 2696, 4560, 6472, 4015, 10591, 14380],
      id='SmoothDepths-spikes-10-mixed',
    ),
    pytest.param(
      [1000, 17000, 1000, 17000, 3000, 20000, 5000, 5000, 8000, 8000, 9000, 3000, 1000, 1000, 1000],
      [2410, 7485, 2546, 8898, 5174, 11651, 6328, 6064, 7546, 7801, 6880, 3072, 1356, 1089, 1001],
      id='SmoothDepths-spikes-15-mixed',
    ),
  ],
)
def test_depth_smoothing(inp: list[int], out: list[int]) -> None:
  """Test."""
  assert frame.SmoothDepths(inp) == out


def test_frame_errors() -> None:
  """Test."""
  with pytest.raises(frame.Error, match=r'Unknown fractal type'):
    frame.Frame(
      fractal='sss',  # type: ignore[arg-type]
      top_re=gmpy2.mpq(2),
      top_im=gmpy2.mpq(2),
      bottom_re=gmpy2.mpq(3),
      bottom_im=gmpy2.mpq(1),
      point_re=gmpy2.mpq(0),
      point_im=gmpy2.mpq(0),
    )
  with pytest.raises(frame.Error, match=r'top_re.*must be < bottom_re'):
    frame.Frame(
      fractal=frame.Fractal('mandelbrot'),
      top_re=gmpy2.mpq(3),
      top_im=gmpy2.mpq(2),
      bottom_re=gmpy2.mpq(2),
      bottom_im=gmpy2.mpq(1),
      point_re=gmpy2.mpq(0),
      point_im=gmpy2.mpq(0),
    )
  with pytest.raises(frame.Error, match=r'top_im.*must be > bottom_im'):
    frame.Frame(
      fractal=frame.Fractal('mandelbrot'),
      top_re=gmpy2.mpq(-2),
      top_im=gmpy2.mpq(-1),
      bottom_re=gmpy2.mpq(2),
      bottom_im=gmpy2.mpq(1),
      point_re=gmpy2.mpq(0),
      point_im=gmpy2.mpq(0),
    )
  with pytest.raises(
    frame.Error, match=r'Mandelbrot frames should not have a non-zero point coordinate'
  ):
    frame.Frame(
      fractal=frame.Fractal('mandelbrot'),
      top_re=gmpy2.mpq(-2),
      top_im=gmpy2.mpq(2),
      bottom_re=gmpy2.mpq(2),
      bottom_im=gmpy2.mpq(1),
      point_re=gmpy2.mpq(1),
      point_im=gmpy2.mpq(0),
    )
  with pytest.raises(
    frame.Error, match=r'Mandelbrot frames should not have a non-zero point coordinate'
  ):
    frame.Frame(
      fractal=frame.Fractal('mandelbrot'),
      top_re=gmpy2.mpq(-2),
      top_im=gmpy2.mpq(2),
      bottom_re=gmpy2.mpq(2),
      bottom_im=gmpy2.mpq(1),
      point_re=gmpy2.mpq(0),
      point_im=gmpy2.mpq(2),
    )


def test_frame_asserts() -> None:
  """Test."""
  # mandelbrot frame
  frm = frame.Frame(
    fractal=frame.Fractal('mandelbrot'),
    top_re=gmpy2.mpq('-2/3'),
    top_im=gmpy2.mpq('1/2'),
    bottom_re=gmpy2.mpq('4/5'),
    bottom_im=gmpy2.mpq('1/4'),
    point_re=gmpy2.mpq(0),
    point_im=gmpy2.mpq(0),
  )
  assert str(frm) == '[MANDELBROT: (1/15, 3/8) ± (22/15, 1/4)]'
  assert frm.center == (gmpy2.mpq(1, 15), gmpy2.mpq(3, 8))
  assert frm.size == (gmpy2.mpq(22, 15), gmpy2.mpq(1, 4))
  assert not frm.is_square
  assert frm.scale == gmpy2.mpq(1, 4)
  assert frm.area == gmpy2.mpq(22, 15) * gmpy2.mpq(1, 4)
  # mandelbrot frame, square
  frm = frame.Frame(
    fractal=frame.Fractal('mandelbrot'),
    top_re=gmpy2.mpq(-4),
    top_im=gmpy2.mpq(4),
    bottom_re=gmpy2.mpq(4),
    bottom_im=gmpy2.mpq(-4),
    point_re=gmpy2.mpq(0),
    point_im=gmpy2.mpq(0),
  )
  assert frm.is_square
  assert str(frm) == '[MANDELBROT: (0, 0) ± 8]'
  assert frm.center == (gmpy2.mpq(0), gmpy2.mpq(0))
  assert frm.size == (gmpy2.mpq(8), gmpy2.mpq(8))
  assert frm.scale == gmpy2.mpq(8)
  assert frm.area == gmpy2.mpq(8) * gmpy2.mpq(8)
  # julia frame
  frm = frame.Frame(
    fractal=frame.Fractal('julia'),
    top_re=gmpy2.mpq(-2),
    top_im=gmpy2.mpq(2),
    bottom_re=gmpy2.mpq(2),
    bottom_im=gmpy2.mpq(1),
    point_re=gmpy2.mpq('1/2'),
    point_im=gmpy2.mpq('15/17'),
  )
  assert str(frm) == '[JULIA: (0, 3/2) ± (4, 1) @ (1/2, 15/17)]'
  assert frm.center == (gmpy2.mpq(0), gmpy2.mpq(3, 2))
  assert frm.size == (gmpy2.mpq(4), gmpy2.mpq(1))
  assert not frm.is_square
  assert frm.scale == gmpy2.mpq(1)
  assert frm.area == gmpy2.mpq(4) * gmpy2.mpq(1)
