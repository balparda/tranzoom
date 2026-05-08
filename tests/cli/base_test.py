# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: base.py."""

from __future__ import annotations

import pathlib

from tranzoom.cli import base
from tranzoom.core import fractal

_REPO_ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent.parent
_SEAHORSE_TAIL_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'demo-mandel-seahorse-tail.png'
)


def test_seahorse_tail_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = fractal.GetBasicDataFromPNG(_SEAHORSE_TAIL_PATH.read_bytes())
  assert w == h == 512
  assert hsh == base.SEAHORSE_TAIL_HASH
