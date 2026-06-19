# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: zoom.py."""

from __future__ import annotations

import json

import gmpy2
import pytest

from tests.core import frame_test, pixels_test
from tranzoom.core import frame, pixels, zoom


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'i_json',
    'r_json',
    'mag',
    'nf',
    'd',
    'lo',
    'json1',
    'sha',
    'txt',
  ),
  [
    pytest.param(
      frame_test.COMPUTATION_STR_1,  # re-used from frame_test.py, ties it all together
      pixels_test.ANIM_STR_1,  # re-used from above (render), ties it all together
      '40/3',
      17,
      80000,
      0,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":80000,"img":{"depth":9999,"frm":{"bottom_im":"-1","bottom_re":"1",'
        '"fractal":"mandelbrot","point_im":"0","point_re":"0","top_im":"1","top_re":"-1"},'
        '"height":512,"set_points":null,"width":512},"loop":0,"mag":"40/3","n_frames":17,'
        '"render":{"anim":"gif","i_frames":0,"render":{"escaped_pal":"sunset","i_pixels":1,'
        '"mark_color":null,"mark_im":"0","mark_re":"0","mark_width":1,"overlay":null,'
        '"set_pal":"rgrayscale","tp":"png"}}}'
      ),
      'b83f2dfefc65ae813aae7a6bf32bf76583142eefafcf35e894277c9a3d68f287',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      (
        '<{[MANDELBROT: (0, 0) ± 2] : [512 × 512, 9999]} -> '  # noqa: RUF001
        '<GIF*1: {[PNG*2: SUNSET, GRAYSCALE_REVERSE]}> / '
        '(mag:40/3, n:17|17, d:2, fps:(17/2)*1, l:0)>'
      ),
      id='ZoomParameters-1',
    ),
    pytest.param(
      frame_test.COMPUTATION_STR_2,  # re-used from frame_test.py, ties it all together
      pixels_test.ANIM_STR_2,  # re-used from above (render), ties it all together
      '3/7',
      1000,
      3000000,
      0,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":3000000,"img":{"depth":6666,"frm":{"bottom_im":"-1","bottom_re":"1",'
        '"fractal":"julia","point_im":"1","point_re":"1","top_im":"1","top_re":"-1"},'
        '"height":1024,"set_points":"imaginary","width":1024},"loop":0,"mag":"3/7",'
        '"n_frames":1000,"render":{"anim":"mp4","i_frames":1,"render":'
        '{"escaped_pal":"electric","i_pixels":0,"mark_color":"red","mark_im":"9/2",'
        '"mark_re":"-11/17","mark_width":2,"overlay":"grid","set_pal":null,"tp":"png"}}}'
      ),
      'fff17a04368fe6a2430d0ad79d61cfee57b2a6a74f78bfef400f7a09b81b6ccc',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      (
        '<{[JULIA: (0, 0) ± 2 @ (1, 1)] : [1024 × 1024, 6666] : imaginary} -> '  # noqa: RUF001
        '<MP4*2: {[PNG*1: ELECTRIC, none] + [MARK: red/2 @ (-11/17, 9/2)] + '
        '[OVERLAY: GRID]}> / (mag:3/7, n:1000|1999, d:75, fps:(40/3)*2, l:0)>'
      ),
      id='ZoomParameters-2',
    ),
    pytest.param(
      frame_test.COMPUTATION_STR_3,  # re-used from frame_test.py, ties it all together
      pixels_test.ANIM_STR_3,  # re-used from above (render), ties it all together
      '3000/4',
      100,
      800000,
      2,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":800000,"img":{"depth":8888,"frm":{"bottom_im":"-17/19","bottom_re":"1/31",'
        '"fractal":"julia","point_im":"-11/19","point_re":"3/2","top_im":"13/7","top_re":"-11/23"},'
        '"height":2048,"set_points":"max","width":2048},"loop":2,"mag":"750","n_frames":100,'
        '"render":{"anim":"gif","i_frames":2,"render":{"escaped_pal":"grayscale","i_pixels":3,'
        '"mark_color":"yellow","mark_im":"-7/11","mark_re":"71/4","mark_width":3,"overlay":null,'
        '"set_pal":"sunset","tp":"png"}}}'
      ),
      '70129081c883c6776dd560592f47e4ea8c6106f7447485d0276ef52b9eb400ed',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      (
        '<{[JULIA: (-159/713, 64/133) ± (364/713, 366/133) @ (3/2, -11/19)] : '
        '[2048 × 2048, 8888] : max} -> <GIF*3: {[PNG*4: GRAYSCALE, SUNSET] + '  # noqa: RUF001
        '[MARK: yellow/3 @ (71/4, -7/11)]}> / (mag:750, n:100|298, d:20, fps:(5)*3, l:2)>'
      ),
      id='ZoomParameters-3',
    ),
  ],
)
def test_zoom_hash_stability_and_serialization_consistency(
  i_json: str,
  r_json: str,
  mag: str,
  nf: int,
  d: int,
  lo: int,
  json1: str,
  sha: str,
  txt: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  params: zoom.ZoomParameters = zoom.ZoomParameters(
    img=frame.ComputationParameters.FromJson(json.loads(i_json)),
    render=pixels.RenderAnimationParameters.FromJson(json.loads(r_json)),
    mag=gmpy2.mpq(mag),
    n_frames=nf,
    duration=d,
    loop=lo,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert zoom.ZoomParameters.FromJson(params.json, check_hash=sha) == params, 'BIG PROBLEM! BUG!'
  assert i_json in data, 'BIG PROBLEM: breaking input JSON! BUG!'
  assert r_json in data, 'BIG PROBLEM: breaking render JSON! BUG!'
  assert str(params) == txt
