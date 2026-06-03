# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Build script for the optional Cython-accelerated fractalfast extension.

Run from the repository root via `make cython` (or directly):

  poetry run python build_ext.py build_ext --inplace

This compiles src/tranzoom/core/fractalfast.py into a native .so (macOS/Linux)
or .pyd (Windows) extension, placed alongside the source file. Python's import
system automatically prefers the compiled extension over the pure-Python fallback.

Notes:
  - The pure-Python src/tranzoom/core/fractalfast.py is always the source of truth;
    the compiled extension is a drop-in replacement and never committed to the repo.
  - The intermediate fractalfast.c file and the build/ directory are both gitignored.
  - annotation_typing defaults to True in Cython 3.x; with include_path=sys.path,
    Cython resolves `gmpy2.mpfr`/`gmpy2.mpq` annotations (via gmpy2.pxd, installed
    alongside gmpy2 in site-packages) to the C extension types, enabling direct
    C-level type specialization without any changes to the pure-Python source.
  - include_dirs=sys.path lets the C compiler find gmpy2.h; library_dirs is populated
    by _gmp_library_dirs() (Homebrew on macOS, no-op elsewhere); libraries=['gmp',
    'mpfr','mpc'] links the GMP/MPFR/MPC C libraries required by the gmpy2 C-API.

"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Extension, setup


def _gmp_library_dirs() -> list[str]:
  """Discover GMP/MPFR/MPC library directories at build time.

  Tries Homebrew (macOS) first, silently ignores errors on other platforms.
  Returns a list of directory paths to pass as library_dirs to the Extension.

  Returns:
      list[str]: Absolute paths to directories containing libgmp, libmpfr, libmpc.

  """
  dirs: list[str] = []
  # Homebrew (macOS, both Apple Silicon /opt/homebrew and Intel /usr/local)
  for pkg in ('gmp', 'mpfr', 'libmpc'):
    try:
      prefix = subprocess.run(
        ['brew', '--prefix', pkg],
        capture_output=True,
        text=True,
        check=True,
      ).stdout.strip()
      lib_dir = Path(prefix) / 'lib'
      if lib_dir.is_dir():
        dirs.append(str(lib_dir))
    except (subprocess.CalledProcessError, FileNotFoundError):
      pass  # brew unavailable or package not installed; linker falls back to system paths
  return dirs


# Extension object for fractalfast, wiring in the gmpy2 C-API headers and libraries.
# include_dirs=sys.path: C compiler needs to find gmpy2.h (lives in site-packages/gmpy2/).
# library_dirs: add Homebrew keg-only paths so the linker can find libgmp/libmpfr/libmpc.
# libraries: link against GMP, MPFR, and MPC shared libraries required by the C-API.
_fractalfast_ext = Extension(
  'tranzoom.core.fractalfast',
  sources=['src/tranzoom/core/fractalfast.py'],
  include_dirs=sys.path,
  library_dirs=_gmp_library_dirs(),
  libraries=['gmp', 'mpfr', 'mpc'],
)

setup(
  ext_modules=cythonize(
    _fractalfast_ext,
    # include_path=sys.path: Cython needs to find gmpy2.pxd (also in site-packages/gmpy2/)
    # so it can resolve `gmpy2.mpfr`/`gmpy2.mpq` annotations as the declared C extension
    # types; annotation_typing=True (the Cython 3.x default) makes this happen automatically.
    include_path=sys.path,
    compiler_directives={
      'language_level': '3',
    },
  ),
  package_dir={'': 'src'},
  zip_safe=False,
)
