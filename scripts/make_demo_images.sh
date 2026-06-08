#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
#
# make_examples.sh — Generate a sequence of example Mandelbrot renders at increasing zoom depth.
#
# Run from the tranzoom repo root: bash scripts/make_examples.sh
# Output: PNG files with pinned names in tests/data/images/; these are used in the docs and tests,
# so they are committed to git, and will change when code changes, so we don't want to be depending
# on the hashes or dates, so we use --no-date and --no-hash to get stable file names. We also use
# flags  --no-db and --force to avoid any caching or database interactions on the critical ones:
# it is tempting to use caching for all, but they need to be regenerated even, or especially, when
# the math changes, so we want to be sure they are always regenerated.

# Each command prints before it runs (set -x xtrace) so output is self-documenting
set -euxo pipefail

####################################################################################################
# Demo Images (don't care for stability: only re-generate when visuals change enough for a human to notice)
####################################################################################################

# Render the Full / Default Mandelbrot set
poetry run tranz --no-db --force --no-date --no-hash --prefix "demo-mandel-whole-set" -o tests/data/images image mandel
poetry run tranz --no-db --force --set imaginary --palette "rgrayscale" --set-palette "lava" --no-date --no-hash --prefix "demo-mandel-whole-set-spicy" -o tests/data/images image mandel

# Render Seahorse
poetry run tranz --no-db --force --no-date --no-hash --prefix "demo-mandel-seahorse" -o tests/data/images image mandel " -0.74303" "0.126433" "0.01611"

# Render Seahorse Tail all palettes (but original is above, already done)
for palette in sahara lava electric sunset aurora plasma forest coral gold toxic iris ember rgrayscale grayscale; do
  poetry run tranz --no-db --force --palette "${palette}" --no-date --no-hash --prefix "demo-mandel-seahorse-tail-${palette}" -o tests/data/images image -w 512 -h 512 mandel " -0.7436499" "0.13188204" "0.00073801"
done

# Render MP4 Animated Seahorse Tail video
poetry run tranz --no-db --force --no-date --no-hash --prefix "demo-mandel-seahorse-tail-video" -o tests/data/images zoom -s 512 auto " -5578776469/7500000000" "8244620127/62500000000" "0.00073801" "0.00073801" "1" --fps 10 --duration 4 --anim mp4

# Render Julia Suzana
poetry run tranz --no-db --force --palette "electric" --no-date --no-hash --prefix "demo-julia-suzana" -o tests/data/images image -s 1024 julia

# generate the 16 images in the POWERS OF 1000 zoom sequence

CX=" -0.7436438870371587047521915061147740000000008"
CY="0.13182590420531197049313205638514950000008"

for n in $(seq 1 16); do
    prefix=$(printf "demo-mandel-zoom-%02d" "$n")
    if [ "$n" -eq 1 ]; then
        zoom="2.5"  # first one is "2.5"
    else
        zoom=$(printf "0.%0*d25" "$((3 * n - 4))" 0)  # then "0.0025", "0.0000025", etc.
    fi
    poetry run tranz --no-db --force --no-date --no-hash --prefix "$prefix" -o tests/data/images image -w 512 -h 512 --mark "($CX,$CY)" mandel "$CX" "$CY" "$zoom"
done
