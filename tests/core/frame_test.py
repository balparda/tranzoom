# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: frame.py."""

from __future__ import annotations

import gmpy2
import pytest

from tranzoom.core import frame


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
  ),
  [
    (
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
      '22c8b5cfc5b0ce22051d1e20d4c27c280d989f0ba65b58243b1b8955a6cd3182',
      (
        '{"depth":9999,"frm":{"bottom_im":"-1","bottom_re":"1","fractal":"mandelbrot",'
        '"point_im":"0","point_re":"0","top_im":"1","top_re":"-1"},"height":512,'
        '"set_points":null,"width":512}'
      ),
      '86f5d287f590adfeafb2878412a8a4bb7b9b56b8f250e797b0cf680e7a1f180e',
    ),
    (
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
      '9e78d5b39bd5b12566406c5936d78075229149b38fce058a1cb86207d834ceca',
      (
        '{"depth":6666,"frm":{"bottom_im":"-1","bottom_re":"1","fractal":"julia"'
        ',"point_im":"1","point_re":"1","top_im":"1","top_re":"-1"},"height":1024,'
        '"set_points":"imaginary","width":1024}'
      ),
      'ea7e24f96db025c8c3a5fe2a7df3bd008fc9ce1e645aa9bdc5751d964779b15b',
    ),
    (
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
      'cbff4724b845e1bfbffcca0f4e83822231cc053705f76b987504d601270b67a9',
      (
        '{"depth":8888,"frm":{"bottom_im":"-17/19","bottom_re":"1/31","fractal":"julia",'
        '"point_im":"-11/19","point_re":"3/2","top_im":"13/7","top_re":"-11/23"},'
        '"height":2048,"set_points":"max","width":2048}'
      ),
      '877b0d190c32be56d7ac6fc7e9daafc5fda739d2ec3550b67790cf261f3ef683',
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
  assert data == json1
  assert frm.sha == sha1
  assert frame.Frame.FromJson(frm.json, check_hash=sha1) == frm
  # ComputationParameters
  cp: frame.ComputationParameters = frame.ComputationParameters(
    frm=frm,
    width=w,
    height=h,
    depth=d,
    set_points=frame.SetHighlightAlgorithm(s) if s else None,
  )
  data = cp.binary.decode('utf-8')
  assert data == json2
  assert cp.sha == sha2
  assert frame.ComputationParameters.FromJson(cp.json, check_hash=sha2) == cp
  assert json1 in json2  # ComputationParameters JSON should contain the Frame JSON
