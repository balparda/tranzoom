# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Build script for the optional Cython-accelerated fractalfast extension.

Run from the repository root via `make cython` (or directly):

  poetry run python build_ext.py build_ext --inplace

This compiles src/tranzoom/core/fractalfast.py into a native .so (macOS/Linux)
or .pyd (Windows) extension, placed alongside the source file.  Python's import
system automatically prefers the compiled extension over the pure-Python fallback.

Prerequisites — install the optional cython dev group first:

  poetry sync

Notes:
  - The pure-Python src/tranzoom/core/fractalfast.py is always the source of truth;
    the compiled extension is a drop-in replacement and never committed to the repo.
  - The intermediate fractalfast.c file and the build/ directory are both gitignored.
  - annotation_typing is set to False so that PEP-484/PEP-563 Python annotations are
    not interpreted as Cython C-type declarations.  Explicit Cython type hints (via
    cython.int, cython.double, etc.) can be added later inside the source file.

"""

from __future__ import annotations

from Cython.Build import cythonize
from setuptools import setup

setup(
  ext_modules=cythonize(
    'src/tranzoom/core/fractalfast.py',
    compiler_directives={
      'language_level': '3',
      # # Keep Python-style type annotations; do NOT treat them as Cython C-type hints.
      # # This is required because the file uses `from __future__ import annotations`
      # # (PEP 563), making all annotations lazy strings at runtime.
      # 'annotation_typing': False,
    },
  ),
  package_dir={'': 'src'},
  zip_safe=False,
)
