# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: image.py."""

from __future__ import annotations

import json
import math

import gmpy2
import pytest

from tranzoom.core import frame, image, palette

# this is the max uint64 that can be encoded to non-nan/inf float32
_MAX_ENCODING_UINT64: int = 18446744073701163007


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
      '3947b7a6bdc58fedce9420d70e58755216c7e109dd86a049499ee9389bc7b081',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
    ),
    (
      'gif',
      'electric',
      None,
      '-11/17',
      '9/2',
      'red',
      2,
      'grid',
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"escaped_pal":"electric","mark_color":"red","mark_im":"9/2",'
        '"mark_re":"-11/17","mark_width":2,"overlay":"grid","set_pal":null,"tp":"gif"}'
      ),
      '8a2a39998c509527d02357aaa14433bdead2f755f5e2fd26e702e150e9ded076',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
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
      '2e2439bcdcfb0aaf0b2127880425478a9a1cdc804debe1ec57c0fd5697a44444',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
    ),
  ],
)
def test_render_hash_stability_and_serialization_consistency(
  tp: str,
  e_pal: str,
  s_pal: str | None,
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
    set_pal=palette.Palette(s_pal) if s_pal else None,
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
      '4af30ffb71a5e60d39b92908e2946f0aeb3ad30ae90bc850fbd356d09707c08d',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
    ),
    (
      'mp4',
      (
        '{"depth":6666,"frm":{"bottom_im":"-1","bottom_re":"1","fractal":"julia"'
        ',"point_im":"1","point_re":"1","top_im":"1","top_re":"-1"},"height":1024,'
        '"set_points":"imaginary","width":1024}'
      ),
      (
        '{"escaped_pal":"electric","mark_color":"red","mark_im":"9/2",'
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
        '"n_frames":1000,"render":{"escaped_pal":"electric","mark_color":"red",'
        '"mark_im":"9/2","mark_re":"-11/17","mark_width":2,"overlay":"grid",'
        '"set_pal":"grayscale","tp":"gif"},"tp":"mp4"}'
      ),
      'e9205b7df0cf877a8254fd749571f18dcae29d8e871a9726eb2ed1980ce67d83',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
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
      '014d14e6c61d06cfe0b80271d81d5cff8853fde0faf1359ba1806484f722c9d3',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
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
  encoded: int = image.EncodeIntFloatTo64(i, f)
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
    image.EncodeIntFloatTo64(i, f)


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
