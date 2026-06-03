# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Fractal computing, CYTHON.

<https://cython.readthedocs.io/en/latest/>

Heavy use of gmpy2 for arbitrary precision, which is needed to render deep zooms correctly; see
<https://gmpy2.readthedocs.io/en/latest/>

Cython can use Python-like syntax plus static declarations to compile modules, and its
“pure Python mode” can consume PEP-484/526-style annotations or Cython annotations while
keeping files importable as Python. The killer feature for this project's case: gmpy2
exposes a C-API usable from Cython, with declared mpz, mpq, mpfr, and mpc extension types:
<https://gmpy2.readthedocs.io/en/latest/cython.html>

There is an important caveat: using the gmpy2 C-API can complicate binary wheels because
an extension using that C-API must match the GMP/MPFR/MPC libraries bundled/linked by gmpy2.
For a local accelerated optional module, that is manageable.

BEWARE when debugging/editing this module:

On MacOS (Python ≥ 3.8) --- and presumably on other systems too --- the default multiprocessing
start method is "spawn", not "fork". With spawn, each worker process is a fresh Python interpreter
that re-imports all modules from disk when it starts. This means that unless `--threads` is
manually set to 1, the code will reload for every worker every time an image is rendered.

This means that if you are executing some long computation with many fractals (think animation),
and you start editing this part of the codebase, you may break your running computation in
really ugly ways.
"""

import math


def NormalizeSmoothEscape(n: int, nu: float) -> tuple[int, float]:
  """Normalize the smooth escape part to be in [0,1) and adjust n accordingly.

  The smooth escape part is a fractional value that represents how far the orbit went beyond
  the escape radius at the escape iteration. We want to ensure that the final escape value
  is n + nu, where n is an integer and nu is in [0,1). This allows for smooth coloring
  of the escape time.

  Args:
    n (int): The integer escape iteration count.
    nu (float): The smooth escape part, which can be any real number.

  Returns:
    tuple[int, float]: A tuple of the adjusted integer escape iteration and the normalized
        smooth escape part.

  Raises:
    ValueError: if the normalized smooth escape part is not in [0,1) after normalization

  """
  # if nu is not finite consider it an error
  if not math.isfinite(nu):
    raise ValueError(f'nu is not a valid number {nu=}, bug! report')
  # get the integer shift to apply to n, and the new nu in [0,1)
  shift: int = math.floor(nu)
  n += shift
  nu -= shift
  # if nu is negative, we need to shift back the other way, to ensure nu is in [0,1)
  if nu < 0.0:
    n -= 1
    nu += 1.0
  # ensure n is not negative, in case the shift made it negative
  n = max(0, n)
  if not (0.0 <= nu < 1.0):
    raise ValueError(f'Normalized smooth escape range should be 0 <= {nu=} < 1, {n=}, bug! report')
  return (n, nu)
