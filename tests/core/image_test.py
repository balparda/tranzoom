# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: image.py."""

from __future__ import annotations

import json
import math

import gmpy2
import pytest

from tranzoom.core import fractalfast, frame, image, palette

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
  params: image.RenderParameters = image.RenderParameters(
    tp=image.FileType(tp),
    escaped_pal=palette.Palette(e_pal),
    set_pal=palette.Palette(s_pal) if s_pal else None,
    i_pixels=ip,
    mark_re=gmpy2.mpq(m_re),
    mark_im=gmpy2.mpq(m_im),
    mark_color=image.Color[m_col.upper()] if m_col is not None else None,
    mark_width=w,
    overlay=image.OverlayType(o) if o is not None else None,
    prev_marker=frame.Frame.FromJson(json.loads(p_json)) if p_json else None,
    next_marker=frame.Frame.FromJson(json.loads(n_json)) if n_json else None,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert image.RenderParameters.FromJson(params.json, check_hash=sha) == params, 'BIG PROBLEM! BUG!'
  assert str(params) == txt


@pytest.mark.parametrize(
  ('i', 'f', 'n'),
  [
    # zero, and lower limit for n
    (0, 0.0, 0),
    # other zero
    (1, 0.0, 4294967296),
    (-1, 0.0, 18446744069414584320),
    (0, 1.3, 1067869798),
    (0, -1.3, 3215353446),
    # the pos/neg
    (1, 1.3, 5362837094),
    (-1, 1.3, 18446744070482454118),
    (1, -1.3, 7510320742),
    (-1, -1.3, 18446744072629937766),
    # random value
    (1_234_567_890, 9.87654321987654321, 5302428713334212178),
    (-987_654_321, -1.23456789123456789, 14204801068476270162),
    # exact limit (i)
    (frame.BIT_31 - 1, 0.0, 9223372032559808512),
    (-frame.BIT_31, 0.0, 9223372036854775808),
    # exact limit (n)
    (-1, -3.4028234663852886e38, _MAX_ENCODING_UINT64),
  ],
)
def test_encode_decode(
  i: int,
  f: float,
  n: int,
) -> None:
  """Encode/decode checks."""
  # encode
  encoded: int = fractalfast.EncodeIntFloatTo64(i, f)
  assert n == encoded, f'encode mismatch for uint64: {n=} != {encoded=}'
  # decode
  decoded_i: int
  decoded_f: float
  decoded_i, decoded_f = image.Decode64ToIntFloat(encoded)
  assert i == decoded_i, f'encode/decode mismatch for int: {i=} != {decoded_i=}'
  error_f: float = abs(f - decoded_f) / f if f != 0 else abs(decoded_f)
  assert error_f < 1e-7, f'encode/decode mismatch for float32: {f=} != {decoded_f=}; {error_f=}'


@pytest.mark.skip(reason='This test works, but is 30s+ and is not super important...')
@pytest.mark.slow
def test_check_all_n_above_are_nan() -> None:
  """Check that all uint64 from _MAX_ENCODING_UINT64 + 1 to BIT_64 decode to NaN/Inf."""
  n: int = frame.BIT_64
  for n in range(frame.BIT_64 - 1, 0, -1):
    f: float = image.Decode64ToIntFloat(n)[1]
    if not math.isnan(f) and not math.isinf(f):
      break
  assert n == _MAX_ENCODING_UINT64, f'Expected {n=}=={_MAX_ENCODING_UINT64} as largest non-NaN/Inf'


@pytest.mark.parametrize(
  ('i', 'f'),
  [
    # exact limit
    (frame.BIT_31, 0.0),
    (-frame.BIT_31 - 1, 0.0),
    # other
    (2**40, 0.0),  # int out of int32 range
    (-(2**40), 0.0),  # int out of int32 range
    (0, 1e40),  # float out of float32 range
    (0, -1e40),  # float out of float32 range
  ],
)
def test_encode_error(
  i: int,
  f: float,
) -> None:
  """Encode error checks."""
  with pytest.raises(image.Error, match=r'encoding.*uint64.*(?:requires|float too large)'):
    fractalfast.EncodeIntFloatTo64(i, f)


@pytest.mark.parametrize(
  'n',
  [
    # exact limit
    -1,
    frame.BIT_64,
    # other
    2**65,  # uint64 out of range
    -(2**65),  # uint64 out of range
  ],
)
def test_decode_error(
  n: int,
) -> None:
  """Decode error checks."""
  with pytest.raises(image.Error, match=r'decoding uint64.*requires'):
    image.Decode64ToIntFloat(n)
