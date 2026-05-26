#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Quick benchmark script.

Usage
poetry run scripts/benchmark.py
"""

from __future__ import annotations

import math

from transcrypto.utils import human, timer

from tranzoom.core import image

M = 10
N = 1024 * 1024


def Main() -> int:
  """Call into the CLI module; thin wrapper for app.

  Returns:
    int: Exit code

  """
  f: float
  f2: float
  i: int
  i2: int
  n: int
  sqrt_results: list[float] = []
  encode_results: list[float] = []
  decode_results: list[float] = []
  combined_results: list[float] = []
  print(f'Running benchmark with M={M} and N={N}...')
  for m in range(1, M + 1):
    print(f'Run {m}/{M}...')
    # just the math.sqrt() part for a baseline
    with timer.Timer() as sqrt_tmr:
      for i in range(N):
        f = math.sqrt(i * m)
    sqrt_results.append(sqrt_tmr.elapsed)
    # only encode()
    with timer.Timer() as encode_tmr:
      for i in range(N):
        n = image.EncodeIntFloatTo64(i * m, i * m)  # 10M = 2.2s
    encode_results.append(encode_tmr.elapsed)
    # only decode()
    with timer.Timer() as decode_tmr:
      for i in range(N):
        i2, f2 = image.Decode64ToIntFloat(i * m)
    decode_results.append(decode_tmr.elapsed)
    # combined
    with timer.Timer() as combined_tmr:
      for i in range(N):
        f = math.sqrt(i * m)  # 10M = 380ms
        n = image.EncodeIntFloatTo64(i * m, f * m)  # 10M = 2.2s
        i2, f2 = image.Decode64ToIntFloat(n)  # 10M = 2.7s
        if i:
          assert i * m == i2 and abs(((f * m) - f2) / (f * m)) < 1e-7, (
            f'mismatch: i={i}, f={f}, i2={i2}, f2={f2}'
          )
    combined_results.append(combined_tmr.elapsed)
  # show results
  print(f'math.sqrt(): {human.HumanizedSeconds(sum(sqrt_results) / M)} per {N}')
  print(f'image.encode(): {human.HumanizedSeconds(sum(encode_results) / M)} per {N}')
  print(f'image.decode(): {human.HumanizedSeconds(sum(decode_results) / M)} per {N}')
  print(f'sqrt()+encode()+decode(): {human.HumanizedSeconds(sum(combined_results) / M)} per {N}')
  # end
  return 0


if __name__ == '__main__':
  raise SystemExit(Main())
