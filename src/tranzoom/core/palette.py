# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Image operations for Mandelbrot rendering."""

from __future__ import annotations

import enum


class Palette(enum.Enum):
  """Palette enum."""

  BYB = 'blue-to-yellow-to-brown'
  LAVA = 'lava'
  OCEAN = 'electric-ocean'
  SUNSET = 'sunset'
  GRAYSCALE = 'grayscale'
  GRAYSCALE_REVERSE = 'rgrayscale'


DEFAULT_PALETTE: Palette = Palette.BYB
DEFAULT_SET_PALETTE: Palette = Palette.GRAYSCALE_REVERSE  # used for interior (set) points coloring

# how many times to cycle through the palette across the histogram-equalized range;
# more cycles = tighter, more frequent color banding; 3 is a visually balanced default
PALETTE_CYCLES: int = 3
# for the interior (Set) palette we cycle only once: the full gradient runs exactly once across
# the histogram-equalized |z| range, keeping the gradient predictable and avoiding extra banding
SET_PALETTE_CYCLES: int = 1

# Color palettes for exterior points. Each is a tuple of RGB color stops that are
# linearly interpolated and cycled PALETTE_CYCLES times across the histogram-equalized
# escape-iteration range. Any number of stops is supported.
PALETTES: dict[Palette, tuple[tuple[int, int, int], ...]] = {
  # Classic 16-stop blue-to-yellow-to-brown gradient (original Mandelbrot color scheme)
  Palette.BYB: (
    (66, 30, 15),  # dark reddish-brown
    (25, 7, 26),  # dark violet
    (9, 1, 47),  # dark blue
    (4, 4, 73),  # deep blue
    (0, 7, 100),  # deep blue
    (12, 44, 138),  # blue
    (24, 82, 177),  # blue
    (57, 125, 209),  # light blue
    (134, 181, 229),  # very light blue
    (211, 236, 248),  # near-white blue
    (241, 233, 191),  # pale yellow
    (248, 201, 95),  # yellow
    (255, 170, 0),  # gold / orange
    (204, 128, 0),  # dark orange
    (153, 87, 0),  # brown
    (106, 52, 3),  # dark brown
  ),
  # 16-stop volcanic lava gradient: deep underground → incandescent white → cooling embers
  Palette.LAVA: (
    (5, 0, 20),  # deep black-violet (underground shadow)
    (30, 0, 10),  # near-black deep red (magma depth)
    (80, 0, 0),  # dark blood red
    (140, 10, 0),  # deep red (magma)
    (195, 25, 0),  # bright red
    (230, 55, 0),  # red-orange (lava surface)
    (250, 90, 0),  # orange
    (255, 130, 0),  # bright orange
    (255, 170, 0),  # amber
    (255, 210, 20),  # golden yellow
    (255, 240, 80),  # yellow
    (255, 255, 160),  # pale yellow
    (255, 255, 235),  # near-white incandescent
    (255, 230, 180),  # warm cream (beginning to cool)
    (210, 120, 30),  # dark orange (cooling lava)
    (100, 25, 5),  # dark ember (cycling back)
  ),
  # 32-stop electric ocean: abyss → cyan → seafoam → deep violet → magenta → lavender
  Palette.OCEAN: (
    (0, 5, 30),  # abyss (nearly black navy)
    (0, 15, 65),  # deep navy
    (0, 35, 105),  # dark ocean blue
    (0, 65, 145),  # ocean blue
    (0, 100, 180),  # medium blue
    (0, 140, 210),  # clear blue
    (0, 175, 230),  # bright blue
    (0, 210, 240),  # electric blue
    (30, 235, 245),  # cyan
    (100, 250, 250),  # bright cyan
    (170, 255, 250),  # light teal
    (215, 255, 240),  # pale seafoam
    (190, 245, 200),  # seafoam
    (130, 225, 155),  # light teal green
    (60, 200, 110),  # teal green
    (10, 165, 75),  # dark teal
    (0, 120, 65),  # deep teal
    (0, 80, 80),  # dark teal-blue
    (0, 45, 90),  # dark navy
    (10, 25, 110),  # dark blue-violet
    (40, 10, 140),  # deep violet
    (85, 0, 160),  # violet
    (135, 0, 175),  # bright violet
    (185, 10, 185),  # magenta-violet
    (225, 40, 200),  # electric magenta
    (250, 80, 210),  # bright magenta
    (255, 130, 220),  # pink-magenta
    (255, 175, 230),  # light pink
    (255, 215, 245),  # pale pink
    (240, 235, 255),  # lavender white
    (210, 215, 255),  # pale periwinkle
    (130, 155, 255),  # periwinkle (wraps back toward blue)
  ),
  # 32-stop sunset: indigo night → purple → violet → salmon → amber → cream → wine → indigo
  Palette.SUNSET: (
    (10, 5, 45),  # deep indigo night
    (25, 10, 80),  # dark indigo
    (50, 15, 110),  # indigo
    (85, 20, 140),  # purple-indigo
    (120, 25, 155),  # purple
    (155, 35, 155),  # violet-purple
    (185, 50, 145),  # warm violet
    (215, 70, 125),  # pink-violet
    (235, 90, 100),  # warm pink
    (250, 115, 75),  # salmon
    (255, 140, 50),  # orange-salmon
    (255, 165, 30),  # bright orange
    (255, 185, 15),  # amber-orange
    (255, 205, 5),  # amber
    (255, 225, 0),  # golden yellow
    (255, 240, 30),  # bright yellow
    (255, 250, 90),  # pale yellow
    (255, 255, 160),  # near-white yellow
    (255, 245, 210),  # cream
    (255, 225, 175),  # warm cream
    (255, 200, 135),  # peach
    (255, 170, 100),  # light salmon
    (245, 140, 80),  # salmon-orange
    (225, 110, 65),  # dark salmon
    (195, 80, 55),  # dark orange-red
    (160, 55, 55),  # dark red
    (125, 35, 65),  # wine
    (90, 20, 80),  # dark wine-purple
    (60, 12, 90),  # dark purple
    (38, 8, 75),  # deep violet
    (22, 5, 60),  # near-dark indigo
    (13, 3, 50),  # almost black indigo (wraps back to start)
  ),
  # 8-stop smooth grayscale: white (deep interior, low |z|) → black (near boundary, high |z|);
  # cycles only once (SET_PALETTE_CYCLES=1) so the full gradient runs across the Set interior;
  # black near the boundary provides contrast with exterior colors; this is the DEFAULT_SET_PALETTE
  Palette.GRAYSCALE_REVERSE: (
    (255, 255, 255),  # white (deepest interior; far from boundary, low |z| magnitude)
    (240, 240, 240),  # near-white
    (210, 210, 210),  # light gray
    (168, 168, 168),  # medium-light gray
    (120, 120, 120),  # medium-dark gray
    (72, 72, 72),  # dark gray
    (32, 32, 32),  # very dark gray
    (0, 0, 0),  # black (near-boundary, high |z| magnitude)
  ),
  # 8-stop smooth grayscale: reverse of the above
  # black (deep interior, low |z|) → white (near boundary, high |z|)
  Palette.GRAYSCALE: (
    (0, 0, 0),  # black (deepest interior; far from boundary, low |z| magnitude)
    (32, 32, 32),  # very dark gray
    (72, 72, 72),  # dark gray
    (120, 120, 120),  # medium-dark gray
    (168, 168, 168),  # medium-light gray
    (210, 210, 210),  # light gray
    (240, 240, 240),  # near-white
    (255, 255, 255),  # white (near-boundary, high |z| magnitude)
  ),
}
