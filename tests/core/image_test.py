# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: image.py."""

from __future__ import annotations

import gmpy2
import pytest

from tranzoom.core import image, palette


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
    'json',
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
def test_frame_hash_stability_and_serialization_consistency(
  tp: str,
  e_pal: str,
  s_pal: str,
  m_re: str,
  m_im: str,
  m_col: str | None,
  w: int,
  o: str | None,
  json: str,
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
  assert data == json, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert image.RenderParameters.FromJson(params.json, check_hash=sha) == params, 'BIG PROBLEM! BUG!'
