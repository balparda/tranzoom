# SPDX-FileCopyrightText: Copyright 2026 Daniel Balparda <balparda@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Business logic examples."""

from __future__ import annotations

import secrets
import string

from transcrypto.utils import saferandom


def RandomNum(min_: int, max_: int) -> int:
  """Generate a random integer.

  Args:
      min_ (int): Minimum value (inclusive).
      max_ (int): Maximum value (inclusive).

  Returns:
      int: A random integer between min_ and max_ inclusive.

  """
  return saferandom.RandInt(min_, max_)


def RandomStr(length: int, alphabet: str | None) -> str:
  """Generate a random string.

  Args:
      length (int): Length of the random string.
      alphabet (str): Custom alphabet to sample from (defaults to [a-zA-Z0-9]).

  Returns:
      str: A random string of the specified length.

  """
  chars: str = alphabet or str(string.ascii_letters + string.digits)
  return ''.join(secrets.choice(chars) for _ in range(length))
