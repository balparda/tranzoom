# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
"""Image operations for Mandelbrot rendering."""

from __future__ import annotations

import enum


class Palette(enum.Enum):
  """Palette enum."""

  SAHARA = 'sahara'
  LAVA = 'lava'
  ELECTRIC = 'electric'
  SUNSET = 'sunset'
  AURORA = 'aurora'
  PLASMA = 'plasma'
  FOREST = 'forest'
  CORAL = 'coral'
  GOLD = 'gold'
  TOXIC = 'toxic'
  IRIS = 'iris'
  EMBER = 'ember'
  GRAYSCALE = 'grayscale'
  GRAYSCALE_REVERSE = 'rgrayscale'


DEFAULT_PALETTE: Palette = Palette.SAHARA
DEFAULT_SET_PALETTE: Palette = Palette.GRAYSCALE_REVERSE  # used for interior (set) points coloring

# Color palettes for exterior points. Each is a tuple of RGB color stops that are
# linearly interpolated and may be cycled on across the histogram-equalized
# escape-iteration range. Any number of stops is supported.
PALETTES: dict[Palette, tuple[tuple[int, int, int], ...]] = {
  # Classic 16-stop blue-to-yellow-to-brown gradient (original Mandelbrot color scheme)
  Palette.SAHARA: (
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
  Palette.ELECTRIC: (
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
  # 16-stop northern-lights aurora: near-black night sky → polar green aurora → brilliant white.
  # Ends in white for maximum contrast with the black set interior.
  Palette.AURORA: (
    (2, 2, 20),  # near-black night sky
    (5, 5, 45),  # dark midnight blue
    (5, 15, 60),  # deep navy
    (0, 35, 65),  # dark teal-navy
    (0, 65, 55),  # dark teal
    (0, 95, 45),  # dark green-teal
    (0, 130, 50),  # forest green
    (0, 170, 70),  # medium green
    (0, 205, 95),  # bright green
    (30, 230, 130),  # emerald
    (80, 245, 170),  # light emerald
    (145, 255, 210),  # seafoam green
    (200, 255, 235),  # mint
    (230, 255, 248),  # pale mint
    (245, 255, 252),  # near-white mint
    (255, 255, 255),  # white (near-boundary; high contrast with black set interior)
  ),
  # 16-stop high-energy plasma: near-black void → deep purple → hot magenta → white-hot.
  # Ends in white for maximum contrast with the black set interior.
  Palette.PLASMA: (
    (3, 0, 10),  # near-black void
    (15, 0, 35),  # deep dark purple
    (40, 0, 80),  # dark purple
    (80, 0, 130),  # purple
    (125, 0, 175),  # bright purple
    (165, 0, 205),  # violet
    (200, 0, 210),  # purple-magenta
    (230, 10, 200),  # magenta
    (250, 30, 180),  # hot pink
    (255, 60, 150),  # bright pink
    (255, 100, 120),  # salmon pink
    (255, 150, 100),  # peach
    (255, 200, 120),  # light amber
    (255, 235, 180),  # cream
    (255, 250, 230),  # near-white warm
    (255, 255, 255),  # white (near-boundary; high contrast with black set interior)
  ),
  # 16-stop deep forest: near-black soil → mossy dark green → acid lime-yellow.
  # Ends in bright lime-yellow for high contrast with the black set interior.
  Palette.FOREST: (
    (10, 5, 0),  # near-black dark soil
    (30, 15, 0),  # dark brown soil
    (55, 30, 0),  # dark brown
    (70, 45, 5),  # brown
    (60, 55, 5),  # olive brown
    (40, 65, 5),  # dark olive
    (20, 80, 10),  # dark olive green
    (10, 100, 15),  # forest green
    (5, 125, 20),  # medium forest green
    (15, 155, 25),  # green
    (40, 185, 30),  # bright green
    (80, 210, 35),  # light green
    (130, 230, 40),  # yellow-green
    (175, 245, 50),  # lime green
    (215, 255, 80),  # bright lime
    (240, 255, 120),  # lime-yellow (near-boundary; high contrast with black set interior)
  ),
  # 16-stop coral reef: near-black abyss → teal → coral → bright pale pink.
  # Ends in pale pink for contrast with the black set interior.
  Palette.CORAL: (
    (0, 5, 15),  # near-black abyss
    (0, 20, 40),  # very dark teal
    (0, 45, 65),  # dark teal
    (0, 75, 85),  # teal
    (0, 110, 100),  # medium teal
    (10, 140, 110),  # light teal
    (30, 165, 115),  # seafoam teal
    (70, 185, 120),  # seafoam
    (120, 200, 130),  # light seafoam
    (170, 210, 140),  # sage
    (210, 200, 140),  # warm tan
    (240, 175, 120),  # light coral
    (255, 145, 100),  # coral
    (255, 110, 90),  # deep coral
    (255, 165, 165),  # light pink
    (255, 220, 225),  # pale pink (near-boundary; high contrast with black set interior)
  ),
  # 16-stop molten metal: near-black iron → bronze → gold → brilliant white-gold.
  # Ends in white for maximum contrast with the black set interior.
  Palette.GOLD: (
    (5, 3, 0),  # near-black
    (20, 12, 0),  # very dark brown
    (45, 25, 0),  # dark brown
    (80, 45, 0),  # brown
    (120, 65, 0),  # dark amber
    (160, 90, 0),  # amber
    (200, 120, 0),  # golden amber
    (230, 155, 0),  # gold
    (250, 190, 0),  # bright gold
    (255, 215, 30),  # yellow-gold
    (255, 235, 80),  # golden yellow
    (255, 248, 140),  # pale yellow
    (255, 253, 195),  # very pale yellow
    (255, 255, 230),  # near-white yellow
    (255, 255, 250),  # near-white
    (255, 255, 255),  # white (near-boundary; high contrast with black set interior)
  ),
  # 16-stop biohazard: near-black swamp → murky dark green → acid yellow-green.
  # Ends in bright acid yellow for maximum contrast with the black set interior.
  Palette.TOXIC: (
    (0, 8, 0),  # near-black
    (5, 20, 0),  # very dark green
    (10, 40, 0),  # dark green
    (10, 65, 0),  # dark olive green
    (15, 90, 0),  # dark green
    (25, 115, 0),  # medium-dark green
    (40, 140, 0),  # medium green
    (60, 165, 0),  # green
    (90, 185, 0),  # bright green
    (125, 200, 0),  # yellow-green
    (160, 215, 0),  # lime
    (195, 230, 0),  # lime-yellow
    (220, 240, 0),  # bright lime
    (240, 250, 0),  # near-yellow
    (250, 255, 30),  # bright yellow
    (255, 255, 80),  # acid yellow (near-boundary; high contrast with black set interior)
  ),
  # 16-stop iris flower: near-black indigo → deep violet → bright lavender → white.
  # Ends in white for maximum contrast with the black set interior.
  Palette.IRIS: (
    (5, 0, 20),  # near-black indigo
    (15, 0, 55),  # deep indigo
    (35, 0, 100),  # indigo
    (65, 0, 150),  # blue-violet
    (100, 10, 190),  # violet-blue
    (135, 30, 220),  # violet
    (165, 60, 235),  # medium violet
    (190, 95, 245),  # light violet
    (210, 130, 250),  # lavender
    (225, 160, 255),  # light lavender
    (235, 190, 255),  # pale lavender
    (242, 215, 255),  # very pale lavender
    (248, 235, 255),  # near-white lavender
    (252, 248, 255),  # almost-white lavender
    (255, 253, 255),  # near-white
    (255, 255, 255),  # white (near-boundary; high contrast with black set interior)
  ),
  # 16-stop dying ember: cold charcoal ash → smoldering red → incandescent near-white.
  # Ends in near-white for high contrast with the black set interior.
  Palette.EMBER: (
    (8, 6, 5),  # near-black ash
    (25, 15, 10),  # dark charcoal
    (55, 28, 10),  # dark brown
    (95, 40, 5),  # dark reddish-brown
    (140, 45, 0),  # deep red-brown
    (185, 40, 0),  # dark red
    (220, 50, 0),  # red
    (245, 75, 0),  # red-orange
    (255, 110, 0),  # orange
    (255, 150, 0),  # bright orange
    (255, 185, 0),  # amber-orange
    (255, 215, 10),  # amber
    (255, 235, 50),  # golden yellow
    (255, 248, 120),  # light yellow
    (255, 253, 200),  # near-white yellow
    (255, 255, 240),  # incandescent white (near-boundary; high contrast with black set interior)
  ),
  # 8-stop smooth grayscale: white (deep interior, low |z|) → black (near boundary, high |z|);
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
