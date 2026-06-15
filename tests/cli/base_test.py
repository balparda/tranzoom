# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: base.py."""

from __future__ import annotations

import pathlib

import pytest

from tranzoom.cli import base
from tranzoom.core import pixels

_REPO_ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent.parent
_IMAGES_DIR: pathlib.Path = _REPO_ROOT / 'tests' / 'data' / 'images'


@pytest.mark.parametrize(
  # SUPER CRITICAL test to make sure computation is stable: THINK before you change!
  ('img', 'w', 'h', 'hsh'),
  [
    # PNG - really only change if core computation changes, so these are more important to be stable
    # don't change anything here: change base.py if the computation changed
    ('demo-mandel-seahorse-tail.png', 1024, 1024, base.SEAHORSE_TAIL_HASH),
    ('demo-julia-suzana-wave.png', 1024, 754, base.SUZANA_WAVE_HASH),
    # GIF - these may change for core computation, or if the animation frame machinery changes
    # don't change anything here: change base.py if the computation changed
    ('demo-mandel-seahorse-tail-anim.gif', 220, 220, base.SEAHORSE_ANIMATED_HASH),
    ('test-mandel-z-auto-seahorse.gif', 159, 117, base.T_GIF_SEAHORSE_HASH),
    ('test-mandel-z-auto-seeds300.gif', 124, 104, base.T_GIF_SEEDS_300_HASH),
    ('test-julia-z-auto-suzana.gif', 88, 118, base.T_GIF_JULIA_SUZANA_HASH),
    ('test-julia-z-auto-dragon.gif', 104, 134, base.T_GIF_JULIA_DRAGON_HASH),
    ('test-julia-z-auto-blob.gif', 142, 110, base.T_GIF_JULIA_BLOB_HASH),
  ],
)
def test_computation_integrity_hashes_of_test_images(img: str, w: int, h: int, hsh: str) -> None:
  """Test computation integrity. SUPER CRITICAL test to make sure computation is stable."""
  i_w: int
  i_h: int
  i_hsh: str
  i_w, i_h, i_hsh, _ = pixels.GetBasicDataFromImage((_IMAGES_DIR / img).read_bytes())
  assert i_w == w, f'Width mismatch for {img}: expected {w}, got {i_w}; BUG!'
  assert i_h == h, f'Height mismatch for {img}: expected {h}, got {i_h}; BUG!'
  assert i_hsh == hsh, (
    f'Hash mismatch for {img}: expected {hsh}, got {i_hsh}; did the computation machinery change?'
  )
