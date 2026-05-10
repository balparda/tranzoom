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
poetry run mandel --no-date --no-hash --prefix "demo-mandel-whole-set" -o tests/data/images gen

# Render Seahorse
poetry run mandel --no-date --no-hash --prefix "demo-mandel-seahorse" -o tests/data/images gen " -0.74303" "0.126433" "0.01611"

# Render Seahorse Tail
poetry run mandel --no-date --no-hash --prefix "demo-mandel-seahorse-tail" -o tests/data/images gen " -0.7436499" "0.13188204" "0.00073801" --palette "blue-to-yellow-to-brown"
poetry run mandel -w 512 -h 512 --no-date --no-hash --prefix "demo-mandel-seahorse-tail-byb" -o tests/data/images gen " -0.7436499" "0.13188204" "0.00073801" --palette "blue-to-yellow-to-brown"
poetry run mandel -w 512 -h 512 --no-date --no-hash --prefix "demo-mandel-seahorse-tail-lava" -o tests/data/images gen " -0.7436499" "0.13188204" "0.00073801" --palette "lava"
poetry run mandel -w 512 -h 512 --no-date --no-hash --prefix "demo-mandel-seahorse-tail-ocean" -o tests/data/images gen " -0.7436499" "0.13188204" "0.00073801" --palette "electric-ocean"
poetry run mandel -w 512 -h 512 --no-date --no-hash --prefix "demo-mandel-seahorse-tail-sunset" -o tests/data/images gen " -0.7436499" "0.13188204" "0.00073801" --palette "sunset"

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
    poetry run mandel -w 512 -h 512 --no-date --no-hash --prefix "$prefix" -o tests/data/images gen "$CX" "$CY" "$zoom"
done
