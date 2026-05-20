#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0
#
# make_examples.sh — Generate a sequence of example Mandelbrot renders at increasing zoom depth.
#
# Run from the tranzoom repo root: bash scripts/make_examples.sh
# Output: PNG files with pinned names in tests/data/images/; these are used in the docs and tests,
# so they are committed to git, and will change when code changes, so we don't want to be depending
# on the hashes or dates, so we use --no-date and --no-hash to get stable file names

# Each command prints before it runs (set -x xtrace) so output is self-documenting
set -euxo pipefail

# Render the Full / Default Mandelbrot set
poetry run tranz --no-date --no-hash --prefix "demo-mandel-whole-set" -o tests/data/images image mandel
poetry run tranz --set imaginary --palette "rgrayscale" --set-palette "lava" --no-date --no-hash --prefix "demo-mandel-whole-set-spicy" -o tests/data/images image mandel

# Render Seahorse
poetry run tranz --no-date --no-hash --prefix "demo-mandel-seahorse" -o tests/data/images image mandel " -0.74303" "0.126433" "0.01611"

# Render Seahorse Tail original and all palettes
poetry run tranz --set imaginary --no-date --no-hash --prefix "demo-mandel-seahorse-tail" -o tests/data/images image mandel " -0.7436499" "0.13188204" "0.00073801"
poetry run tranz --set imaginary --no-date --no-hash --prefix "demo-mandel-seahorse-tail-byb" -o tests/data/images --palette "blue-to-yellow-to-brown" image -w 512 -h 512 mandel " -0.7436499" "0.13188204" "0.00073801"
poetry run tranz --set imaginary --no-date --no-hash --prefix "demo-mandel-seahorse-tail-lava" -o tests/data/images --palette "lava" image -w 512 -h 512 mandel " -0.7436499" "0.13188204" "0.00073801"
poetry run tranz --set imaginary --no-date --no-hash --prefix "demo-mandel-seahorse-tail-ocean" -o tests/data/images --palette "electric-ocean" image -w 512 -h 512 mandel " -0.7436499" "0.13188204" "0.00073801"
poetry run tranz --set imaginary --no-date --no-hash --prefix "demo-mandel-seahorse-tail-sunset" -o tests/data/images --palette "sunset" image -w 512 -h 512 mandel " -0.7436499" "0.13188204" "0.00073801"

# Render Animated Seahorse Tail zoom
poetry run tranz --no-date --no-hash --prefix "demo-mandel-seahorse-tail-anim" -o tests/data/images zoom -s 220 auto " -5578776469/7500000000" "8244620127/62500000000" "0.00073801" "0.00073801" "1" --fps 10 --duration 4

# Render Julia Suzana
poetry run tranz --no-date --no-hash --prefix "demo-julia-suzana" -o tests/data/images --palette "electric-ocean" image -s 1024 julia

# Render Julia Suzana Wave
poetry run tranz --set max --no-date --no-hash --prefix "demo-julia-suzana-wave" -o tests/data/images --palette "electric-ocean" --set-palette sunset image -s 512 julia "13667/50000" "371/50000" " -313420497/429687500" "0.6567" "0.00544" "0.004"

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
    poetry run tranz --set imaginary --no-date --no-hash --prefix "$prefix" -o tests/data/images image -w 512 -h 512 --mark "($CX,$CY)" mandel "$CX" "$CY" "$zoom"
done
