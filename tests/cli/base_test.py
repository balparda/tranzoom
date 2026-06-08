# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: base.py."""

from __future__ import annotations

import pathlib

import pytest

from tranzoom.cli import base
from tranzoom.core import image

_REPO_ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent.parent
_IMAGES_DIR: pathlib.Path = _REPO_ROOT / 'tests' / 'data' / 'images'


@pytest.mark.parametrize(
  # SUPER CRITICAL test to make sure computation is stable: THINK before you change!
  ('img', 'w', 'h', 'hsh'),
  [
    # PNG - really only change if core computation changes, so these are more important to be stable
    # don't change anything here: change base.py if the computation changed
    ('demo-mandel-seahorse-tail.png', 1024, 1024, base.SEAHORSE_TAIL_HASH),
    ('demo-julia-suzana-wave.png', 512, 377, base.SUZANA_WAVE_HASH),
    # GIF - these may change for core computation, or if the animation frame machinery changes
    # don't change anything here: change base.py if the computation changed
    ('demo-mandel-seahorse-tail-anim.gif', 220, 220, base.SEAHORSE_ANIMATED_HASH),
    ('test-mandel-z-auto-seahorse.gif', 53, 39, base.T_GIF_SEAHORSE_HASH),
    ('test-mandel-z-auto-seeds300.gif', 31, 26, base.T_GIF_SEEDS_300_HASH),
    ('test-julia-z-auto-suzana.gif', 44, 59, base.T_GIF_JULIA_SUZANA_HASH),
    ('test-julia-z-auto-dragon.gif', 52, 67, base.T_GIF_JULIA_DRAGON_HASH),
    ('test-julia-z-auto-blob.gif', 71, 55, base.T_GIF_JULIA_BLOB_HASH),
  ],
)
def test_computation_integrity_hashes_of_test_images(img: str, w: int, h: int, hsh: str) -> None:
  """Test computation integrity. SUPER CRITICAL test to make sure computation is stable."""
  i_w: int
  i_h: int
  i_hsh: str
  i_w, i_h, i_hsh, _ = image.GetBasicDataFromImage((_IMAGES_DIR / img).read_bytes())
  assert w == i_w, f'Width mismatch for {img}: expected {w}, got {i_w}; BUG!'
  assert h == i_h, f'Height mismatch for {img}: expected {h}, got {i_h}; BUG!'
  assert hsh == i_hsh, (
    f'Hash mismatch for {img}: expected {hsh}, got {i_hsh}; did the computation machinery change?'
  )
