# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: base.py."""

from __future__ import annotations

import pathlib

from tranzoom.cli import base
from tranzoom.core import image

_REPO_ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent.parent
_SEAHORSE_TAIL_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'demo-mandel-seahorse-tail.png'
)
_SUZANA_WAVE_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'demo-julia-suzana-wave.png'
)


def test_seahorse_tail_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromPNG(_SEAHORSE_TAIL_PATH.read_bytes())
  assert w == h == 1024
  assert hsh == base.SEAHORSE_TAIL_HASH


def test_suzana_wave_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromPNG(_SUZANA_WAVE_PATH.read_bytes())
  assert w == 512
  assert h == 377
  assert hsh == base.SUZANA_WAVE_HASH
