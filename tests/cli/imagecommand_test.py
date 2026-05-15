# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Tests for: imagecommand.py."""

from __future__ import annotations

import pytest
from transcrypto.utils import config as app_config
from transcrypto.utils import logging as cli_logging

from tranzoom.cli import imagecommand  # pyright: ignore[reportUnusedImport] # noqa: F401


@pytest.fixture(autouse=True)
def reset_cli() -> None:
  """Reset CLI singleton before each test."""
  cli_logging.ResetConsole()
  app_config.ResetConfig()
