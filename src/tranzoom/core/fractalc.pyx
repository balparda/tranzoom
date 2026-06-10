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

import warnings
import tqdm.rich
from tranzoom.core import frame, image
from tqdm import TqdmExperimentalWarning

from libc.stdlib cimport malloc, free
from libc.math cimport isfinite, floor
from libc.string cimport memcpy
from libc.stdint cimport int32_t, uint32_t, uint64_t

from gmpy2 cimport *

cdef extern from 'gmp.h':
  void mpq_init(mpq_t) nogil
  void mpq_clear(mpq_t) nogil
  void mpq_set_si(mpq_t, long, unsigned long) nogil
  void mpq_add '__gmpq_add'(mpq_t, mpq_srcptr, mpq_srcptr) nogil
  void mpq_sub '__gmpq_sub'(mpq_t, mpq_srcptr, mpq_srcptr) nogil
  void mpq_mul '__gmpq_mul'(mpq_t, mpq_srcptr, mpq_srcptr) nogil
  void mpq_div '__gmpq_div'(mpq_t, mpq_srcptr, mpq_srcptr) nogil


cdef extern from 'mpfr.h':
  void mpfr_init2(mpfr_t, mpfr_prec_t)
  void mpfr_clear(mpfr_t)

  int mpfr_const_pi(mpfr_t, mpfr_rnd_t)

  int mpfr_cmp(mpfr_srcptr, mpfr_srcptr)
  int mpfr_cmp_ui(mpfr_srcptr, unsigned long)
  int mpfr_less_p(mpfr_srcptr, mpfr_srcptr)
  int mpfr_greater_p(mpfr_srcptr, mpfr_srcptr)
  int mpfr_lessequal_p(mpfr_srcptr, mpfr_srcptr)
  int mpfr_greaterequal_p(mpfr_srcptr, mpfr_srcptr)
  int mpfr_zero_p(mpfr_srcptr)
  int mpfr_fits_slong_p(mpfr_srcptr, mpfr_rnd_t)

  int mpfr_floor(mpfr_t, mpfr_srcptr)
  int mpfr_add(mpfr_t, mpfr_srcptr, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_sub(mpfr_t, mpfr_srcptr, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_mul(mpfr_t, mpfr_srcptr, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_div(mpfr_t, mpfr_srcptr, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_sqr(mpfr_t, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_sqrt(mpfr_t, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_log(mpfr_t, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_log2(mpfr_t, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_atan2(mpfr_t, mpfr_srcptr, mpfr_srcptr, mpfr_rnd_t)

  double mpfr_get_d(mpfr_srcptr, mpfr_rnd_t)
  long mpfr_get_si(mpfr_srcptr, mpfr_rnd_t)

  int mpfr_set(mpfr_t, mpfr_srcptr, mpfr_rnd_t)
  int mpfr_set_ui(mpfr_t, unsigned long, mpfr_rnd_t)
  int mpfr_set_si(mpfr_t, long, mpfr_rnd_t)
  int mpfr_set_d(mpfr_t, double, mpfr_rnd_t)
  int mpfr_set_q(mpfr_t, mpq_srcptr, mpfr_rnd_t)


import_gmpy2()


cdef inline void mpfr_min_set(mpfr_t out, mpfr_t a, mpfr_t b) noexcept:
  if mpfr_lessequal_p(a, b):
    mpfr_set(out, a, MPFR_RNDN)
  else:
    mpfr_set(out, b, MPFR_RNDN)


cdef inline void mpfr_max_set(mpfr_t out, mpfr_t a, mpfr_t b) noexcept:
  if mpfr_greaterequal_p(a, b):
    mpfr_set(out, a, MPFR_RNDN)
  else:
    mpfr_set(out, b, MPFR_RNDN)


cdef inline double smooth_escape_fraction(
  mpfr_t mag_z2,
  mpfr_t half,
  mpfr_t tmp0,
  mpfr_t tmp1,
) noexcept:
  """
  Equivalent of:

    1.0 - float(gmpy2.log2(0.5 * gmpy2.log(mag_z2)))
  """
  cdef double out

  mpfr_log(tmp0, mag_z2, MPFR_RNDN)
  mpfr_mul(tmp0, tmp0, half, MPFR_RNDN)
  mpfr_log2(tmp1, tmp0, MPFR_RNDN)

  out = 1.0 - mpfr_get_d(tmp1, MPFR_RNDN)
  if not isfinite(out):
    return 0.0
  return out


cdef inline void NormalizeSmoothEscape_c(Py_ssize_t *n, double *nu) except *:
  """Cython hot-path version of NormalizeSmoothEscape()."""
  cdef double shift_d

  if not isfinite(nu[0]):
    raise image.Error(f'nu is not a valid number nu={nu[0]}, bug! report')

  shift_d = floor(nu[0])
  n[0] += <Py_ssize_t>shift_d
  nu[0] -= shift_d

  if nu[0] < 0.0:
    n[0] -= 1
    nu[0] += 1.0

  if n[0] < 0:
    n[0] = 0

  if not (0.0 <= nu[0] < 1.0):
    raise image.Error(f'Normalized smooth escape range 0 <= nu={nu[0]} < 1, n={n[0]}, bug! report')


cdef inline void NormalizeSmoothSet_c(
  mpfr_t v,
  mpfr_t lo,
  mpfr_t d,
  mpfr_t tmp0,
  mpfr_t tmp1,
  mpfr_t tmp2,
  mpfr_t zero,
  mpfr_t one,
  mpfr_t interior_span_mpfr,
  long long interior_max,
  Py_ssize_t *n,
  double *nu,
) except *:
  """
  Hot-path MPFR version of NormalizeSmoothSet().
  """
  cdef long whole_l
  cdef long long whole
  cdef double frac

  if mpfr_lessequal_p(d, zero):
    raise image.Error('Invalid normalization range, should be > 0, bug! report')

  # tmp0 = (v - lo) / d
  mpfr_sub(tmp0, v, lo, MPFR_RNDN)
  mpfr_div(tmp0, tmp0, d, MPFR_RNDN)

  # clamp tmp0 to [0, 1]
  if mpfr_less_p(tmp0, zero):
    mpfr_set(tmp0, zero, MPFR_RNDN)
  elif mpfr_greater_p(tmp0, one):
    mpfr_set(tmp0, one, MPFR_RNDN)

  # tmp1 = 1 + tmp0 * interior_span_mpfr
  mpfr_mul(tmp1, tmp0, interior_span_mpfr, MPFR_RNDN)
  mpfr_add(tmp1, tmp1, one, MPFR_RNDN)

  # tmp2 = floor(tmp1)
  mpfr_floor(tmp2, tmp1)

  # Convert bucket to integer.
  #
  # In the intended range this is <= 2^31, so it fits in long on LP64.
  # If it does not fit in C long, saturate defensively.
  if mpfr_fits_slong_p(tmp2, MPFR_RNDZ):
    whole_l = mpfr_get_si(tmp2, MPFR_RNDZ)
    whole = <long long>whole_l
  else:
    whole = interior_max

  if whole < 1:
    whole = 1
  elif whole > interior_max:
    whole = interior_max

  # tmp2 = frac = scaled - whole
  #
  # Use double because all integers up to 2^53 are exactly representable;
  # SET_INTERIOR_INT_MAX is 2^31.
  mpfr_set_d(tmp2, <double>whole, MPFR_RNDN)
  mpfr_sub(tmp2, tmp1, tmp2, MPFR_RNDN)

  # Defensive only: normal operation gives 0 <= frac < 1.
  if mpfr_less_p(tmp2, zero):
    mpfr_set(tmp2, zero, MPFR_RNDN)
  elif not mpfr_less_p(tmp2, one):
    if whole < interior_max:
      whole += 1
      mpfr_sub(tmp2, tmp2, one, MPFR_RNDN)
    else:
      mpfr_set(tmp2, zero, MPFR_RNDN)

  frac = mpfr_get_d(tmp2, MPFR_RNDN)

  if not isfinite(frac) or not (0.0 <= frac < 1.0):
    raise image.Error(
      f'Invalid normalized Set fractional part: nu={frac}, whole={whole}'
    )

  n[0] = -<Py_ssize_t>whole
  nu[0] = frac


cdef inline uint64_t EncodeIntFloatTo64_c(int i, double f) noexcept:
  cdef:
    int32_t i32 = <int32_t>i
    float f32 = <float>f
    uint32_t ibits
    uint32_t fbits

  memcpy(&ibits, &i32, sizeof(uint32_t))
  memcpy(&fbits, &f32, sizeof(uint32_t))

  return (
    ((<uint64_t>ibits & 0xffffffff) << 32) |
    (<uint64_t>fbits & 0xffffffff)
  )


def NormalizeSmoothEscape(int n, double nu) -> tuple[int, float]:
  """Python-callable wrapper."""
  cdef Py_ssize_t nn = n
  cdef double nnu = nu
  NormalizeSmoothEscape_c(&nn, &nnu)
  return (<int>nn, nnu)


def EncodeIntFloatTo64(int i, double f) -> int:
  """Python-callable wrapper."""
  return <uint64_t>EncodeIntFloatTo64_c(i, f)


def MandelbrotComputation(object inp):
  """
  Cython/MPFR version of MandelbrotComputation.

  Python-level object fields are still accessed as Python objects, but the inner numeric
  operations are raw MPFR/GMP calls.
  """
  cdef:
    bint is_preprocess
    object img
    object p_bar
    bint has_procs
    int n_task
    Py_ssize_t width, height, depth
    Py_ssize_t px, py, px_count
    Py_ssize_t escaped_at
    int n_interior = 0
    double smooth_escape

    mpfr_prec_t prec

    mpfr_t *xs = NULL

    mpq_t dx_q
    mpq_t dy_q
    mpq_t tmpq0
    mpq_t tmpq1

    mpfr_t zero, sixteenth, fourth, half, one, two, four
    mpfr_t cx, cy
    mpfr_t zx, zy, zx2, zy2, mag_z2
    mpfr_t min_z2, max_z2
    mpfr_t x_minus_quarter, x_plus_one, q, tmp0, tmp1, tmp2
    mpfr_t mpfr_pi, mpfr_two_pi, max_iter_p_1
    mpfr_t max_lo, max_hi, min_lo, min_hi, ang_lo, ang_hi, imag_lo, imag_hi
    mpfr_t sqrt_lo, sqrt_delta, sqrt_lo2, sqrt_delta2, ang_delta, imag_delta
    mpfr_t sqrt_min, sqrt_max, ang, imag_acc, imag_mean
    mpfr_t interior_resolution_mpfr

    bint stats_max = False
    bint stats_min = False
    bint stats_ang = False
    bint stats_imag = False

    object set_points

  is_preprocess = (
    inp.params.width == frame.MIN_IMAGE_SIZE and
    inp.params.height == frame.MIN_IMAGE_SIZE
  )

  img = image.Image(inp.params)

  width = inp.params.width
  height = inp.params.height
  depth = inp.params.depth
  set_points = inp.params.set_points

  # Keep your existing exact mpq frame-size logic, but avoid per-pixel gmpy2 calls.
  mpq_init(dx_q)
  mpq_init(dy_q)
  mpq_init(tmpq0)
  mpq_init(tmpq1)

  # Requires inp.params.frm.size to be a tuple of gmpy2.mpq objects.
  dx_obj, dy_obj = inp.params.frm.size

  mpq_set(dx_q, MPQ(<mpq>dx_obj))
  mpq_set(dy_q, MPQ(<mpq>dy_obj))

  mpq_set_si(tmpq0, width - 1, 1)
  mpq_div(dx_q, dx_q, tmpq0)

  mpq_set_si(tmpq0, height - 1, 1)
  mpq_div(dy_q, dy_q, tmpq0)

  if dx_obj <= 0 or dy_obj <= 0:
    mpq_clear(dx_q)
    mpq_clear(dy_q)
    mpq_clear(tmpq0)
    mpq_clear(tmpq1)
    raise image.Error(f'frame must have positive area, got {dx_obj=} and {dy_obj=}')

  with inp.params.context:
    # You may prefer to expose this from inp.params rather than introspecting.
    prec = inp.params.context.precision

    mpfr_init2(zero, prec)
    mpfr_init2(sixteenth, prec)
    mpfr_init2(fourth, prec)
    mpfr_init2(half, prec)
    mpfr_init2(one, prec)
    mpfr_init2(two, prec)
    mpfr_init2(four, prec)

    mpfr_init2(cx, prec)
    mpfr_init2(cy, prec)
    mpfr_init2(zx, prec)
    mpfr_init2(zy, prec)
    mpfr_init2(zx2, prec)
    mpfr_init2(zy2, prec)
    mpfr_init2(mag_z2, prec)
    mpfr_init2(min_z2, prec)
    mpfr_init2(max_z2, prec)

    mpfr_init2(x_minus_quarter, prec)
    mpfr_init2(x_plus_one, prec)
    mpfr_init2(q, prec)
    mpfr_init2(tmp0, prec)
    mpfr_init2(tmp1, prec)
    mpfr_init2(tmp2, prec)

    mpfr_init2(mpfr_pi, prec)
    mpfr_init2(mpfr_two_pi, prec)
    mpfr_init2(max_iter_p_1, prec)

    mpfr_init2(max_lo, prec)
    mpfr_init2(max_hi, prec)
    mpfr_init2(min_lo, prec)
    mpfr_init2(min_hi, prec)
    mpfr_init2(ang_lo, prec)
    mpfr_init2(ang_hi, prec)
    mpfr_init2(imag_lo, prec)
    mpfr_init2(imag_hi, prec)

    mpfr_init2(sqrt_lo, prec)
    mpfr_init2(sqrt_delta, prec)
    mpfr_init2(sqrt_lo2, prec)
    mpfr_init2(sqrt_delta2, prec)
    mpfr_init2(ang_delta, prec)
    mpfr_init2(imag_delta, prec)

    mpfr_init2(sqrt_min, prec)
    mpfr_init2(sqrt_max, prec)
    mpfr_init2(ang, prec)
    mpfr_init2(imag_acc, prec)
    mpfr_init2(imag_mean, prec)
    mpfr_init2(interior_resolution_mpfr, prec)

    try:
      mpfr_set_ui(zero, 0, MPFR_RNDN)
      mpfr_set_d(sixteenth, 0.0625, MPFR_RNDN)
      mpfr_set_d(fourth, 0.25, MPFR_RNDN)
      mpfr_set_d(half, 0.5, MPFR_RNDN)
      mpfr_set_ui(one, 1, MPFR_RNDN)
      mpfr_set_ui(two, 2, MPFR_RNDN)
      mpfr_set_ui(four, 4, MPFR_RNDN)
      mpfr_set(interior_resolution_mpfr, MPFR(<mpfr>frame.MPFR_SET_INTERIOR_INT_SPAN), MPFR_RNDN)

      mpfr_const_pi(mpfr_pi, MPFR_RNDN)
      mpfr_mul(mpfr_two_pi, two, mpfr_pi, MPFR_RNDN)

      mpfr_set_si(max_iter_p_1, depth, MPFR_RNDN)
      mpfr_add(max_iter_p_1, max_iter_p_1, one, MPFR_RNDN)

      mpfr_set(max_lo, four, MPFR_RNDN)
      mpfr_set(max_hi, zero, MPFR_RNDN)
      mpfr_set(min_lo, four, MPFR_RNDN)
      mpfr_set(min_hi, zero, MPFR_RNDN)
      mpfr_set(ang_lo, one, MPFR_RNDN)
      mpfr_set(ang_hi, zero, MPFR_RNDN)
      mpfr_set(imag_lo, one, MPFR_RNDN)
      mpfr_set(imag_hi, zero, MPFR_RNDN)

      mpfr_set(sqrt_lo, zero, MPFR_RNDN)
      mpfr_set(sqrt_delta, zero, MPFR_RNDN)
      mpfr_set(sqrt_lo2, zero, MPFR_RNDN)
      mpfr_set(sqrt_delta2, zero, MPFR_RNDN)
      mpfr_set(ang_delta, zero, MPFR_RNDN)
      mpfr_set(imag_delta, zero, MPFR_RNDN)

      if inp.stats is not None:
        if (
          inp.stats.max_lo is not None and
          inp.stats.max_hi is not None and
          inp.stats.max_hi > inp.stats.max_lo
        ):
          stats_max = True
          mpfr_sqrt(sqrt_lo, MPFR(<mpfr>inp.stats.max_lo), MPFR_RNDN)
          mpfr_sqrt(tmp0, MPFR(<mpfr>inp.stats.max_hi), MPFR_RNDN)
          mpfr_sub(sqrt_delta, tmp0, sqrt_lo, MPFR_RNDN)

        if (
          inp.stats.min_lo is not None and
          inp.stats.min_hi is not None and
          inp.stats.min_hi > inp.stats.min_lo
        ):
          stats_min = True
          mpfr_sqrt(sqrt_lo2, MPFR(<mpfr>inp.stats.min_lo), MPFR_RNDN)
          mpfr_sqrt(tmp0, MPFR(<mpfr>inp.stats.min_hi), MPFR_RNDN)
          mpfr_sub(sqrt_delta2, tmp0, sqrt_lo2, MPFR_RNDN)

        if (
          inp.stats.ang_lo is not None and
          inp.stats.ang_hi is not None and
          inp.stats.ang_hi > inp.stats.ang_lo
        ):
          stats_ang = True
          mpfr_sub(ang_delta, MPFR(<mpfr>inp.stats.ang_hi), MPFR(<mpfr>inp.stats.ang_lo), MPFR_RNDN)

        if (
          inp.stats.imag_lo is not None and
          inp.stats.imag_hi is not None and
          inp.stats.imag_hi > inp.stats.imag_lo
        ):
          stats_imag = True
          mpfr_sub(imag_delta, MPFR(<mpfr>inp.stats.imag_hi), MPFR(<mpfr>inp.stats.imag_lo), MPFR_RNDN)

      # xs[i] = mpfr(top_re + i * dx_q)
      xs = <mpfr_t *>malloc(width * sizeof(mpfr_t))
      if xs == NULL:
        raise MemoryError()

      for px in range(width):
        mpfr_init2(xs[px], prec)

        # tmpq0 = i * dx_q
        mpq_set_si(tmpq0, px, 1)
        mpq_mul(tmpq0, tmpq0, dx_q)

        # tmpq1 = top_re + tmpq0
        mpq_set(tmpq1, MPQ(<mpq>inp.params.frm.top_re))
        # tmpq1 += tmpq0 via subtraction with negative is avoided by using Python fallback
        # If you want 100% GMP here, add mpq_add to the extern block and use it:
        #   void mpq_add(mpq_t, mpq_srcptr, mpq_srcptr)
        #   mpq_add(tmpq1, tmpq1, tmpq0)
        #
        # Temporary safe bridge:
        # mpfr_set_q(xs[px], MPQ(<mpq>(inp.params.frm.top_re + px * dx_obj)), MPFR_RNDN)
        mpq_set_si(tmpq0, px, 1)
        mpq_mul(tmpq0, tmpq0, dx_q)
        mpq_set(tmpq1, MPQ(<mpq>inp.params.frm.top_re))
        mpq_add(tmpq1, tmpq1, tmpq0)
        mpfr_set_q(xs[px], tmpq1, MPFR_RNDN)

      has_procs = inp.total_tasks > 1
      n_task = inp.n_task - 1

      with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=TqdmExperimentalWarning)
        p_bar = tqdm.rich.tqdm(
          total=width * height,
          desc='Pre' if is_preprocess else 'Img',
          unit='px',
          dynamic_ncols=True,
          smoothing=0.1,
          colour='green',
          disable=not inp.progress_bar or (has_procs and n_task != 0),
        )

      px_count = -1

      for py in range(height):
        # cy = mpfr(top_im - py * dy_q)
        #
        # Same note as above: add mpq_sub/mpq_mul/mpq_add and keep this all-GMP.
        # mpfr_set_q(cy, MPQ(<mpq>(inp.params.frm.top_im - py * dy_obj)), MPFR_RNDN)
        mpq_set_si(tmpq0, py, 1)
        mpq_mul(tmpq0, tmpq0, dy_q)
        mpq_set(tmpq1, MPQ(<mpq>inp.params.frm.top_im))
        mpq_sub(tmpq1, tmpq1, tmpq0)
        mpfr_set_q(cy, tmpq1, MPFR_RNDN)

        for px in range(width):
          px_count += 1

          if has_procs and (px_count % inp.total_tasks) != n_task:
            p_bar.update(1)
            continue

          mpfr_set(cx, xs[px], MPFR_RNDN)

          if set_points is None:
            # Main cardioid:
            # x_minus_quarter = cx - 1/4
            mpfr_sub(x_minus_quarter, cx, fourth, MPFR_RNDN)

            # q = x_minus_quarter^2 + cy^2
            mpfr_sqr(tmp0, x_minus_quarter, MPFR_RNDN)
            mpfr_sqr(tmp1, cy, MPFR_RNDN)
            mpfr_add(q, tmp0, tmp1, MPFR_RNDN)

            # tmp0 = q * (q + x_minus_quarter)
            mpfr_add(tmp0, q, x_minus_quarter, MPFR_RNDN)
            mpfr_mul(tmp0, q, tmp0, MPFR_RNDN)

            # tmp1 = 1/4 * cy^2
            mpfr_sqr(tmp1, cy, MPFR_RNDN)
            mpfr_mul(tmp1, fourth, tmp1, MPFR_RNDN)

            if mpfr_lessequal_p(tmp0, tmp1):
              n_interior += 1
              img.escape[px_count] = EncodeIntFloatTo64_c(-frame.SET_INTERIOR_INT_MAX, 0.0)
              p_bar.update(1)
              continue

            # Period-2 bulb:
            # (cx + 1)^2 + cy^2 <= 1/16
            mpfr_add(x_plus_one, cx, one, MPFR_RNDN)
            mpfr_sqr(tmp0, x_plus_one, MPFR_RNDN)
            mpfr_sqr(tmp1, cy, MPFR_RNDN)
            mpfr_add(tmp0, tmp0, tmp1, MPFR_RNDN)

            if mpfr_lessequal_p(tmp0, sixteenth):
              n_interior += 1
              img.escape[px_count] = EncodeIntFloatTo64_c(-frame.SET_INTERIOR_INT_MAX, 0.0)
              p_bar.update(1)
              continue

          mpfr_set(zx, zero, MPFR_RNDN)
          mpfr_set(zy, zero, MPFR_RNDN)
          mpfr_set(min_z2, four, MPFR_RNDN)
          mpfr_set(max_z2, zero, MPFR_RNDN)
          mpfr_set(imag_acc, zero, MPFR_RNDN)

          escaped_at = 0
          smooth_escape = 0.0

          for escaped_at in range(depth):
            mpfr_sqr(zx2, zx, MPFR_RNDN)
            mpfr_sqr(zy2, zy, MPFR_RNDN)
            mpfr_add(mag_z2, zx2, zy2, MPFR_RNDN)

            if mpfr_greater_p(mag_z2, four):
              for _ in range(frame.SMOOTH_EXTRA_ITERS):
                escaped_at += 1

                # zy = 2 * zx * zy + cy
                mpfr_mul(tmp0, zx, zy, MPFR_RNDN)
                mpfr_mul(tmp0, two, tmp0, MPFR_RNDN)
                mpfr_add(zy, tmp0, cy, MPFR_RNDN)

                # zx = zx2 - zy2 + cx
                mpfr_sub(tmp1, zx2, zy2, MPFR_RNDN)
                mpfr_add(zx, tmp1, cx, MPFR_RNDN)

                mpfr_sqr(zx2, zx, MPFR_RNDN)
                mpfr_sqr(zy2, zy, MPFR_RNDN)

              mpfr_add(mag_z2, zx2, zy2, MPFR_RNDN)
              smooth_escape = smooth_escape_fraction(mag_z2, half, tmp0, tmp1)

              NormalizeSmoothEscape_c(&escaped_at, &smooth_escape)
              break

            if (
              set_points == frame.SetHighlightAlgorithm.IMAGINARY and
              mpfr_greater_p(mag_z2, zero)
            ):
              # imag_acc += zy2 / mag_z2
              mpfr_div(tmp0, zy2, mag_z2, MPFR_RNDN)
              mpfr_add(imag_acc, imag_acc, tmp0, MPFR_RNDN)

            # zy = 2 * zx * zy + cy
            mpfr_mul(tmp0, zx, zy, MPFR_RNDN)
            mpfr_mul(tmp0, two, tmp0, MPFR_RNDN)
            mpfr_add(zy, tmp0, cy, MPFR_RNDN)

            # zx = zx2 - zy2 + cx
            mpfr_sub(tmp1, zx2, zy2, MPFR_RNDN)
            mpfr_add(zx, tmp1, cx, MPFR_RNDN)

            if set_points == frame.SetHighlightAlgorithm.MIN:
              if mpfr_less_p(mag_z2, min_z2):
                mpfr_set(min_z2, mag_z2, MPFR_RNDN)
            elif set_points == frame.SetHighlightAlgorithm.MAX:
              if mpfr_greater_p(mag_z2, max_z2):
                mpfr_set(max_z2, mag_z2, MPFR_RNDN)

          else:
            if not (
              mpfr_greaterequal_p(max_z2, zero) and
              mpfr_less_p(max_z2, four)
            ):
              raise image.Error(
                f'Interior point exceeded max |z|^2 of 4, should never happen, '
                f'max_z2={GMPy_MPFR_From_mpfr(max_z2)}'
              )

            n_interior += 1

            if set_points is None:
              escaped_at = -frame.SET_INTERIOR_INT_MAX
              smooth_escape = 0.0

            elif set_points == frame.SetHighlightAlgorithm.MIN:
              if mpfr_less_p(min_z2, min_lo):
                mpfr_set(min_lo, min_z2, MPFR_RNDN)
              if mpfr_greater_p(min_z2, min_hi):
                mpfr_set(min_hi, min_z2, MPFR_RNDN)

              mpfr_sqrt(sqrt_min, min_z2, MPFR_RNDN)
              if stats_min:
                NormalizeSmoothSet_c(
                  sqrt_min, sqrt_lo2, sqrt_delta2,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )
              else:
                NormalizeSmoothSet_c(
                  sqrt_min, zero, MPFR(<mpfr>frame.MPFR_MAX_SET_Z),
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )

            elif set_points == frame.SetHighlightAlgorithm.MAX:
              if mpfr_less_p(max_z2, max_lo):
                mpfr_set(max_lo, max_z2, MPFR_RNDN)
              if mpfr_greater_p(max_z2, max_hi):
                mpfr_set(max_hi, max_z2, MPFR_RNDN)

              mpfr_sqrt(sqrt_max, max_z2, MPFR_RNDN)
              if stats_max:
                NormalizeSmoothSet_c(
                  sqrt_max, sqrt_lo, sqrt_delta,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )
              else:
                NormalizeSmoothSet_c(
                  sqrt_max, zero, MPFR(<mpfr>frame.MPFR_MAX_SET_Z),
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )

            elif set_points == frame.SetHighlightAlgorithm.ANGLE:
              # ang = atan2(zy, zx)
              # ang = (ang + pi) / (2*pi)
              mpfr_atan2(ang, zy, zx, MPFR_RNDN)
              mpfr_add(ang, ang, mpfr_pi, MPFR_RNDN)
              mpfr_div(ang, ang, mpfr_two_pi, MPFR_RNDN)

              if mpfr_less_p(ang, ang_lo):
                mpfr_set(ang_lo, ang, MPFR_RNDN)
              if mpfr_greater_p(ang, ang_hi):
                mpfr_set(ang_hi, ang, MPFR_RNDN)

              if stats_ang:
                NormalizeSmoothSet_c(
                  ang, MPFR(<mpfr>inp.stats.ang_lo), ang_delta,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )
              else:
                NormalizeSmoothSet_c(
                  ang, zero, one,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )

            elif set_points == frame.SetHighlightAlgorithm.IMAGINARY:
              # imag_mean = (imag_acc / max_iter_p_1) / frame.MPFR_MAX_SET_Z
              mpfr_div(imag_mean, imag_acc, max_iter_p_1, MPFR_RNDN)
              mpfr_div(imag_mean, imag_mean, MPFR(<mpfr>frame.MPFR_MAX_SET_Z), MPFR_RNDN)

              if mpfr_less_p(imag_mean, imag_lo):
                mpfr_set(imag_lo, imag_mean, MPFR_RNDN)
              if mpfr_greater_p(imag_mean, imag_hi):
                mpfr_set(imag_hi, imag_mean, MPFR_RNDN)

              if stats_imag:
                NormalizeSmoothSet_c(
                  imag_mean, MPFR(<mpfr>inp.stats.imag_lo), imag_delta,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )
              else:
                NormalizeSmoothSet_c(
                  imag_mean, zero, one,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )

            else:
              raise image.Error(f'Unknown fractal type {inp.params.set_points=}; should never happen')

          img.escape[px_count] = EncodeIntFloatTo64_c(<int>escaped_at, smooth_escape)
          p_bar.update(1)

      p_bar.close()

      img.stats = image.FractalStats(
        n_px=width * height,
        n_interior=n_interior,

        max_lo=GMPy_MPFR_From_mpfr(max_lo) if mpfr_greaterequal_p(max_hi, max_lo) else None,
        max_hi=GMPy_MPFR_From_mpfr(max_hi) if mpfr_greaterequal_p(max_hi, max_lo) else None,

        min_lo=GMPy_MPFR_From_mpfr(min_lo) if mpfr_greaterequal_p(min_hi, min_lo) else None,
        min_hi=GMPy_MPFR_From_mpfr(min_hi) if mpfr_greaterequal_p(min_hi, min_lo) else None,

        ang_lo=GMPy_MPFR_From_mpfr(ang_lo) if mpfr_greaterequal_p(ang_hi, ang_lo) else None,
        ang_hi=GMPy_MPFR_From_mpfr(ang_hi) if mpfr_greaterequal_p(ang_hi, ang_lo) else None,

        imag_lo=GMPy_MPFR_From_mpfr(imag_lo) if mpfr_greaterequal_p(imag_hi, imag_lo) else None,
        imag_hi=GMPy_MPFR_From_mpfr(imag_hi) if mpfr_greaterequal_p(imag_hi, imag_lo) else None,
      )

      return image.FractalTaskOutput(
        img=img,
        n_task=inp.n_task,
        total_tasks=inp.total_tasks,
      )

    finally:
      if xs != NULL:
        for px in range(width):
          mpfr_clear(xs[px])
        free(xs)

      mpfr_clear(zero)
      mpfr_clear(sixteenth)
      mpfr_clear(fourth)
      mpfr_clear(half)
      mpfr_clear(one)
      mpfr_clear(two)
      mpfr_clear(four)

      mpfr_clear(cx)
      mpfr_clear(cy)
      mpfr_clear(zx)
      mpfr_clear(zy)
      mpfr_clear(zx2)
      mpfr_clear(zy2)
      mpfr_clear(mag_z2)
      mpfr_clear(min_z2)
      mpfr_clear(max_z2)

      mpfr_clear(x_minus_quarter)
      mpfr_clear(x_plus_one)
      mpfr_clear(q)
      mpfr_clear(tmp0)
      mpfr_clear(tmp1)
      mpfr_clear(tmp2)

      mpfr_clear(mpfr_pi)
      mpfr_clear(mpfr_two_pi)
      mpfr_clear(max_iter_p_1)

      mpfr_clear(max_lo)
      mpfr_clear(max_hi)
      mpfr_clear(min_lo)
      mpfr_clear(min_hi)
      mpfr_clear(ang_lo)
      mpfr_clear(ang_hi)
      mpfr_clear(imag_lo)
      mpfr_clear(imag_hi)

      mpfr_clear(sqrt_lo)
      mpfr_clear(sqrt_delta)
      mpfr_clear(sqrt_lo2)
      mpfr_clear(sqrt_delta2)
      mpfr_clear(ang_delta)
      mpfr_clear(imag_delta)

      mpfr_clear(sqrt_min)
      mpfr_clear(sqrt_max)
      mpfr_clear(ang)
      mpfr_clear(imag_acc)
      mpfr_clear(imag_mean)
      mpfr_clear(interior_resolution_mpfr)

      mpq_clear(dx_q)
      mpq_clear(dy_q)
      mpq_clear(tmpq0)
      mpq_clear(tmpq1)


def JuliaComputation(object inp):
  """
  Cython/MPFR version of JuliaComputation.

  Python-level object fields are still accessed as Python objects, but the inner numeric
  operations are raw MPFR/GMP calls.
  """
  cdef:
    bint is_preprocess
    object img
    object p_bar
    bint has_procs
    int n_task
    Py_ssize_t width, height, depth
    Py_ssize_t px, py, px_count
    Py_ssize_t escaped_at
    int n_interior = 0
    double smooth_escape

    mpfr_prec_t prec

    mpfr_t *xs = NULL

    mpq_t dx_q
    mpq_t dy_q
    mpq_t tmpq0
    mpq_t tmpq1

    mpfr_t zero, sixteenth, fourth, half, one, two, four
    mpfr_t c_re, c_im
    mpfr_t img_y, img_y2
    mpfr_t zx, zy, zx2, zy2, mag_z2
    mpfr_t min_z2, max_z2
    mpfr_t tmp0, tmp1, tmp2
    mpfr_t mpfr_pi, mpfr_two_pi, max_iter_p_1
    mpfr_t max_lo, max_hi, min_lo, min_hi, ang_lo, ang_hi, imag_lo, imag_hi
    mpfr_t sqrt_lo, sqrt_delta, sqrt_lo2, sqrt_delta2, ang_delta, imag_delta
    mpfr_t sqrt_min, sqrt_max, ang, imag_acc, imag_mean
    mpfr_t interior_resolution_mpfr

    bint stats_max = False
    bint stats_min = False
    bint stats_ang = False
    bint stats_imag = False

    object set_points
    object dx_obj
    object dy_obj

  if inp.params.frm.fractal != frame.Fractal.JULIA:
    raise image.Error(f'Expected Julia computation, got {inp.params.frm.fractal}')

  is_preprocess = (
    inp.params.width == frame.MIN_IMAGE_SIZE and
    inp.params.height == frame.MIN_IMAGE_SIZE
  )

  img = image.Image(inp.params)

  width = inp.params.width
  height = inp.params.height
  depth = inp.params.depth
  set_points = inp.params.set_points

  mpq_init(dx_q)
  mpq_init(dy_q)
  mpq_init(tmpq0)
  mpq_init(tmpq1)

  dx_obj, dy_obj = inp.params.frm.size

  mpq_set(dx_q, MPQ(<mpq>dx_obj))
  mpq_set(dy_q, MPQ(<mpq>dy_obj))

  mpq_set_si(tmpq0, width - 1, 1)
  mpq_div(dx_q, dx_q, tmpq0)

  mpq_set_si(tmpq0, height - 1, 1)
  mpq_div(dy_q, dy_q, tmpq0)

  if dx_obj <= 0 or dy_obj <= 0:
    mpq_clear(dx_q)
    mpq_clear(dy_q)
    mpq_clear(tmpq0)
    mpq_clear(tmpq1)
    raise image.Error(f'frame must have positive area, got {dx_obj=} and {dy_obj=}')

  with inp.params.context:
    prec = inp.params.context.precision

    mpfr_init2(zero, prec)
    mpfr_init2(sixteenth, prec)
    mpfr_init2(fourth, prec)
    mpfr_init2(half, prec)
    mpfr_init2(one, prec)
    mpfr_init2(two, prec)
    mpfr_init2(four, prec)

    mpfr_init2(c_re, prec)
    mpfr_init2(c_im, prec)
    mpfr_init2(img_y, prec)
    mpfr_init2(img_y2, prec)

    mpfr_init2(zx, prec)
    mpfr_init2(zy, prec)
    mpfr_init2(zx2, prec)
    mpfr_init2(zy2, prec)
    mpfr_init2(mag_z2, prec)
    mpfr_init2(min_z2, prec)
    mpfr_init2(max_z2, prec)

    mpfr_init2(tmp0, prec)
    mpfr_init2(tmp1, prec)
    mpfr_init2(tmp2, prec)

    mpfr_init2(mpfr_pi, prec)
    mpfr_init2(mpfr_two_pi, prec)
    mpfr_init2(max_iter_p_1, prec)

    mpfr_init2(max_lo, prec)
    mpfr_init2(max_hi, prec)
    mpfr_init2(min_lo, prec)
    mpfr_init2(min_hi, prec)
    mpfr_init2(ang_lo, prec)
    mpfr_init2(ang_hi, prec)
    mpfr_init2(imag_lo, prec)
    mpfr_init2(imag_hi, prec)

    mpfr_init2(sqrt_lo, prec)
    mpfr_init2(sqrt_delta, prec)
    mpfr_init2(sqrt_lo2, prec)
    mpfr_init2(sqrt_delta2, prec)
    mpfr_init2(ang_delta, prec)
    mpfr_init2(imag_delta, prec)

    mpfr_init2(sqrt_min, prec)
    mpfr_init2(sqrt_max, prec)
    mpfr_init2(ang, prec)
    mpfr_init2(imag_acc, prec)
    mpfr_init2(imag_mean, prec)
    mpfr_init2(interior_resolution_mpfr, prec)

    try:
      mpfr_set_ui(zero, 0, MPFR_RNDN)
      mpfr_set_d(sixteenth, 0.0625, MPFR_RNDN)
      mpfr_set_d(fourth, 0.25, MPFR_RNDN)
      mpfr_set_d(half, 0.5, MPFR_RNDN)
      mpfr_set_ui(one, 1, MPFR_RNDN)
      mpfr_set_ui(two, 2, MPFR_RNDN)
      mpfr_set_ui(four, 4, MPFR_RNDN)
      mpfr_set(interior_resolution_mpfr, MPFR(<mpfr>frame.MPFR_SET_INTERIOR_INT_SPAN), MPFR_RNDN)

      mpfr_const_pi(mpfr_pi, MPFR_RNDN)
      mpfr_mul(mpfr_two_pi, two, mpfr_pi, MPFR_RNDN)

      mpfr_set_si(max_iter_p_1, depth, MPFR_RNDN)
      mpfr_add(max_iter_p_1, max_iter_p_1, one, MPFR_RNDN)

      mpfr_set(max_lo, four, MPFR_RNDN)
      mpfr_set(max_hi, zero, MPFR_RNDN)
      mpfr_set(min_lo, four, MPFR_RNDN)
      mpfr_set(min_hi, zero, MPFR_RNDN)
      mpfr_set(ang_lo, one, MPFR_RNDN)
      mpfr_set(ang_hi, zero, MPFR_RNDN)
      mpfr_set(imag_lo, one, MPFR_RNDN)
      mpfr_set(imag_hi, zero, MPFR_RNDN)

      mpfr_set(sqrt_lo, zero, MPFR_RNDN)
      mpfr_set(sqrt_delta, zero, MPFR_RNDN)
      mpfr_set(sqrt_lo2, zero, MPFR_RNDN)
      mpfr_set(sqrt_delta2, zero, MPFR_RNDN)
      mpfr_set(ang_delta, zero, MPFR_RNDN)
      mpfr_set(imag_delta, zero, MPFR_RNDN)

      # Julia fixed c-parameter.
      # point_re / point_im are frame coordinates, so they are mpq, not mpfr.
      mpfr_set_q(c_re, MPQ(<mpq>inp.params.frm.point_re), MPFR_RNDN)
      mpfr_set_q(c_im, MPQ(<mpq>inp.params.frm.point_im), MPFR_RNDN)

      if inp.stats is not None:
        if (
          inp.stats.max_lo is not None and
          inp.stats.max_hi is not None and
          inp.stats.max_hi > inp.stats.max_lo
        ):
          stats_max = True
          mpfr_sqrt(sqrt_lo, MPFR(<mpfr>inp.stats.max_lo), MPFR_RNDN)
          mpfr_sqrt(tmp0, MPFR(<mpfr>inp.stats.max_hi), MPFR_RNDN)
          mpfr_sub(sqrt_delta, tmp0, sqrt_lo, MPFR_RNDN)

        if (
          inp.stats.min_lo is not None and
          inp.stats.min_hi is not None and
          inp.stats.min_hi > inp.stats.min_lo
        ):
          stats_min = True
          mpfr_sqrt(sqrt_lo2, MPFR(<mpfr>inp.stats.min_lo), MPFR_RNDN)
          mpfr_sqrt(tmp0, MPFR(<mpfr>inp.stats.min_hi), MPFR_RNDN)
          mpfr_sub(sqrt_delta2, tmp0, sqrt_lo2, MPFR_RNDN)

        if (
          inp.stats.ang_lo is not None and
          inp.stats.ang_hi is not None and
          inp.stats.ang_hi > inp.stats.ang_lo
        ):
          stats_ang = True
          mpfr_sub(ang_delta, MPFR(<mpfr>inp.stats.ang_hi), MPFR(<mpfr>inp.stats.ang_lo), MPFR_RNDN)

        if (
          inp.stats.imag_lo is not None and
          inp.stats.imag_hi is not None and
          inp.stats.imag_hi > inp.stats.imag_lo
        ):
          stats_imag = True
          mpfr_sub(imag_delta, MPFR(<mpfr>inp.stats.imag_hi), MPFR(<mpfr>inp.stats.imag_lo), MPFR_RNDN)

      # xs[i] = mpfr(top_re + i * dx_q)
      xs = <mpfr_t *>malloc(width * sizeof(mpfr_t))
      if xs == NULL:
        raise MemoryError()

      for px in range(width):
        mpfr_init2(xs[px], prec)

        mpq_set_si(tmpq0, px, 1)
        mpq_mul(tmpq0, tmpq0, dx_q)

        mpq_set(tmpq1, MPQ(<mpq>inp.params.frm.top_re))
        mpq_add(tmpq1, tmpq1, tmpq0)

        mpfr_set_q(xs[px], tmpq1, MPFR_RNDN)

      has_procs = inp.total_tasks > 1
      n_task = inp.n_task - 1

      with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=TqdmExperimentalWarning)
        p_bar = tqdm.rich.tqdm(
          total=width * height,
          desc='Pre' if is_preprocess else 'Img',
          unit='px',
          dynamic_ncols=True,
          smoothing=0.1,
          colour='green',
          disable=not inp.progress_bar or (has_procs and n_task != 0),
        )

      px_count = -1

      for py in range(height):
        # img_y = mpfr(top_im - py * dy_q)
        mpq_set_si(tmpq0, py, 1)
        mpq_mul(tmpq0, tmpq0, dy_q)

        mpq_set(tmpq1, MPQ(<mpq>inp.params.frm.top_im))
        mpq_sub(tmpq1, tmpq1, tmpq0)

        mpfr_set_q(img_y, tmpq1, MPFR_RNDN)
        mpfr_sqr(img_y2, img_y, MPFR_RNDN)

        for px in range(width):
          px_count += 1

          if has_procs and (px_count % inp.total_tasks) != n_task:
            p_bar.update(1)
            continue

          # Julia starts each orbit at the pixel coordinate z0.
          mpfr_set(zx, xs[px], MPFR_RNDN)
          mpfr_set(zy, img_y, MPFR_RNDN)

          mpfr_set(min_z2, four, MPFR_RNDN)
          mpfr_set(max_z2, zero, MPFR_RNDN)
          mpfr_set(imag_acc, zero, MPFR_RNDN)

          # Fast exterior pre-check: |z0|^2 > 4 means escaped at iteration 0.
          mpfr_sqr(tmp0, zx, MPFR_RNDN)
          mpfr_add(tmp0, tmp0, img_y2, MPFR_RNDN)

          if mpfr_greater_p(tmp0, four):
            img.escape[px_count] = EncodeIntFloatTo64_c(0, 0.0)
            p_bar.update(1)
            continue

          escaped_at = 0
          smooth_escape = 0.0

          for escaped_at in range(depth):
            mpfr_sqr(zx2, zx, MPFR_RNDN)
            mpfr_sqr(zy2, zy, MPFR_RNDN)
            mpfr_add(mag_z2, zx2, zy2, MPFR_RNDN)

            if mpfr_greater_p(mag_z2, four):
              for _ in range(frame.SMOOTH_EXTRA_ITERS):
                escaped_at += 1

                # zy = 2 * zx * zy + c_im
                mpfr_mul(tmp0, zx, zy, MPFR_RNDN)
                mpfr_mul(tmp0, two, tmp0, MPFR_RNDN)
                mpfr_add(zy, tmp0, c_im, MPFR_RNDN)

                # zx = zx2 - zy2 + c_re
                mpfr_sub(tmp1, zx2, zy2, MPFR_RNDN)
                mpfr_add(zx, tmp1, c_re, MPFR_RNDN)

                mpfr_sqr(zx2, zx, MPFR_RNDN)
                mpfr_sqr(zy2, zy, MPFR_RNDN)

              mpfr_add(mag_z2, zx2, zy2, MPFR_RNDN)
              smooth_escape = smooth_escape_fraction(mag_z2, half, tmp0, tmp1)

              NormalizeSmoothEscape_c(&escaped_at, &smooth_escape)
              break

            if (
              set_points == frame.SetHighlightAlgorithm.IMAGINARY and
              mpfr_greater_p(mag_z2, zero)
            ):
              # imag_acc += zy2 / mag_z2
              mpfr_div(tmp0, zy2, mag_z2, MPFR_RNDN)
              mpfr_add(imag_acc, imag_acc, tmp0, MPFR_RNDN)

            # zy = 2 * zx * zy + c_im
            mpfr_mul(tmp0, zx, zy, MPFR_RNDN)
            mpfr_mul(tmp0, two, tmp0, MPFR_RNDN)
            mpfr_add(zy, tmp0, c_im, MPFR_RNDN)

            # zx = zx2 - zy2 + c_re
            mpfr_sub(tmp1, zx2, zy2, MPFR_RNDN)
            mpfr_add(zx, tmp1, c_re, MPFR_RNDN)

            if set_points == frame.SetHighlightAlgorithm.MIN:
              if mpfr_less_p(mag_z2, min_z2):
                mpfr_set(min_z2, mag_z2, MPFR_RNDN)
            elif set_points == frame.SetHighlightAlgorithm.MAX:
              if mpfr_greater_p(mag_z2, max_z2):
                mpfr_set(max_z2, mag_z2, MPFR_RNDN)

          else:
            if not (
              mpfr_greaterequal_p(max_z2, zero) and
              mpfr_less_p(max_z2, four)
            ):
              raise image.Error(
                f'Interior point exceeded max |z|^2 of 4, should never happen, '
                f'max_z2={GMPy_MPFR_From_mpfr(max_z2)}'
              )

            n_interior += 1

            if set_points is None:
              escaped_at = -frame.SET_INTERIOR_INT_MAX
              smooth_escape = 0.0

            elif set_points == frame.SetHighlightAlgorithm.MIN:
              if mpfr_less_p(min_z2, min_lo):
                mpfr_set(min_lo, min_z2, MPFR_RNDN)
              if mpfr_greater_p(min_z2, min_hi):
                mpfr_set(min_hi, min_z2, MPFR_RNDN)

              mpfr_sqrt(sqrt_min, min_z2, MPFR_RNDN)
              if stats_min:
                NormalizeSmoothSet_c(
                  sqrt_min, sqrt_lo2, sqrt_delta2,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )
              else:
                NormalizeSmoothSet_c(
                  sqrt_min, zero, MPFR(<mpfr>frame.MPFR_MAX_SET_Z),
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )

            elif set_points == frame.SetHighlightAlgorithm.MAX:
              if mpfr_less_p(max_z2, max_lo):
                mpfr_set(max_lo, max_z2, MPFR_RNDN)
              if mpfr_greater_p(max_z2, max_hi):
                mpfr_set(max_hi, max_z2, MPFR_RNDN)

              mpfr_sqrt(sqrt_max, max_z2, MPFR_RNDN)
              if stats_max:
                NormalizeSmoothSet_c(
                  sqrt_max, sqrt_lo, sqrt_delta,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )
              else:
                NormalizeSmoothSet_c(
                  sqrt_max, zero, MPFR(<mpfr>frame.MPFR_MAX_SET_Z),
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )

            elif set_points == frame.SetHighlightAlgorithm.ANGLE:
              # ang = atan2(zy, zx)
              # ang = (ang + pi) / (2*pi)
              mpfr_atan2(ang, zy, zx, MPFR_RNDN)
              mpfr_add(ang, ang, mpfr_pi, MPFR_RNDN)
              mpfr_div(ang, ang, mpfr_two_pi, MPFR_RNDN)

              if mpfr_less_p(ang, ang_lo):
                mpfr_set(ang_lo, ang, MPFR_RNDN)
              if mpfr_greater_p(ang, ang_hi):
                mpfr_set(ang_hi, ang, MPFR_RNDN)

              if stats_ang:
                NormalizeSmoothSet_c(
                  ang, MPFR(<mpfr>inp.stats.ang_lo), ang_delta,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )
              else:
                NormalizeSmoothSet_c(
                  ang, zero, one,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )

            elif set_points == frame.SetHighlightAlgorithm.IMAGINARY:
              # imag_mean = (imag_acc / max_iter_p_1) / frame.MPFR_MAX_SET_Z
              mpfr_div(imag_mean, imag_acc, max_iter_p_1, MPFR_RNDN)
              mpfr_div(imag_mean, imag_mean, MPFR(<mpfr>frame.MPFR_MAX_SET_Z), MPFR_RNDN)

              if mpfr_less_p(imag_mean, imag_lo):
                mpfr_set(imag_lo, imag_mean, MPFR_RNDN)
              if mpfr_greater_p(imag_mean, imag_hi):
                mpfr_set(imag_hi, imag_mean, MPFR_RNDN)

              if stats_imag:
                NormalizeSmoothSet_c(
                  imag_mean, MPFR(<mpfr>inp.stats.imag_lo), imag_delta,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )
              else:
                NormalizeSmoothSet_c(
                  imag_mean, zero, one,
                  tmp0, tmp1, tmp2, zero, one,
                  interior_resolution_mpfr,
                  frame.SET_INTERIOR_INT_MAX,
                  &escaped_at, &smooth_escape,
                )

            else:
              raise image.Error(f'Unknown fractal type {inp.params.set_points=}; should never happen')

          img.escape[px_count] = EncodeIntFloatTo64_c(<int>escaped_at, smooth_escape)
          p_bar.update(1)

      p_bar.close()

      img.stats = image.FractalStats(
        n_px=width * height,
        n_interior=n_interior,

        max_lo=GMPy_MPFR_From_mpfr(max_lo) if mpfr_greaterequal_p(max_hi, max_lo) else None,
        max_hi=GMPy_MPFR_From_mpfr(max_hi) if mpfr_greaterequal_p(max_hi, max_lo) else None,

        min_lo=GMPy_MPFR_From_mpfr(min_lo) if mpfr_greaterequal_p(min_hi, min_lo) else None,
        min_hi=GMPy_MPFR_From_mpfr(min_hi) if mpfr_greaterequal_p(min_hi, min_lo) else None,

        ang_lo=GMPy_MPFR_From_mpfr(ang_lo) if mpfr_greaterequal_p(ang_hi, ang_lo) else None,
        ang_hi=GMPy_MPFR_From_mpfr(ang_hi) if mpfr_greaterequal_p(ang_hi, ang_lo) else None,

        imag_lo=GMPy_MPFR_From_mpfr(imag_lo) if mpfr_greaterequal_p(imag_hi, imag_lo) else None,
        imag_hi=GMPy_MPFR_From_mpfr(imag_hi) if mpfr_greaterequal_p(imag_hi, imag_lo) else None,
      )

      return image.FractalTaskOutput(
        img=img,
        n_task=inp.n_task,
        total_tasks=inp.total_tasks,
      )

    finally:
      if xs != NULL:
        for px in range(width):
          mpfr_clear(xs[px])
        free(xs)

      mpfr_clear(zero)
      mpfr_clear(sixteenth)
      mpfr_clear(fourth)
      mpfr_clear(half)
      mpfr_clear(one)
      mpfr_clear(two)
      mpfr_clear(four)

      mpfr_clear(c_re)
      mpfr_clear(c_im)
      mpfr_clear(img_y)
      mpfr_clear(img_y2)

      mpfr_clear(zx)
      mpfr_clear(zy)
      mpfr_clear(zx2)
      mpfr_clear(zy2)
      mpfr_clear(mag_z2)
      mpfr_clear(min_z2)
      mpfr_clear(max_z2)

      mpfr_clear(tmp0)
      mpfr_clear(tmp1)
      mpfr_clear(tmp2)

      mpfr_clear(mpfr_pi)
      mpfr_clear(mpfr_two_pi)
      mpfr_clear(max_iter_p_1)

      mpfr_clear(max_lo)
      mpfr_clear(max_hi)
      mpfr_clear(min_lo)
      mpfr_clear(min_hi)
      mpfr_clear(ang_lo)
      mpfr_clear(ang_hi)
      mpfr_clear(imag_lo)
      mpfr_clear(imag_hi)

      mpfr_clear(sqrt_lo)
      mpfr_clear(sqrt_delta)
      mpfr_clear(sqrt_lo2)
      mpfr_clear(sqrt_delta2)
      mpfr_clear(ang_delta)
      mpfr_clear(imag_delta)

      mpfr_clear(sqrt_min)
      mpfr_clear(sqrt_max)
      mpfr_clear(ang)
      mpfr_clear(imag_acc)
      mpfr_clear(imag_mean)
      mpfr_clear(interior_resolution_mpfr)

      mpq_clear(dx_q)
      mpq_clear(dy_q)
      mpq_clear(tmpq0)
      mpq_clear(tmpq1)
