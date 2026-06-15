# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: pixels.py."""

from __future__ import annotations

import json

import gmpy2
import pytest

from tranzoom.core import frame, palette, pixels

# this is the max uint64 that can be encoded to non-nan/inf float32
_MAX_ENCODING_UINT64: int = 18446744073701163007


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
RENDER_STR_1: str = (
  '{"escaped_pal":"sunset","i_pixels":1,"mark_color":null,"mark_im":"0","mark_re":"0",'
  '"mark_width":1,"next_marker":null,"overlay":null,"prev_marker":null,'
  '"set_pal":"rgrayscale","tp":"png"}'
)
RENDER_STR_2: str = (
  '{"escaped_pal":"electric","i_pixels":0,"mark_color":"red","mark_im":"9/2",'
  '"mark_re":"-11/17","mark_width":2,"next_marker":{"bottom_im":"-1","bottom_re":"11/9",'
  '"fractal":"mandelbrot","point_im":"0","point_re":"0","top_im":"1","top_re":"-1/2"},'
  '"overlay":"grid","prev_marker":{"bottom_im":"-1","bottom_re":"1",'
  '"fractal":"mandelbrot","point_im":"0","point_re":"0","top_im":"1","top_re":"-1"},'
  '"set_pal":null,"tp":"gif"}'
)
RENDER_STR_3: str = (
  '{"escaped_pal":"grayscale","i_pixels":3,"mark_color":"yellow","mark_im":"-7/11",'
  '"mark_re":"71/4","mark_width":3,"next_marker":null,"overlay":null,'
  '"prev_marker":null,"set_pal":"sunset","tp":"mp4"}'
)
# DO NOT "JUST FIX" THESE! If they are wrong, it means something will break in the DB!


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'tp',
    'e_pal',
    's_pal',
    'ip',
    'm_re',
    'm_im',
    'm_col',
    'w',
    'o',
    'p_json',
    'n_json',
    'json1',
    'sha',
    'txt',
  ),
  [
    (
      'png',
      'sunset',
      'rgrayscale',
      1,
      '0',
      '0',
      None,
      1,
      None,
      None,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      RENDER_STR_1,  # re-used below (zoom) to make sure it is all tied together
      '8d93c85ee64d1f9d2e379cf12e646493445d2855bae6ddcdb945cfa510982731',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '{[PNG*2: SUNSET, GRAYSCALE_REVERSE]}',
    ),
    (
      'gif',
      'electric',
      None,
      0,
      '-11/17',
      '9/2',
      'red',
      2,
      'grid',
      (
        '{"bottom_im":"-1","bottom_re":"1","fractal":"mandelbrot","point_im":"0","point_re":"0",'
        '"top_im":"1","top_re":"-1"}'
      ),
      (
        '{"bottom_im":"-1","bottom_re":"11/9","fractal":"mandelbrot","point_im":"0","point_re":"0",'
        '"top_im":"1","top_re":"-1/2"}'
      ),
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      RENDER_STR_2,  # re-used below (zoom) to make sure it is all tied together
      '20876ddd181c33300831b61318d096f71eae28944b148961e97e698e3bd26fd1',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      (
        '{[GIF*1: ELECTRIC, none] + [MARK: red/2 @ (-11/17, 9/2)] + '
        '[OVERLAY: GRID] + [P:22c8b5cfc5, N:2f0dcd61dc]}'
      ),
    ),
    (
      'mp4',
      'grayscale',
      'sunset',
      3,
      '71/4',
      '-7/11',
      'yellow',
      3,
      None,
      None,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      RENDER_STR_3,  # re-used below (zoom) to make sure it is all tied together
      'f0c9521daa9d566928f591eb5bc074b9bc0c40bd90e09783e8d50ebedca95f28',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '{[MP4*4: GRAYSCALE, SUNSET] + [MARK: yellow/3 @ (71/4, -7/11)]}',
    ),
  ],
)
def test_render_hash_stability_and_serialization_consistency(
  tp: str,
  e_pal: str,
  s_pal: str | None,
  ip: int,
  m_re: str,
  m_im: str,
  m_col: str | None,
  w: int,
  o: str | None,
  p_json: str | None,
  n_json: str | None,
  json1: str,
  sha: str,
  txt: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  params: pixels.RenderParameters = pixels.RenderParameters(
    tp=pixels.FileType(tp),
    escaped_pal=palette.Palette(e_pal),
    set_pal=palette.Palette(s_pal) if s_pal else None,
    i_pixels=ip,
    mark_re=gmpy2.mpq(m_re),
    mark_im=gmpy2.mpq(m_im),
    mark_color=pixels.Color[m_col.upper()] if m_col is not None else None,
    mark_width=w,
    overlay=pixels.OverlayType(o) if o is not None else None,
    prev_marker=frame.Frame.FromJson(json.loads(p_json)) if p_json else None,
    next_marker=frame.Frame.FromJson(json.loads(n_json)) if n_json else None,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert pixels.RenderParameters.FromJson(params.json, check_hash=sha) == params, (
    'BIG PROBLEM! BUG!'
  )
  assert str(params) == txt
