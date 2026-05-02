#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Daniel Balparda <balparda@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Script name / short purpose.

This file is meant to be executed directly.

Usage
- ./scripts/<name> [args]
- Or: poetry run <task>

Notes
-----
- Keep logic thin here; import and call into src/ code.

"""

from __future__ import annotations

from mycli import mycli


def Main() -> int:
  """Call into the CLI module; thin wrapper for app.

  Returns:
    int: Exit code

  """
  mycli.app()
  return 0


if __name__ == '__main__':
  raise SystemExit(Main())
