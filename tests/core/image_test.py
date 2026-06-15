# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: image.py."""

from __future__ import annotations

import math

import pytest

from tranzoom.core import fractalfast, frame, image

# this is the max uint64 that can be encoded to non-nan/inf float32
_MAX_ENCODING_UINT64: int = 18446744073701163007


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
