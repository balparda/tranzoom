# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: zoom.py."""

from __future__ import annotations

import json

import gmpy2
import pytest

from tests.core import frame_test, image_test
from tranzoom.core import frame, image, zoom


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'tp',
    'i_json',
    'r_json',
    'mag',
    'nf',
    'd',
    'it',
    'lo',
    'json1',
    'sha',
    'txt',
  ),
  [
    (
      'gif',
      frame_test.COMPUTATION_STR_1,  # re-used from frame_test.py, ties it all together
      image_test.RENDER_STR_1,  # re-used from above (render), ties it all together
      '40/3',
      17,
      80000,
      0,
      0,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":80000,"i_frames":0,"img":{"depth":9999,"frm":{"bottom_im":"-1",'
        '"bottom_re":"1","fractal":"mandelbrot","point_im":"0","point_re":"0","top_im":"1",'
        '"top_re":"-1"},"height":512,"set_points":null,"width":512},"loop":0,"mag":"40/3",'
        '"n_frames":17,"render":{"escaped_pal":"sunset","i_pixels":1,"mark_color":null,"mark_im":"0",'
        '"mark_re":"0","mark_width":1,"next_marker":null,"overlay":null,"prev_marker":null,'
        '"set_pal":"rgrayscale","tp":"png"},"tp":"gif"}'
      ),
      'a1873e82bf22db0e3a9664864409c60003222483291ca0c5094f57cb48c56803',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      (
        '<GIF: {[MANDELBROT: (0, 0) ± 2] : [512, 512, 9999]} -> '
        '{[PNG*2: SUNSET, GRAYSCALE_REVERSE]} / (mag:40/3, n:17|17, d:2, fps:(17/2)*1, l:0)>'
      ),
    ),
    (
      'mp4',
      frame_test.COMPUTATION_STR_2,  # re-used from frame_test.py, ties it all together
      image_test.RENDER_STR_2,  # re-used from above (render), ties it all together
      '3/7',
      1000,
      3000000,
      1,
      0,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":3000000,"i_frames":1,"img":{"depth":6666,"frm":{"bottom_im":"-1",'
        '"bottom_re":"1","fractal":"julia","point_im":"1","point_re":"1","top_im":"1",'
        '"top_re":"-1"},"height":1024,"set_points":"imaginary","width":1024},"loop":0,"mag":"3/7",'
        '"n_frames":1000,"render":{"escaped_pal":"electric","i_pixels":0,"mark_color":"red","mark_im":"9/2",'
        '"mark_re":"-11/17","mark_width":2,"next_marker":{"bottom_im":"-1","bottom_re":"11/9",'
        '"fractal":"mandelbrot","point_im":"0","point_re":"0","top_im":"1","top_re":"-1/2"},'
        '"overlay":"grid","prev_marker":{"bottom_im":"-1","bottom_re":"1","fractal":"mandelbrot",'
        '"point_im":"0","point_re":"0","top_im":"1","top_re":"-1"},"set_pal":null,"tp":"gif"},'
        '"tp":"mp4"}'
      ),
      '67cd9ad734ecd0cef9fff2cff9f5fccb0479eb1f26c0656e09f4c601f57c5895',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      (
        '<MP4: {[JULIA: (0, 0) ± 2 @ (1, 1)] : [1024, 1024, 6666] : imaginary} -> '
        '{[GIF*1: ELECTRIC, none] + [MARK: red/2 @ (-11/17, 9/2)] + [OVERLAY: GRID] + '
        '[P:22c8b5cfc5, N:2f0dcd61dc]} / (mag:3/7, n:1000|1999, d:75, fps:(40/3)*2, l:0)>'
      ),
    ),
    (
      'gif',
      frame_test.COMPUTATION_STR_3,  # re-used from frame_test.py, ties it all together
      image_test.RENDER_STR_3,  # re-used from above (render), ties it all together
      '3000/4',
      100,
      800000,
      3,
      2,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":800000,"i_frames":3,"img":{"depth":8888,"frm":{"bottom_im":"-17/19",'
        '"bottom_re":"1/31","fractal":"julia","point_im":"-11/19","point_re":"3/2","top_im":"13/7",'
        '"top_re":"-11/23"},"height":2048,"set_points":"max","width":2048},"loop":2,"mag":"750",'
        '"n_frames":100,"render":{"escaped_pal":"grayscale","i_pixels":3,"mark_color":"yellow",'
        '"mark_im":"-7/11","mark_re":"71/4","mark_width":3,"next_marker":null,"overlay":null,'
        '"prev_marker":null,"set_pal":"sunset","tp":"mp4"},"tp":"gif"}'
      ),
      'adf8e9920164bb97b61b5e6623d8afbc81be95333ab457d61801a4e8668afcce',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      (
        '<GIF: {[JULIA: (-159/713, 64/133) ± (364/713, 366/133) @ (3/2, -11/19)] : '
        '[2048, 2048, 8888] : max} -> {[MP4*4: GRAYSCALE, SUNSET] + '
        '[MARK: yellow/3 @ (71/4, -7/11)]} / (mag:750, n:100|397, d:20, fps:(5)*4, l:2)>'
      ),
    ),
  ],
)
def test_zoom_hash_stability_and_serialization_consistency(
  tp: str,
  i_json: str,
  r_json: str,
  mag: str,
  nf: int,
  d: int,
  it: int,
  lo: int,
  json1: str,
  sha: str,
  txt: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  params: zoom.ZoomParameters = zoom.ZoomParameters(
    tp=zoom.AnimationType(tp),
    img=frame.ComputationParameters.FromJson(json.loads(i_json)),
    render=image.RenderParameters.FromJson(json.loads(r_json)),
    mag=gmpy2.mpq(mag),
    n_frames=nf,
    duration=d,
    i_frames=it,
    loop=lo,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert zoom.ZoomParameters.FromJson(params.json, check_hash=sha) == params, 'BIG PROBLEM! BUG!'
  assert i_json in data, 'BIG PROBLEM: breaking input JSON! BUG!'
  assert r_json in data, 'BIG PROBLEM: breaking render JSON! BUG!'
  assert str(params) == txt
