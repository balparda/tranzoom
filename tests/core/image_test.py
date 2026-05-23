# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: image.py."""

from __future__ import annotations

import json

import gmpy2
import pytest

from tranzoom.core import frame, image, palette


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'tp',
    'e_pal',
    's_pal',
    'm_re',
    'm_im',
    'm_col',
    'w',
    'o',
    'json1',
    'sha',
  ),
  [
    (
      'png',
      'sunset',
      'rgrayscale',
      '0',
      '0',
      None,
      1,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"escaped_pal":"sunset","mark_color":null,"mark_im":"0","mark_re":"0",'
        '"mark_width":1,"overlay":null,"set_pal":"rgrayscale","tp":"png"}'
      ),
      '3947b7a6bdc58fedce9420d70e58755216c7e109dd86a049499ee9389bc7b081',
    ),
    (
      'gif',
      'electric-ocean',
      'grayscale',
      '-11/17',
      '9/2',
      'red',
      2,
      'grid',
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"escaped_pal":"electric-ocean","mark_color":"red","mark_im":"9/2",'
        '"mark_re":"-11/17","mark_width":2,"overlay":"grid","set_pal":"grayscale","tp":"gif"}'
      ),
      'e382dbcc8c3db3a64140a8c1b30e3c90bcbfc4000e188910b5d780fccb54bfe0',
    ),
    (
      'mp4',
      'grayscale',
      'sunset',
      '71/4',
      '-7/11',
      'yellow',
      3,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"escaped_pal":"grayscale","mark_color":"yellow","mark_im":"-7/11",'
        '"mark_re":"71/4","mark_width":3,"overlay":null,"set_pal":"sunset","tp":"mp4"}'
      ),
      '2e2439bcdcfb0aaf0b2127880425478a9a1cdc804debe1ec57c0fd5697a44444',
    ),
  ],
)
def test_render_hash_stability_and_serialization_consistency(
  tp: str,
  e_pal: str,
  s_pal: str,
  m_re: str,
  m_im: str,
  m_col: str | None,
  w: int,
  o: str | None,
  json1: str,
  sha: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  params: image.RenderParameters = image.RenderParameters(
    tp=image.FileType(tp),
    escaped_pal=palette.Palette(e_pal),
    set_pal=palette.Palette(s_pal),
    mark_re=gmpy2.mpq(m_re),
    mark_im=gmpy2.mpq(m_im),
    mark_color=image.Color[m_col.upper()] if m_col is not None else None,
    mark_width=w,
    overlay=image.OverlayType(o) if o is not None else None,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert image.RenderParameters.FromJson(params.json, check_hash=sha) == params, 'BIG PROBLEM! BUG!'


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'tp',
    'i_json',
    'r_json',
    'mag',
    'nf',
    'd',
    'lo',
    'json1',
    'sha',
  ),
  [
    (
      'gif',
      (
        '{"depth":9999,"frm":{"bottom_im":"-1","bottom_re":"1","fractal":"mandelbrot",'
        '"point_im":"0","point_re":"0","top_im":"1","top_re":"-1"},"height":512,'
        '"set_points":null,"width":512}'
      ),
      (
        '{"escaped_pal":"sunset","mark_color":null,"mark_im":"0","mark_re":"0",'
        '"mark_width":1,"overlay":null,"set_pal":"rgrayscale","tp":"png"}'
      ),
      '40/3',
      100,
      80000,
      0,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":80000,"img":{"depth":9999,"frm":{"bottom_im":"-1","bottom_re":"1",'
        '"fractal":"mandelbrot","point_im":"0","point_re":"0","top_im":"1","top_re":"-1"},'
        '"height":512,"set_points":null,"width":512},"loop":0,"mag":"40/3","n_frames":100,'
        '"render":{"escaped_pal":"sunset","mark_color":null,"mark_im":"0","mark_re":"0",'
        '"mark_width":1,"overlay":null,"set_pal":"rgrayscale","tp":"png"},"tp":"gif"}'
      ),
      '4af30ffb71a5e60d39b92908e2946f0aeb3ad30ae90bc850fbd356d09707c08d',
    ),
    (
      'mp4',
      (
        '{"depth":6666,"frm":{"bottom_im":"-1","bottom_re":"1","fractal":"julia"'
        ',"point_im":"1","point_re":"1","top_im":"1","top_re":"-1"},"height":1024,'
        '"set_points":"imaginary","width":1024}'
      ),
      (
        '{"escaped_pal":"electric-ocean","mark_color":"red","mark_im":"9/2",'
        '"mark_re":"-11/17","mark_width":2,"overlay":"grid","set_pal":"grayscale","tp":"gif"}'
      ),
      '3/7',
      1000,
      300000,
      0,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":300000,"img":{"depth":6666,"frm":{"bottom_im":"-1","bottom_re":"1",'
        '"fractal":"julia","point_im":"1","point_re":"1","top_im":"1","top_re":"-1"},'
        '"height":1024,"set_points":"imaginary","width":1024},"loop":0,"mag":"3/7",'
        '"n_frames":1000,"render":{"escaped_pal":"electric-ocean","mark_color":"red",'
        '"mark_im":"9/2","mark_re":"-11/17","mark_width":2,"overlay":"grid",'
        '"set_pal":"grayscale","tp":"gif"},"tp":"mp4"}'
      ),
      '86997a2c51538373e1f7872193518b02f929c51bbd46e24779e5221241fd01b8',
    ),
    (
      'gif',
      (
        '{"depth":8888,"frm":{"bottom_im":"-17/19","bottom_re":"1/31","fractal":"julia",'
        '"point_im":"-11/19","point_re":"3/2","top_im":"13/7","top_re":"-11/23"},'
        '"height":2048,"set_points":"max","width":2048}'
      ),
      (
        '{"escaped_pal":"grayscale","mark_color":"yellow","mark_im":"-7/11",'
        '"mark_re":"71/4","mark_width":3,"overlay":null,"set_pal":"sunset","tp":"mp4"}'
      ),
      '3000/4',
      10000,
      800000,
      2,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"duration":800000,"img":{"depth":8888,"frm":{"bottom_im":"-17/19","bottom_re":"1/31",'
        '"fractal":"julia","point_im":"-11/19","point_re":"3/2","top_im":"13/7","top_re":"-11/23"},'
        '"height":2048,"set_points":"max","width":2048},"loop":2,"mag":"750","n_frames":10000,'
        '"render":{"escaped_pal":"grayscale","mark_color":"yellow","mark_im":"-7/11",'
        '"mark_re":"71/4","mark_width":3,"overlay":null,"set_pal":"sunset","tp":"mp4"},"tp":"gif"}'
      ),
      '014d14e6c61d06cfe0b80271d81d5cff8853fde0faf1359ba1806484f722c9d3',
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
  lo: int,
  json1: str,
  sha: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  params: image.ZoomParameters = image.ZoomParameters(
    tp=image.AnimationType(tp),
    img=frame.ComputationParameters.FromJson(json.loads(i_json)),
    render=image.RenderParameters.FromJson(json.loads(r_json)),
    mag=gmpy2.mpq(mag),
    n_frames=nf,
    duration=d,
    loop=lo,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert image.ZoomParameters.FromJson(params.json, check_hash=sha) == params, 'BIG PROBLEM! BUG!'
  assert i_json in data, 'BIG PROBLEM: breaking input JSON! BUG!'
  assert r_json in data, 'BIG PROBLEM: breaking render JSON! BUG!'
