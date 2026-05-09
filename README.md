<!-- SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# tranZoom

Fractal manipulation with LLMs

- **Primary use case:** Render ultra-deep Mandelbrot fractal images with arbitrary precision, and (planned) use AI/LLMs to guide fractal zoom sequences
- **Works with:** Local filesystem (PNG output), complex-plane coordinates, AI models (future)
- **Status:** Early / experimental — core fractal engine is functional; AI guidance is planned
- **License:** Apache-2.0

**tranZoom** is a Python CLI tool for rendering the Mandelbrot set at virtually unlimited zoom depth using arbitrary-precision arithmetic (`gmpy2`). The goal is to be able to zoom so deep that standard double-precision floating point becomes meaningless — tranZoom automatically computes the required precision and renders faithfully at any scale. The long-term vision is to integrate with LLMs (via the `transai` library) to intelligently select and navigate interesting regions of the fractal automatically.

Since version 1.0.0 it is a PyPI package: <https://pypi.org/project/tranzoom/>

Built with:

- **Python 3.12+** with **Poetry** for dependency management
- **gmpy2** for arbitrary-precision (`mpq`/`mpfr`) complex-plane arithmetic
- **Pillow** for PNG image output
- **tqdm** for progress bars during rendering
- **transai** as the foundation for future AI/LLM integration
- **Typer** + **Rich** for the CLI and terminal output
- **Transcrypto** for CLI boilerplate, logging, hashing, and config management
- **Ruff**, **MyPy**, **Pyright**, **typeguard**, **pre-commit**, **GitHub Actions** for quality and CI

## Table of contents

- [tranZoom](#tranzoom)
  - [Table of contents](#table-of-contents)
  - [License](#license)
    - [Third-party notices](#third-party-notices)
    - [Contributions and inbound licensing](#contributions-and-inbound-licensing)
  - [Installation](#installation)
    - [Supported platforms](#supported-platforms)
    - [Known dependencies (Prerequisites)](#known-dependencies-prerequisites)
  - [Context / Problem Space](#context--problem-space)
    - [What this tool is](#what-this-tool-is)
    - [What this tool is not](#what-this-tool-is-not)
    - [Key concepts and terminology](#key-concepts-and-terminology)
    - [Inputs and outputs](#inputs-and-outputs)
      - [Inputs](#inputs)
      - [Outputs](#outputs)
  - [CLI Interface](#cli-interface)
    - [Quick start](#quick-start)
    - [Command structure](#command-structure)
    - [Global flags](#global-flags)
    - [CLI Commands Documentation](#cli-commands-documentation)
    - [`zoom image` — Render a Mandelbrot image](#zoom-image--render-a-mandelbrot-image)
    - [Comprehensive example images and zooms](#comprehensive-example-images-and-zooms)
      - [Full / Default (×1, 80 bits)](#full--default-1-80-bits)
      - [Seahorse (×155, 83 bits)](#seahorse-155-83-bits)
      - [Seahorse Tail (×3k, 88 bits)](#seahorse-tail-3k-88-bits)
      - [Powers of 1000](#powers-of-1000)
    - [Configuration](#configuration)
    - [Color and formatting](#color-and-formatting)
    - [Exit codes](#exit-codes)
  - [Project Design](#project-design)
    - [Modules / packages](#modules--packages)
    - [Performance characteristics](#performance-characteristics)
  - [Development Instructions](#development-instructions)
    - [File structure](#file-structure)
    - [Development Setup](#development-setup)
      - [Install Python](#install-python)
      - [Install Poetry (recommended: `pipx`)](#install-poetry-recommended-pipx)
      - [Make sure `.venv` is local](#make-sure-venv-is-local)
      - [Get the repository](#get-the-repository)
      - [Create environment and install dependencies](#create-environment-and-install-dependencies)
      - [Optional: VSCode setup](#optional-vscode-setup)
    - [Build](#build)
    - [Run locally](#run-locally)
    - [Testing](#testing)
      - [Unit tests / Coverage](#unit-tests--coverage)
      - [Instrumenting your code](#instrumenting-your-code)
      - [Integration / e2e tests](#integration--e2e-tests)
    - [Linting / formatting / static analysis](#linting--formatting--static-analysis)
      - [Type checking](#type-checking)
    - [Documentation updates](#documentation-updates)
    - [Versioning and releases](#versioning-and-releases)
      - [Versioning scheme](#versioning-scheme)
      - [Updating versions](#updating-versions)
        - [Bump project version (patch/minor/major)](#bump-project-version-patchminormajor)
        - [Update dependency versions](#update-dependency-versions)
        - [Exporting the `requirements.txt` file](#exporting-the-requirementstxt-file)
        - [CI and docs](#ci-and-docs)
        - [Git tag and commit](#git-tag-and-commit)
        - [Publish to PyPI](#publish-to-pypi)
  - [Security](#security)
  - [Troubleshooting](#troubleshooting)
    - [Enable debug output](#enable-debug-output)
    - [`gmpy2` installation issues](#gmpy2-installation-issues)
    - [Rendering is very slow](#rendering-is-very-slow)

## License

Copyright 2026 Daniel Balparda <balparda@github.com> & Bella Keri <BellaKeri@github.com>

Licensed under the **Apache License, Version 2.0** (the "License"); you may not use this file except in compliance with the License. You may obtain a [copy of the License here](http://www.apache.org/licenses/LICENSE-2.0).

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

### Third-party notices

This project includes or depends on third-party software (see `requirements.txt` and `pyproject.toml`). Key dependencies include:

- [gmpy2](https://gmpy2.readthedocs.io/) — Apache-2.0 compatible
- [Pillow](https://python-pillow.github.io/) — HPND license
- [tqdm](https://github.com/tqdm/tqdm) — MPL-2.0 / MIT
- [transai](https://github.com/balparda/transai) — Apache-2.0
- [transcrypto](https://github.com/balparda/transcrypto) — Apache-2.0

### Contributions and inbound licensing

Contributions are accepted under the Apache-2.0 license (same as project).

## Installation

To install from PyPI:

```sh
pip3 install tranzoom
```

Or install from the repository for development (see [Development Setup](#development-setup)).

### Supported platforms

- OS: Linux, macOS
- Architectures: x86_64, arm64
- Python: 3.12, 3.13, 3.14

### Known dependencies (Prerequisites)

- **[python 3.12+](https://python.org/)** — [documentation](https://docs.python.org/3.12/)
- **[gmpy2 2.3+](https://pypi.org/project/gmpy2/)** — Arbitrary-precision arithmetic using GMP/MPFR/MPC — [documentation](https://gmpy2.readthedocs.io/en/latest/)
- **[Pillow 12+](https://pypi.org/project/Pillow/)** — PNG image generation — [documentation](https://pillow.readthedocs.io/)
- **[tqdm 4.67+](https://pypi.org/project/tqdm/)** — Progress bars — [documentation](https://tqdm.github.io/)
- **[rich 14.2+](https://pypi.org/project/rich/)** — Terminal formatting — [documentation](https://rich.readthedocs.io/en/latest/)
- **[typer 0.21+](https://pypi.org/project/typer/)** — CLI parser — [documentation](https://typer.tiangolo.com/)
- **[transai 1.2+](https://pypi.org/project/transai/)** — AI integration foundation — [documentation](https://github.com/balparda/transai)
- **[transcrypto 2.1+](https://pypi.org/project/transcrypto/)** — CLI utilities, logging, hashing, config — [documentation](https://github.com/balparda/transcrypto)

## Context / Problem Space

### What this tool is

tranZoom is a command-line fractal renderer focused on extreme zoom depth. Standard double-precision (`float64`) floating point has only about 15–16 significant decimal digits, so any zoom below roughly 1e-14 of the full Mandelbrot set will produce incorrect images due to precision loss. tranZoom uses `gmpy2.mpq` (exact rational arithmetic) to represent frame coordinates and `gmpy2.mpfr` (arbitrary-precision floating point) for the escape-time computations, automatically determining how many bits of precision are needed for any given zoom level.

The long-term vision is to use LLMs to autonomously guide the zoom — identifying interesting regions, proposing successive frames, and building navigated zoom sequences without manual coordinate discovery.

### What this tool is not

- Not a real-time / interactive fractal explorer (rendering is intentionally CPU-intensive for correctness at depth)
- Not limited to a fixed precision (unlike most other fractal tools, which cap at `float64`)
- Not yet AI-guided (that is the planned future direction)

### Key concepts and terminology

- **Frame**: A rectangular region of the complex plane, defined by two corners or a center + width. Stored as `gmpy2.mpq` (exact rationals) to avoid any accumulation of rounding error in coordinates.
- **Precision**: The number of bits of `mpfr` floating-point precision used for escape-time iteration. Computed automatically from the frame size; never needs to be set manually.
- **Magnification**: Ratio of the default full-set frame area to the current frame area. 1× = full set; 1G× = zoomed in one billion times.
- **Escape-time iteration**: The core Mandelbrot test; larger `max_iter` produces more detail at high zoom.
- **Interior tests**: Fast algebraic checks (main cardioid, period-2 bulb) that skip the iterative test for points known to be inside the set, speeding up rendering significantly.
- **Color palette**: A smooth 16-stop blue-to-yellow-to-brown gradient used to color exterior (escaped) pixels. Positions in the gradient are determined by histogram equalization of escape-iteration counts, ensuring the full color range is used regardless of zoom depth or iteration scale. Interior points (never escaped) are always rendered as pure black.

### Inputs and outputs

#### Inputs

- stdin: not used
- CLI arguments: center coordinates (real + imaginary parts as strings, for exact `mpq` conversion), frame width/height, output image dimensions
- Config file: stored in the OS-native location via `transcrypto.utils.config`

#### Outputs

- stdout: progress info and saved filename
- stderr: warnings/errors/logs (controlled by `--verbose`)
- Output images are saved as `<prefix>[-<YYYYMMDDhhmmss>][-<SHA256-20>].png`; the prefix defaults to `mandel` and is set via `--prefix`; date inclusion is controlled by `--date/--no-date`; hash (first 20 chars of SHA256, 80 bits) inclusion is controlled by `--hash/--no-hash`; output directory is set via `-o/--out` (defaults to the current working directory)

## CLI Interface

### Quick start

![Full / Default](tests/data/images/demo-mandel-whole-set.png)

Render the [full Mandelbrot set](#full--default-1-80-bits) (default, 1024×1024):

```sh
$ poetry run zoom image

1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2], precision 80 bits, 1 magnification, AUTO iterations...

Pre: 100%|█████████████████████████████████████████████| 256/256 [00:00<00:00, 1011.19px/s]
Img: 100%|█████████████████████████████████████████████| 1048576/1048576 [00:13<00:00, 78912.96px/s]

Generated image 'bd77ee8874aa425422a9ea92867c53937f28534898d49a56b9e4d1dca7b5dd54' in 14.120 s, escape range (1, 1000)
Saved to "mandel-bd77ee8874aa425422a9.png"
```

As can be seen, the `Frame` is stored as rational numbers with arbitrary precision, `[(-3/4, 0) @ 5/2]`, so it is guaranteed to be exact (centered in $-0.75+0j$ and with width of $2.5$). It will pick a precision, in bits, which is the internal `float` representation (mantissa), and will pick the (max) number of iterations for the generation. The magnification here is 1 because it is the full Mandelbrot set. There will be a progress bar, counting the horizontal lines being produced. The generated image data will be hashed and then saved to a PNG on disk.

Render a 512×512 [well-known zoom ("Seahorse", ~155× magnification, 512×512)](#seahorse-155-83-bits):

```sh
poetry run zoom -w 512 -h 512 image " -0.74303" "0.126433" "0.01611"
```

![Seahorse](tests/data/images/demo-mandel-seahorse.png)

See many more examples in *[Comprehensive example images and zooms](#comprehensive-example-images-and-zooms)*.

### Command structure

```sh
zoom [global flags] <command> [args]
```

### Global flags

| Flag | Description | Default |
| --- | --- | --- |
| `--help` | Show help | off |
| `--version` | Show version and exit | off |
| `-v`, `-vv`, `-vvv`, `--verbose` | Verbosity (nothing=*ERROR*, `-v`=*WARNING*, `-vv`=*INFO*, `-vvv`=*DEBUG*) | *ERROR* |
| `--color`/`--no-color` | Force enable/disable colored output (respects `NO_COLOR` env var if not provided) | `--color` |
| `-w`/`--width` | Output image width in pixels (4–8192) | 1024 |
| `-h`/`--height` | Output image height in pixels (4–8192) | 1024 |
| `-o`/`--out` | Output directory path | current directory |
| `--prefix` | Filename prefix | `mandel` |
| `--date`/`--no-date` | Include date-time (`YYYYMMDDhhmmss`) in filename | `--date` |
| `--hash`/`--no-hash` | Include 20-char SHA256 hash in filename | `--hash` |

### CLI Commands Documentation

Auto-generated CLI reference: [**`zoom` documentation**](zoom.md)

### `zoom image` — Render a Mandelbrot image

```sh
zoom [-w WIDTH] [-h HEIGHT] image [CENTER_RE] [CENTER_IM] [F_WIDTH] [F_HEIGHT]
```

Arguments (all optional; defaults show the full Mandelbrot set):

| Argument | Description | Default |
| --- | --- | --- |
| `CENTER_RE` | Real part of the center point (string, for exact precision) | `'-0.75'` |
| `CENTER_IM` | Imaginary part of the center point (string, for exact precision) | `'0'` |
| `F_WIDTH` | Width of the frame in the real plane | `'2.5'` |
| `F_HEIGHT` | Height of the frame in the imaginary plane | same as `F_WIDTH` |

The command:

1. Constructs a `Frame` from the given coordinates using `gmpy2.mpq` exact arithmetic
2. Calculates the required `mpfr` precision automatically based on zoom depth
3. Scales `max_iter` logarithmically with magnification
4. Renders all pixels using the escape-time algorithm (with cardioid/bulb interior shortcuts)
5. Saves the PNG to `<prefix>[-<YYYYMMDDhhmmss>][-<SHA256-20>].png` in the working directory (or the path given by `-o/--out`)

See below for many example outputs.

### Comprehensive example images and zooms

You can run all these at once by executing `scripts/make_examples.sh`.

#### Full / Default (×1, 80 bits)

![Full / Default](tests/data/images/demo-mandel-whole-set.png)

Render the full [Mandelbrot set](https://en.wikipedia.org/wiki/Mandelbrot_set) with all the default values (image size 1024×1024, centered in $-0.75+0j$ and with width of $2.5$, a good frame that contains the whole set):

```sh
$ poetry run zoom image

1024x1024 Mandelbrot in frame [(-3/4, 0) @ 5/2], precision 80 bits, 1 magnification, AUTO iterations...

Pre: 100%|█████████████████████████████████████████████| 256/256 [00:00<00:00, 1011.19px/s]
Img: 100%|█████████████████████████████████████████████| 1048576/1048576 [00:13<00:00, 78912.96px/s]

Generated image 'bd77ee8874aa425422a9ea92867c53937f28534898d49a56b9e4d1dca7b5dd54' in 14.120 s, escape range (1, 1000)
Saved to "mandel-bd77ee8874aa425422a9.png"
```

This is what tranZoom considers ***"1 magnification"***, and will measure other magnifications against this size.

#### Seahorse (×155, 83 bits)

![Seahorse](tests/data/images/demo-mandel-seahorse.png)

Render a [well-known zoom ("Seahorse")](https://en.wikipedia.org/wiki/File:Mandel_zoom_03_seehorse.jpg) to a 512×512 image:

```sh
$ poetry run zoom -w 512 -h 512 image " -0.74303" "0.126433" "0.01611"

1024x1024 Mandelbrot in frame [(-74303/100000, 126433/1000000) @ 1611/100000], precision 83 bits, 155.183 magnification, AUTO iterations...

Pre: 100%|█████████████████████████████████████████████| 256/256 [00:00<00:00, 388.31px/s]
Img: 100%|█████████████████████████████████████████████| 1048576/1048576 [05:41<00:00, 3069.95px/s]

Generated image '0cf52a6f78b4a883727c553da286b9f0f446a3671b01a6e364e3ae8f9b2391b3' in 5.714 min, escape range (24, 9276)
Saved to "mandel-0cf52a6f78b4a883727c.png"
```

#### Seahorse Tail (×3k, 88 bits)

![Seahorse Tail](tests/data/images/demo-mandel-seahorse-tail.png)

Render a ["Seahorse Tail"](https://en.wikipedia.org/wiki/File:Mandel_zoom_05_tail_part.jpg) to a 512×512 image:

```sh
$ poetry run zoom -w 512 -h 512 image " -0.7436499" "0.13188204" "0.00073801"

1024x1024 Mandelbrot in frame [(-7436499/10000000, 3297051/25000000) @ 73801/100000000], precision 88 bits, 3.387 k magnification, AUTO iterations...

Pre: 100%|█████████████████████████████████████████████| 256/256 [00:00<00:00, 23513.97px/s]
Img: 100%|█████████████████████████████████████████████| 1048576/1048576 [00:48<00:00, 21757.95px/s]

Generated image '38824cdaa58b64496ebfd86facf4d4ba4596ab18db95ac97afd643a7a892ff83' in 48.953 s, escape range (36, 1000)
Saved to "mandel-38824cdaa58b64496ebf.png"
```

This image is relatively fast to generate (despite the zoom level, it has very little interior regions), so we use it in the unit and integration tests to make sure we are operating consistently. If the hash of this image changes, remember to change it in `src/tranzoom/cli/base.py`.

#### Powers of 1000

Centering on exactly:

$-0.7436438870371587047521915061147740000000008 + 0.13182590420531197049313205638514950000008j$

or, if you want to use as parameters:

`" -0.7436438870371587047521915061147740000000008" "0.13182590420531197049313205638514950000008"`

We have, for fun, generated a sequence of powers of 1000, demonstrating the amazing power of the infinite. The view size of each image is always $2.5$ times some power of 1000.

| Image | Bits | Depth | Size $2.5\times$ | Equivalent real-world size / Landmark examples |
| --- | --- | --- | --- | --- |
| ![Zoom 1](tests/data/images/demo-mandel-zoom-01.png) | $80$ | $1$-$1000$ | $1$ | $\sim 10^{11}$ light-years = Observable-universe scale, about $93$ billion light-years across. |
| ![Zoom 10^-3](tests/data/images/demo-mandel-zoom-02.png) | $86$ | $32$-$1000$ | $10^{-3}$ | $\sim 10^{8}$ light-years = Cosmic-web / supercluster scale: galaxy walls, voids. |
| ![Zoom 10^-6](tests/data/images/demo-mandel-zoom-03.png) | $96$ | $219$-$7348$ | $10^{-6}$ | $\sim 10^{5}$ light-years = Galaxy scale: the Milky Way is about $100{,}000$ light-years across. |
| ![Zoom 10^-9](tests/data/images/demo-mandel-zoom-04.png) | $106$ | $1006$-$2664$ | $10^{-9}$ | $\sim 100$ light-years = Local stellar-neighborhood scale: nearby star groups, nebulae, and star-forming regions. |
| ![Zoom 10^-12](tests/data/images/demo-mandel-zoom-05.png) | $116$ | $1974$-$3901$ | $10^{-12}$ | $\sim 0.1$ light-year = Outer-solar-system scale: comparable to the distant Oort-cloud region. |
| ![Zoom 10^-15](tests/data/images/demo-mandel-zoom-06.png) | $126$ | $4132$-$93051$ | $10^{-15}$ | $\sim 10^{9}\,\mathrm{km}$ = Inner-to-middle solar-system scale: comparable to giant-planet orbital distances. |
| ![Zoom 10^-18](tests/data/images/demo-mandel-zoom-07.png) | $136$ | $8035$-$11740$ | $10^{-18}$ | $\sim 10^{6}\,\mathrm{km}$ = Star / giant-planet scale: the Sun’s diameter is about $1.39 \times 10^{6}\,\mathrm{km}$. |
| ![Zoom 10^-21](tests/data/images/demo-mandel-zoom-08.png) | $146$ | $9033$-$15673$ | $10^{-21}$ | $\sim 10^{3}\,\mathrm{km}$ = Planetary-geography scale: large countries, small moons, continent-scale weather systems. |
| ![Zoom 10^-24](tests/data/images/demo-mandel-zoom-09.png) | $156$ | $13074$-$33133$ | $10^{-24}$ | $\sim 1\,\mathrm{km}$ = Human landscape scale: mountains, city districts, bridges, runways. |
| ![Zoom 10^-27](tests/data/images/demo-mandel-zoom-10.png) | $166$ | $17130$-$32103$ | $10^{-27}$ | $\sim 1\,\mathrm{m}$ = Human/body scale: a person, table, doorway, musical instrument. |
| ![Zoom 10^-30](tests/data/images/demo-mandel-zoom-11.png) | $176$ | $26939$-$61788$ | $10^{-30}$ | $\sim 1\,\mathrm{mm}$ = Small visible-object scale: sand grains, seeds, insect parts, raindrops. |
| ![Zoom 10^-33](tests/data/images/demo-mandel-zoom-12.png) | $186$ | $58119$-$205876$ | $10^{-33}$ | $\sim 1\,\mu\mathrm{m}$ = Cell/microbe scale: bacteria, organelles, and wavelengths near visible/infrared light. |
| ![Zoom 10^-36](tests/data/images/demo-mandel-zoom-13.png) | $196$ | $65240$-$67722$ | $10^{-36}$ | $\sim 1\,\mathrm{nm}$ = Molecule scale: DNA width, proteins, small molecular machines. |
| ![Zoom 10^-39](tests/data/images/demo-mandel-zoom-14.png) | $206$ | $65327$-$67968$ | $10^{-39}$ | $\sim 1\,\mathrm{pm}$ = Deep atomic/electron-cloud scale: smaller than typical atomic diameters, which are around $10^{-10}\,\mathrm{m}$. |
| ![Zoom 10^-42](tests/data/images/demo-mandel-zoom-15.png) | $216$ | $1$-$1$ | $10^{-42}$ | $\sim 1\,\mathrm{fm}$ = Atomic nucleus / proton scale: the proton rms charge radius is about $8.4075 \times 10^{-16}\,\mathrm{m}$. |
| ![Zoom 10^-45](tests/data/images/demo-mandel-zoom-16.png) | $1$ | $1$-$1$ | $10^{-45}$ | $\sim 1\,\mathrm{am}$ = Quarks and leptons: elementary particles in the Standard Model |

" -0.743643887037158704752191506114774" "0.131825904205311970493132056385139"

### Configuration

Config files are stored in OS-native locations via `transcrypto.utils.config`:

- macOS: `~/Library/Application Support/tranzoom/config.bin`
- Linux: `~/.config/tranzoom/config.bin`
- Windows: `%APPDATA%\tranzoom\config.bin`

### Color and formatting

The CLI respects the `NO_COLOR` environment variable and the `--no-color` / `--color` flag. Rich markup is used for console output — see [Rich markup conventions](https://rich.readthedocs.io/en/latest/markup.html).

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Generic failure |
| 2 | CLI usage error (bad arguments) |

## Project Design

### Modules / packages

| Component | Responsibility |
| --- | --- |
| `zoom.py` | CLI entry point (`app`, `Main`, `TranZoomConfig`) |
| `cli/base.py` | Shared CLI options, defaults, `DEFAULT_FRAME` |
| `cli/imagecommand.py` | `zoom image` command implementation |
| `core/fractal.py` | `Mandelbrot()` renderer — most fractal math |
| `core/frame.py` | `Frame` class and base math |
| `core/image.py` | `Image` class |
| `utils/template.py` | Template for new utility modules |

### Performance characteristics

Rendering is CPU-bound. Time scales roughly with `width × height × max_iter × precision_overhead`. For deep zooms, higher precision means slower `mpfr` arithmetic (roughly linear in the number of bits). For very deep zooms (>100 bits precision), rendering a 256×256 image at 50k iterations can take minutes to hours. The `tqdm` progress bar shows per-row speed.

The `Mandelbrot()` function pre-computes all X-axis `mpfr` values once per image and reuses them across rows, which is an important optimization since `mpfr` construction is expensive at high precision.

## Development Instructions

### File structure

```txt
.
├── CHANGELOG.md                  ⟸ latest changes/releases
├── LICENSE
├── Makefile
├── zoom.md                       ⟸ auto-generated CLI doc (by `make docs` or `make ci`)
├── poetry.lock                   ⟸ maintained by Poetry; do not manually edit
├── pyproject.toml                ⟸ most important configurations live here
├── README.md                     ⟸ this documentation
├── SECURITY.md                   ⟸ security policy
├── requirements.txt
├── .editorconfig
├── .gitignore
├── .pre-commit-config.yaml       ⟸ pre-submit configs
├── .github/
│   ├── copilot-instructions.md
│   ├── dependabot.yaml
│   └── workflows/
│       ├── ci.yaml
│       └── codeql.yaml
├── .vscode/
│   ├── extensions.json
│   └── settings.json
├── scripts/
│   ├── make_examples.sh          ⟸ renders example images at all zoom levels to test/data/images
│   └── template.py               ⟸ template for standalone executable scripts
├── src/
│   └── tranzoom/
│       ├── __init__.py           ⟸ version lives here
│       ├── __main__.py
│       ├── zoom.py               ⟸ main CLI entry point (Main, TranZoomConfig)
│       ├── py.typed
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── base.py           ⟸ shared CLI options and frame defaults
│       │   └── imagecommand.py   ⟸ `zoom image` command implementation
│       ├── core/
│       │   ├── __init__.py
│       │   ├── fractal.py        ⟸ Mandelbrot() renderer
│       │   ├── frame.py          ⟸ Frame class; base for computation
│       │   └── image.py          ⟸ Image class
│       └── utils/
│           ├── __init__.py
│           └── template.py       ⟸ template for new utility modules
├── tests/
│   ├── zoom_test.py
│   ├── cli/
│   │   ├── base_test.py          ⟸ seahorse tail hash regression test
│   │   └── imagecommand_test.py
│   └── data/
│       └── images/               ⟸ example renders at 7 zoom levels (committed to git)
└── tests_integration/
    └── test_installed_cli.py
```

### Development Setup

#### Install Python

On **Linux**:

```sh
sudo apt-get update && sudo apt-get upgrade
sudo apt-get install git python3 python3-dev python3-venv build-essential software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt-get update
sudo apt-get install python3.12  # or python3.13 or python3.14
```

On **macOS**:

```sh
brew update && brew upgrade && brew cleanup -s
brew install git python@3.12  # or python3.13 or python3.14
```

Note: `gmpy2` requires the GMP, MPFR, and MPC C libraries. On macOS: `brew install gmp mpfr mpc`. On Linux: `sudo apt-get install libgmp-dev libmpfr-dev libmpc-dev`.

#### Install Poetry (recommended: `pipx`)

[Poetry reference.](https://python-poetry.org/docs/cli/)

```sh
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install poetry
poetry --version
```

If you will use [PyPI](https://pypi.org/) to publish:

```sh
poetry config pypi-token.pypi <TOKEN>
```

#### Make sure `.venv` is local

```sh
poetry config virtualenvs.in-project true
```

#### Get the repository

```sh
git clone https://github.com/balparda/tranzoom.git
cd tranzoom
```

#### Create environment and install dependencies

```sh
poetry env use python3.12   # creates the .venv with the correct Python version
poetry sync                  # install all dependencies from poetry.lock
poetry env info              # verify environment
poetry run zoom --help       # smoke test
make ci                      # should pass on clean repo
```

To activate the environment:

```sh
source .venv/bin/activate
# ... work ...
deactivate
```

#### Optional: VSCode setup

This repo ships a `.vscode/settings.json` configured to use `./.venv/bin/python`, run `pytest`, format with Ruff, and use Google-style docstrings. Recommended extensions:

- Python (`ms-python.python`)
- Python Environments (`ms-python.vscode-python-envs`)
- Python Debugger (`ms-python.debugpy`)
- Pylance (`ms-python.vscode-pylance`)
- Mypy Type Checker (`ms-python.mypy-type-checker`)
- Ruff (`charliermarsh.ruff`)
- autoDocstring (`njpwerner.autodocstring`)
- Code Spell Checker (`streetsidesoftware.code-spell-checker`)
- markdownlint (`davidanson.vscode-markdownlint`)
- Markdown All in One (`yzhang.markdown-all-in-one`)
- GitHub Copilot (`github.copilot`)

### Build

```sh
poetry build   # builds wheel + sdist in dist/
```

### Run locally

```sh
poetry run zoom --help
poetry run zoom image                                          # full set, 1024×1024
poetry run zoom -w 512 -h 512 image "-0.74303" "0.126433" "0.01611"  # seahorse valley
```

### Testing

#### Unit tests / Coverage

```sh
make test               # plain test run (no integration tests)
make integration        # run the integration tests
poetry run pytest -vvv  # verbose

make cov  # coverage: poetry run pytest --cov=src --cov-report=term-missing
```

Test tags defined in `pyproject.toml`:

| Tag | Meaning |
| --- | --- |
| `slow` | test takes > 1s |
| `flaky` | known flaky test — avoid |
| `stochastic` | may fail with very low probability |

Filter by tag:

```sh
poetry run pytest -vvv -m slow
```

Find slow tests:

```sh
poetry run pytest -vvv -q --durations=20
```

Find flaky tests:

```sh
make flakes  # runs all tests 100 times
```

#### Instrumenting your code

```sh
source .venv/bin/activate
pyinstrument -r html -o profile.html -- $(which zoom) image "-0.74303" "0.126433" "0.01611"
deactivate
```

#### Integration / e2e tests

Integration tests build a wheel, install it into a fresh temporary virtualenv, and run the console scripts. Run with:

```sh
make integration
# or:
poetry run pytest -m integration -q
```

### Linting / formatting / static analysis

```sh
make lint  # poetry run ruff check .
make fmt   # poetry run ruff format .

poetry run ruff format --check .  # check formatting without rewriting
```

#### Type checking

```sh
make type  # poetry run mypy src tests tests_integration
```

### Documentation updates

CLI reference is auto-generated from the CLI source code:

```sh
make docs  # regenerates zoom.md
# or:
poetry run zoom markdown > zoom.md
```

Always run `make ci` before committing — it runs linting, type checking, tests, and regenerates docs and `requirements.txt`.

### Versioning and releases

#### Versioning scheme

- **Patch**: bug fixes / docs / small improvements.
- **Minor**: new features or non-breaking changes.
- **Major**: breaking changes (command renames, incompatible output formats).

See: [CHANGELOG.md](CHANGELOG.md)

#### Updating versions

##### Bump project version (patch/minor/major)

```sh
poetry version minor   # 1.0.0 → 1.1.0
poetry version patch   # 1.0.0 → 1.0.1
poetry version 1.2.3   # explicit version
```

**Also update `src/tranzoom/__init__.py` to match!**

##### Update dependency versions

```sh
poetry update                      # update poetry.lock to latest compatible versions
poetry cache clear PyPI --all      # if cache issues
poetry add "pkg>=1.2.3"            # add prod dependency
poetry add -G dev "pkg>=1.2.3"     # add dev dependency
```

##### Exporting the `requirements.txt` file

```sh
make req  # poetry export --format requirements.txt --without-hashes --output requirements.txt
```

##### CI and docs

```sh
make ci  # runs lint, type check, tests, docs, requirements — do this before every commit
```

##### Git tag and commit

```sh
git commit -a -m "release version 1.0.0"
git tag 1.0.0
git push && git push --tags
```

##### Publish to PyPI

```sh
poetry config pypi-token.pypi <TOKEN>  # once, if not already configured
poetry build
poetry publish
```

## Security

Please refer to the security policy in [SECURITY.md](SECURITY.md) for supported versions and how to report vulnerabilities.

The project uses [**CodeQL**](https://codeql.github.com/docs/) (weekly + on every push) and [**dependabot**](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/dependabot-quickstart-guide) (weekly dependency updates) to keep the codebase secure and up-to-date.

## Troubleshooting

### Enable debug output

```sh
zoom -vvv image ...   # DEBUG level logging
```

### `gmpy2` installation issues

On macOS, `gmpy2` requires the GMP, MPFR, and MPC C libraries. Install them first:

```sh
brew install gmp mpfr mpc
poetry sync
```

On Linux:

```sh
sudo apt-get install libgmp-dev libmpfr-dev libmpc-dev
poetry sync
```

### Rendering is very slow

- Reduce image size: `zoom -w 256 -h 256 image ...`
- `max_iter` is auto-scaled with zoom depth; very deep zooms are inherently slow
- Very high precision (> 1000 bits, i.e., zoom > ~10^300) will always be slow — this is expected

---

Thanks! *Daniel Balparda & Bella Keri*
