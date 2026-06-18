# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: pixels.py."""

from __future__ import annotations

import json

import gmpy2
import pytest

from tranzoom.core import palette, pixels

# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
_RENDER_STR_1: str = (
  '{"escaped_pal":"sunset","i_pixels":1,"mark_color":null,"mark_im":"0","mark_re":"0",'
  '"mark_width":1,"overlay":null,"set_pal":"rgrayscale","tp":"png"}'
)
_RENDER_STR_2: str = (
  '{"escaped_pal":"electric","i_pixels":0,"mark_color":"red","mark_im":"9/2",'
  '"mark_re":"-11/17","mark_width":2,"overlay":"grid","set_pal":null,"tp":"png"}'
)
_RENDER_STR_3: str = (
  '{"escaped_pal":"grayscale","i_pixels":3,"mark_color":"yellow","mark_im":"-7/11",'
  '"mark_re":"71/4","mark_width":3,"overlay":null,"set_pal":"sunset","tp":"png"}'
)
ANIM_STR_1: str = (
  '{"anim":"gif","i_frames":0,"render":{"escaped_pal":"sunset","i_pixels":1,"mark_color":null,'
  '"mark_im":"0","mark_re":"0","mark_width":1,"overlay":null,"set_pal":"rgrayscale","tp":"png"}}'
)
ANIM_STR_2: str = (
  '{"anim":"mp4","i_frames":1,"render":{"escaped_pal":"electric","i_pixels":0,"mark_color":"red",'
  '"mark_im":"9/2","mark_re":"-11/17","mark_width":2,"overlay":"grid","set_pal":null,"tp":"png"}}'
)
ANIM_STR_3: str = (
  '{"anim":"gif","i_frames":2,"render":{"escaped_pal":"grayscale","i_pixels":3,'
  '"mark_color":"yellow","mark_im":"-7/11","mark_re":"71/4","mark_width":3,"overlay":null,'
  '"set_pal":"sunset","tp":"png"}}'
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
    'json1',
    'sha',
    'txt',
  ),
  [
    pytest.param(
      'png',
      'sunset',
      'rgrayscale',
      1,
      '0',
      '0',
      None,
      1,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      _RENDER_STR_1,  # re-used below (zoom) to make sure it is all tied together
      '2103c7db59d6e6a8d29b0ee4ab190095c16596eac74293253781d3ce3c48cd2b',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '{[PNG*2: SUNSET, GRAYSCALE_REVERSE]}',
      id='RenderParameters-1',
    ),
    pytest.param(
      'png',
      'electric',
      None,
      0,
      '-11/17',
      '9/2',
      'red',
      2,
      'grid',
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      _RENDER_STR_2,  # re-used below (zoom) to make sure it is all tied together
      '439d95f21fd945fee8c7f06c2b3d0d1abf9e45ace4e227093a5d95cfc4860324',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '{[PNG*1: ELECTRIC, none] + [MARK: red/2 @ (-11/17, 9/2)] + [OVERLAY: GRID]}',
      id='RenderParameters-2',
    ),
    pytest.param(
      'png',
      'grayscale',
      'sunset',
      3,
      '71/4',
      '-7/11',
      'yellow',
      3,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      _RENDER_STR_3,  # re-used below (zoom) to make sure it is all tied together
      '110d8105db06ef5c7bcfc4345a183b33a3d4fb4d7ce4170db2c881ee2967d00b',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '{[PNG*4: GRAYSCALE, SUNSET] + [MARK: yellow/3 @ (71/4, -7/11)]}',
      id='RenderParameters-3',
    ),
  ],
)
def test_render_png_hash_stability_and_serialization_consistency(
  tp: str,
  e_pal: str,
  s_pal: str | None,
  ip: int,
  m_re: str,
  m_im: str,
  m_col: str | None,
  w: int,
  o: str | None,
  json1: str,
  sha: str,
  txt: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  params: pixels.RenderParameters = pixels.RenderParameters(
    tp=pixels.ImageEncoding(tp),
    escaped_pal=palette.Palette(e_pal),
    set_pal=palette.Palette(s_pal) if s_pal else None,
    i_pixels=ip,
    mark_re=gmpy2.mpq(m_re),
    mark_im=gmpy2.mpq(m_im),
    mark_color=pixels.Color[m_col.upper()] if m_col is not None else None,
    mark_width=w,
    overlay=pixels.OverlayType(o) if o is not None else None,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert pixels.RenderParameters.FromJson(params.json, check_hash=sha) == params, (
    'BIG PROBLEM! BUG!'
  )
  assert str(params) == txt


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'father',
    'tp',
    'i_f',
    'json1',
    'sha',
    'txt',
  ),
  [
    pytest.param(
      _RENDER_STR_1,
      'gif',
      0,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      ANIM_STR_1,  # re-used below (zoom) to make sure it is all tied together
      '58eedf88f7892580d0319cd3b4715d71c773e00a56dc06f34a45bf0c855333df',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '<GIF*1: {[PNG*2: SUNSET, GRAYSCALE_REVERSE]}>',
      id='RenderAnimationParameters-1',
    ),
    pytest.param(
      _RENDER_STR_2,
      'mp4',
      1,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      ANIM_STR_2,  # re-used below (zoom) to make sure it is all tied together
      '821be148451935d2adfb016d14033077dd4283ba0d12de9812e89dfdf71653a1',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '<MP4*2: {[PNG*1: ELECTRIC, none] + [MARK: red/2 @ (-11/17, 9/2)] + [OVERLAY: GRID]}>',
      id='RenderAnimationParameters-2',
    ),
    pytest.param(
      _RENDER_STR_3,
      'gif',
      2,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      ANIM_STR_3,  # re-used below (zoom) to make sure it is all tied together
      '9a999088fd67c6308133ae86766c474dcc7b4da27cc0482705ee3e9713b0f284',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '<GIF*3: {[PNG*4: GRAYSCALE, SUNSET] + [MARK: yellow/3 @ (71/4, -7/11)]}>',
      id='RenderAnimationParameters-3',
    ),
  ],
)
def test_render_anim_hash_stability_and_serialization_consistency(
  father: str,
  tp: str,
  i_f: int,
  json1: str,
  sha: str,
  txt: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  params: pixels.RenderAnimationParameters = pixels.RenderAnimationParameters.FromRender(
    pixels.RenderParameters.FromJson(json.loads(father)),
    anim=pixels.AnimationEncoding(tp),
    i_frames=i_f,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert pixels.RenderAnimationParameters.FromJson(params.json, check_hash=sha) == params, (
    'BIG PROBLEM! BUG!'
  )
  assert str(params) == txt
