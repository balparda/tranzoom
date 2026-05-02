# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Business logic examples."""

from __future__ import annotations

import pathlib

import fractalshades.colors
import fractalshades.models
from fractalshades import postproc
from fractalshades.colors import layers


def render_mandelbrot(
  *,
  out_dir: str | pathlib.Path,
  x: str,
  y: str,
  dx: str,
  precision: int,
  width: int = 1920,
  height: int = 1080,
  max_iter: int = 100_000,
) -> None:
  """Render one arbitrary-precision Mandelbrot image.

  x, y:
    Center coordinate, as decimal strings.

  dx:
    Width of the viewport in Mandelbrot-plane units, as a decimal string.
    For deep zooms, keep this as a string, e.g. '1e-80'.

  precision:
    Decimal precision used by Fractalshades for the deep-zoom reference
    orbit. Rough rule: use a bit more than the number of decimal places
    implied by dx.

  width, height:
    Output image pixel dimensions.

  Output:
    Fractalshades writes image files into out_dir.
  """
  out_dir = pathlib.Path(out_dir)
  out_dir.mkdir(parents=True, exist_ok=True)

  fractalshades.settings.enable_multithreading = True
  fractalshades.settings.inspect_calc = True

  calc_name = 'mandelbrot'
  xy_ratio: float = width / height

  # Built-in palette. Replace this later with your own Fractal_colormap.
  colormap = fractalshades.colors.cmap_register['classic']

  # This is the arbitrary-precision Mandelbrot implementation.
  fractal_obj = fractalshades.models.Perturbation_mandelbrot(str(out_dir))

  # Define the viewport.
  # Fractalshades' examples pass x/y/dx as strings for deep zooms.
  fractal_obj.zoom(
    precision=precision,
    x=x,
    y=y,
    dx=dx,
    nx=width,
    xy_ratio=xy_ratio,
    theta_deg=0.0,
    projection='cartesian',
  )

  # Run the Mandelbrot divergence calculation.
  fractal_obj.calc_std_div(
    calc_name=calc_name,
    subset=None,
    max_iter=max_iter,
    M_divergence=1.0e3,
    epsilon_stationnary=1.0e-3,
    BLA_eps=1.0e-6,
    interior_detect=False,
    calc_orbit=False,
  )

  # Convert raw calculation fields into something colorable.
  pp = postproc.Postproc_batch(fractal_obj, calc_name)
  pp.add_postproc('cont_iter', postproc.Continuous_iter_pp())
  pp.add_postproc('interior', postproc.Raw_pp('stop_reason', func='x != 1.'))

  plotter = fractalshades.Fractal_plotter(pp)

  # Black interior mask.
  plotter.add_layer(layers.Bool_layer('interior', output=False))

  # Smooth exterior coloring.
  plotter.add_layer(
    layers.Color_layer(
      'cont_iter',
      func='np.log(x)',
      colormap=colormap,
      probes_z=[1.0, 10.0],
      output=True,
    )
  )

  plotter['cont_iter'].set_mask(
    plotter['interior'],
    mask_color=(0.0, 0.0, 0.0),
  )

  plotter.plot()
