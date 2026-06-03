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

from gmpy2 cimport *

cdef extern from "gmp.h":
    void mpz_set_si(mpz_t, long)

import_gmpy2()   # needed to initialize the C-API

cdef mpz z = GMPy_MPZ_New(NULL)
mpz_set_si(MPZ(z), -7)

def haha():
    return z
