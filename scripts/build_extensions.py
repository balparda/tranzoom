#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Build the Cython extensions."""

from __future__ import annotations

import pathlib
import shutil
import subprocess  # noqa: S404
import sys

import setuptools
import setuptools.command.build_ext
from Cython.Build import (  # pyright: ignore[reportMissingImports]
  cythonize,  # pyright: ignore[reportUnknownVariableType]
)

ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parents[1]
SRC: pathlib.Path = ROOT / 'src'


def _GMPLibraryDirs() -> list[str]:
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
      prefix: str = subprocess.run(  # noqa: S603
        ['brew', '--prefix', pkg],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
      ).stdout.strip()
      lib_dir: pathlib.Path = pathlib.Path(prefix) / 'lib'
      if lib_dir.is_dir():
        dirs.append(str(lib_dir))
    except subprocess.CalledProcessError, FileNotFoundError:
      pass  # brew unavailable or package not installed; linker falls back to system paths
  return dirs


def BuildCython() -> None:
  """Build the Cython extensions.

  Builds in-place, copying the resulting .so files back to the source directory.
  """
  # add both versions of the core computation
  extensions: list[setuptools.Extension] = [
    setuptools.Extension(
      'tranzoom.core.fractalc',
      [str(SRC / 'tranzoom' / 'core' / 'fractalc.pyx')],
      include_dirs=sys.path,
      library_dirs=_GMPLibraryDirs(),
      libraries=['gmp', 'mpfr', 'mpc'],
    ),
    setuptools.Extension(
      'tranzoom.core.fractalfast',
      [str(SRC / 'tranzoom' / 'core' / 'fractalfast.py')],
      include_dirs=sys.path,
      library_dirs=_GMPLibraryDirs(),
      libraries=['gmp', 'mpfr', 'mpc'],
    ),
  ]
  # "cythonize"
  ext_modules: list[setuptools.Extension] = cythonize(  # type: ignore[no-untyped-call]
    extensions,
    compiler_directives={
      'language_level': '3',
      'binding': True,
      'boundscheck': False,
      'wraparound': False,
      'initializedcheck': False,
      'nonecheck': False,
      'cdivision': True,
      'infer_types': True,
    },
  )
  # make a distribution and build the extensions in-place
  cmd = setuptools.command.build_ext.build_ext(
    setuptools.Distribution(
      # add the extensions to a dummy distribution so the build_ext command will know what to build
      {
        'name': 'tranzoom',
        'ext_modules': ext_modules,
      }
    )
  )
  cmd.ensure_finalized()
  cmd.run()
  # copy the built .so files back to the source directory so they can be imported in-place
  for output in cmd.get_outputs():
    p_output = pathlib.Path(output)
    relative: pathlib.Path = p_output.relative_to(cmd.build_lib)
    destination: pathlib.Path = SRC / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(p_output, destination)
    mode: int = destination.stat().st_mode
    mode |= (mode & 0o444) >> 2
    destination.chmod(mode)


if __name__ == '__main__':
  BuildCython()
