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
_SEAHORSE_TAIL_ANIMATED_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'demo-mandel-seahorse-tail-anim.gif'
)
_SUZANA_WAVE_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'demo-julia-suzana-wave.png'
)
_T_GIF_SEAHORSE_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'test-mandel-z-auto-seahorse.gif'
)
_T_GIF_SEEDS_300_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'test-mandel-z-auto-seeds300.gif'
)
_T_GIF_JULIA_SUZANA_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'test-julia-z-auto-suzana.gif'
)
_T_GIF_JULIA_DRAGON_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'test-julia-z-auto-dragon.gif'
)
_T_GIF_JULIA_BLOB_PATH: pathlib.Path = (
  _REPO_ROOT / 'tests' / 'data' / 'images' / 'test-julia-z-auto-blob.gif'
)


def test_seahorse_tail_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromImage(_SEAHORSE_TAIL_PATH.read_bytes())
  assert w == h == 1024
  assert hsh == base.SEAHORSE_TAIL_HASH


def test_seahorse_tail_animated_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromImage(_SEAHORSE_TAIL_ANIMATED_PATH.read_bytes())
  assert w == h == 220
  assert hsh == base.SEAHORSE_ANIMATED_HASH


def test_suzana_wave_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromImage(_SUZANA_WAVE_PATH.read_bytes())
  assert w == 512
  assert h == 377
  assert hsh == base.SUZANA_WAVE_HASH


def test_t_gif_seahorse_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromImage(_T_GIF_SEAHORSE_PATH.read_bytes())
  assert w == 53
  assert h == 39
  assert hsh == base.T_GIF_SEAHORSE_HASH


def test_t_gif_seeds_300_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromImage(_T_GIF_SEEDS_300_PATH.read_bytes())
  assert w == 31
  assert h == 26
  assert hsh == base.T_GIF_SEEDS_300_HASH


def test_t_gif_julia_suzana_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromImage(_T_GIF_JULIA_SUZANA_PATH.read_bytes())
  assert w == 44
  assert h == 59
  assert hsh == base.T_GIF_JULIA_SUZANA_HASH


def test_t_gif_julia_dragon_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromImage(_T_GIF_JULIA_DRAGON_PATH.read_bytes())
  assert w == 52
  assert h == 67
  assert hsh == base.T_GIF_JULIA_DRAGON_HASH


def test_t_gif_julia_blob_has_correct_hash() -> None:
  """Test."""
  w, h, hsh, _ = image.GetBasicDataFromImage(_T_GIF_JULIA_BLOB_PATH.read_bytes())
  assert w == 71
  assert h == 55
  assert hsh == base.T_GIF_JULIA_BLOB_HASH
