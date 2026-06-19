# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: pixels.py."""

from __future__ import annotations

import json

import gmpy2
import numpy as np
import pytest

from tranzoom.core import palette, pixels

# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
_RENDER_STR_1: str = (
  '{"escaped_pal":"sunset","i_pixels":1,"mark_color":null,"mark_im":"0","mark_re":"0",'
  '"mark_width":1,"overlay":null,"resample":3,"set_pal":"rgrayscale","tp":"png"}'
)
_RENDER_STR_2: str = (
  '{"escaped_pal":"electric","i_pixels":0,"mark_color":"red","mark_im":"9/2",'
  '"mark_re":"-11/17","mark_width":2,"overlay":"grid","resample":1,"set_pal":null,"tp":"png"}'
)
_RENDER_STR_3: str = (
  '{"escaped_pal":"grayscale","i_pixels":3,"mark_color":"yellow","mark_im":"-7/11",'
  '"mark_re":"71/4","mark_width":3,"overlay":null,"resample":100,"set_pal":"sunset","tp":"png"}'
)
ANIM_STR_1: str = (
  '{"anim":"gif","i_frames":0,"render":{"escaped_pal":"sunset","i_pixels":1,"mark_color":null,'
  '"mark_im":"0","mark_re":"0","mark_width":1,"overlay":null,'
  '"resample":3,"set_pal":"rgrayscale","tp":"png"}}'
)
ANIM_STR_2: str = (
  '{"anim":"mp4","i_frames":1,"render":{"escaped_pal":"electric","i_pixels":0,"mark_color":"red",'
  '"mark_im":"9/2","mark_re":"-11/17","mark_width":2,"overlay":"grid",'
  '"resample":1,"set_pal":null,"tp":"png"}}'
)
ANIM_STR_3: str = (
  '{"anim":"gif","i_frames":2,"render":{"escaped_pal":"grayscale","i_pixels":3,'
  '"mark_color":"yellow","mark_im":"-7/11","mark_re":"71/4","mark_width":3,"overlay":null,'
  '"resample":100,"set_pal":"sunset","tp":"png"}}'
)
# DO NOT "JUST FIX" THESE! If they are wrong, it means something will break in the DB!


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'tp',
    'e_pal',
    's_pal',
    'ip',
    'res',
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
      pixels.Resampling.BICUBIC,
      '0',
      '0',
      None,
      1,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      _RENDER_STR_1,  # re-used below (zoom) to make sure it is all tied together
      '56deab438b4453b358140917b24d12b9e3aeaec8c2d92381c1f2459e6196d207',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '{[PNG*2/Bicubic: SUNSET, GRAYSCALE_REVERSE]}',
      id='RenderParameters-1',
    ),
    pytest.param(
      'png',
      'electric',
      None,
      0,
      pixels.Resampling.LANCZOS,
      '-11/17',
      '9/2',
      'red',
      2,
      'grid',
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      _RENDER_STR_2,  # re-used below (zoom) to make sure it is all tied together
      'd751524a3d651b73433d697157aabe811d507520be83ee7c588194ccca0febfa',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '{[PNG*1: ELECTRIC, none] + [MARK: red/2 @ (-11/17, 9/2)] + [OVERLAY: GRID]}',
      id='RenderParameters-2',
    ),
    pytest.param(
      'png',
      'grayscale',
      'sunset',
      3,
      pixels.Resampling.BILINEAR,
      '71/4',
      '-7/11',
      'yellow',
      3,
      None,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      _RENDER_STR_3,  # re-used below (zoom) to make sure it is all tied together
      '480fe1f8d9b32faa5d287ea1fdb7c5bf7cf9c6299da1a3655af9642cf9cf2dbb',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '{[PNG*4/Bilinear: GRAYSCALE, SUNSET] + [MARK: yellow/3 @ (71/4, -7/11)]}',
      id='RenderParameters-3',
    ),
  ],
)
def test_render_png_hash_stability_and_serialization_consistency(
  tp: str,
  e_pal: str,
  s_pal: str | None,
  ip: int,
  res: pixels.Resampling,
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
    resample=res,
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
      '971d28ec5018bb2f577105f04a9be59dbc82ba1112bd37fdc4a718d04d33b5f6',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '<GIF*1: {[PNG*2/Bicubic: SUNSET, GRAYSCALE_REVERSE]}>',
      id='RenderAnimationParameters-1',
    ),
    pytest.param(
      _RENDER_STR_2,
      'mp4',
      1,
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      ANIM_STR_2,  # re-used below (zoom) to make sure it is all tied together
      '8cdae0435ea5195c8ea785ccd6f359df3807dde5cf408a629f1b4c2c26a8be00',  # DO NOT "JUST FIX"
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
      '77f58d02da3c21bd92f886949121a29abef558f356bb08d91f23a45cce88e2a3',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '<GIF*3: {[PNG*4/Bilinear: GRAYSCALE, SUNSET] + [MARK: yellow/3 @ (71/4, -7/11)]}>',
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


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'img',
    'anim',
    'width',
    'height',
    'bin_hash',
    'data_hash',
    'meta',
    'json1',
    'sha',
    'txt',
  ),
  [
    pytest.param(
      'png',
      None,
      512,
      512,
      'a' * 64,
      'b' * 64,
      {'key1': 'value1'},
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"anim":null,"bin_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        'aaa","data_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",'
        '"height":512,"img":"png","meta":{"key1":"value1"},"width":512}'
      ),
      '1efdcf2c7cb8386e30ef30cfe1de26e1a37daddebd3ceb4074b25cf11b9e0c3d',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '[PNG.img: 512 × 512, '  # noqa: RUF001
      "BIN:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', "
      "DATA:'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', "
      "{'key1': 'value1'}]",
      id='ObjInfo-1',
    ),
    pytest.param(
      None,
      'gif',
      1024,
      768,
      '1' * 64,
      '2' * 64,
      {'key2': 'value2', 'key3': 'value3'},
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"anim":"gif","bin_hash":"1111111111111111111111111111111111111111111111111111111111111'
        '111","data_hash":"2222222222222222222222222222222222222222222222222222222222222222",'
        '"height":768,"img":null,"meta":{"key2":"value2","key3":"value3"},"width":1024}'
      ),
      '7f04ba3e080d0b2fcf1f958d9051579e2d5329c48228ec83a8817e152ef91b47',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '[GIF.anim: 1024 × 768, '  # noqa: RUF001
      "BIN:'1111111111111111111111111111111111111111111111111111111111111111', "
      "DATA:'2222222222222222222222222222222222222222222222222222222222222222', "
      "{'key2': 'value2', 'key3': 'value3'}]",
      id='ObjInfo-2',
    ),
    pytest.param(
      'jpg',
      None,
      256,
      256,
      'c' * 64,
      'd' * 64,
      {},
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      (
        '{"anim":null,"bin_hash":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",'
        '"data_hash":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","height"'
        ':256,"img":"jpg","meta":{},"width":256}'
      ),
      '47f1a2bf3386e2c526a3486f8b2d96fc03c3d24f6d8e06bc7ebd52872ac47d27',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      '[JPG.img: 256 × 256, '  # noqa: RUF001
      "BIN:'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc', "
      "DATA:'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd', {}]",
      id='ObjInfo-3',
    ),
  ],
)
def test_obj_info_hash_stability_and_serialization_consistency(
  img: str | None,
  anim: str | None,
  width: int,
  height: int,
  bin_hash: str,
  data_hash: str,
  meta: dict[str, str],
  json1: str,
  sha: str,
  txt: str,
) -> None:
  """Important JSON and hash consistency/stability checks."""
  params: pixels.ObjInfo = pixels.ObjInfo(
    img=pixels.ImageEncoding(img) if img else None,
    anim=pixels.AnimationEncoding(anim) if anim else None,
    width=width,
    height=height,
    bin_hash=bin_hash,
    data_hash=data_hash,
    meta=meta,
  )
  data: str = params.binary.decode('utf-8')
  assert data == json1, 'BIG PROBLEM: breaking JSON! BUG!'
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert pixels.ObjInfo.FromJson(params.json, check_hash=sha) == params, 'BIG PROBLEM! BUG!'
  assert str(params) == txt


# ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
@pytest.mark.parametrize(
  (
    'width',
    'height',
    'data_generator',
    'meta',
    'sha',
    'data_hash',
    'txt',
  ),
  [
    pytest.param(
      24,
      24,
      'pattern1',
      {'test': 'pixels1'},
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      'bf15c3139ca906aec2c41dfca91ee5dbb56b7db1ead533c9026e2f5f02bf7694',  # DO NOT "JUST FIX"
      '9590eb30c3f2c7a68e1182fafecf6f44ad8ccc535806f6383e9e90b50837ec7f',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      "[24, 24, '9590eb30c3f2c7a68e1182fafecf6f44ad8ccc535806f6383e9e90b50837ec7f', "
      "{'test': 'pixels1'}]",
      id='Pixels-1',
    ),
    pytest.param(
      24,
      32,
      'grayscale',
      {'test': 'pixels2', 'mode': 'grayscale'},
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      'de537a242c57d1ad32a9a8cfdbcb5eb77eaf35c5fbce24cbad97e40b94032957',  # DO NOT "JUST FIX"
      '887d1668e897bc5803503a00ef38f290cf9692cd48e14573951ae64ec0f008b7',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      "[24, 32, '887d1668e897bc5803503a00ef38f290cf9692cd48e14573951ae64ec0f008b7', "
      "{'test': 'pixels2', 'mode': 'grayscale'}]",
      id='Pixels-2',
    ),
    pytest.param(
      32,
      24,
      'uniform',
      {},
      # ATTENTION: if these change/break, ever, BIG PROBLEM!! b/c hashes will break in DB!!
      'ee29035f60b8c9ccfac1bdfda262a5eff26fa70f6f4155cebe140a86704486a7',  # DO NOT "JUST FIX"
      'dea313a03db46a224a28a8a79febff397b832f3256b9c9ce236e79ee90e6ed7f',  # DO NOT "JUST FIX"
      # DO NOT "JUST FIX" THIS HASH! If the hash is wrong, it means something will break in the DB!
      "[32, 24, 'dea313a03db46a224a28a8a79febff397b832f3256b9c9ce236e79ee90e6ed7f', {}]",
      id='Pixels-3',
    ),
  ],
)
def test_pixels_hash_stability_and_serialization_consistency(
  width: int,
  height: int,
  data_generator: str,
  meta: dict[str, str],
  sha: str,
  data_hash: str,
  txt: str,
) -> None:
  """Test."""
  # generate pixel data based on the generator type
  data: np.ndarray
  if data_generator == 'pattern1':
    data = np.zeros((height, width, 3), dtype=np.float32)
    for i in range(height):
      for j in range(width):
        data[i, j] = [float(i * 10 % 256), float(j * 10 % 256), float((i + j) * 5 % 256)]
  elif data_generator == 'grayscale':
    data = np.zeros((height, width, 3), dtype=np.float32)
    for i in range(height):
      for j in range(width):
        val: float = float((i * width + j) * 255 // (height * width))
        data[i, j] = [val, val, val]
  elif data_generator == 'uniform':
    data = np.ones((height, width, 3), dtype=np.float32) * 128.0
  else:
    pytest.fail(f'Unknown data generator: {data_generator}')
  # create Pixels object
  params: pixels.Pixels = pixels.Pixels(data=data, meta=meta)
  # check hash stability
  assert params.sha == sha, 'BIG PROBLEM: breaking hash! BUG!'
  assert params.data_hash == data_hash, 'BIG PROBLEM: breaking data hash! BUG!'
  assert params.width == width
  assert params.height == height
  # check round-trip serialization
  reconstructed: pixels.Pixels = pixels.Pixels.FromJson(params.json, check_hash=sha)
  assert reconstructed.sha == params.sha, 'BIG PROBLEM: FromJson hash mismatch! BUG!'
  assert reconstructed.data_hash == params.data_hash, 'BIG PROBLEM: FromJson data mismatch! BUG!'
  assert reconstructed.width == params.width, 'BIG PROBLEM: FromJson width mismatch! BUG!'
  assert reconstructed.height == params.height, 'BIG PROBLEM: FromJson height mismatch! BUG!'
  assert reconstructed.meta == params.meta, 'BIG PROBLEM: FromJson meta mismatch! BUG!'
  assert np.array_equal(reconstructed.data, params.data), 'BIG PROBLEM: FromJson pixel error! BUG!'
  assert str(params) == txt
