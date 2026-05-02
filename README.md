<!-- SPDX-FileCopyrightText: Copyright 2026 Daniel Balparda <balparda@github.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# poetrycli - Python/Poetry/Typer/Rich CLI Template

***TODO:*** *One-line description of what this CLI does and who it’s for. Change the title above.*

- **Primary use case:** *<e.g., bulk process files, manage deployments, query APIs>*
- **Works with:** *<e.g., local files, Git repos, Kubernetes, AWS, JSON logs>*
- **Status:** *<stable | beta | experimental>*
- **License:** *<MIT | Apache-2.0 | GPL-3.0 | Proprietary>*

***TODO:*** *throughout this documentation* ***ITALICS*** *mark* ***placeholder content*** *that a new project would typically want to edit with its own information.*

***TODO:*** *If you are starting a new project, there are lots of instructions and useful information in the* "[Appendix **I**: Using the `poetrycli` template](#appendix-i-using-the-poetrycli-template)" *and* [Appendix **II**: Template Checklist](#appendix-ii-template-checklist-turning-poetrycli-into-your-new-cli-project-in-12-steps) *sections.*

**`poetrycli`** is a **template** for building modern Python CLI applications using:

- **Python 3.12** or **Python 3.13** or **Python 3.14**
- **Poetry** for packaging, dependency management, and `venv` workflow
- **Typer** for CLI structure (commands, options, subcommands, help)
- **Transcrypto** for CLI modules, logging, humanization, crypto, random, hash, serialization, etc
- **Rich** for consistent console output and pretty logging
- **Ruff** for formatting + linting
- **MyPy** (and **Pyright/Pylance/typeguard**) for strict type checking
- **Pytest + coverage** for tests
- **pre-commit** + **GitHub Actions CI** to keep everything enforced automatically
- **dependabot** + **codeql** to keep dependencies always up-to-date and security issues at bay

The `poetrycli` repo is intentionally opinionated because it was built to help the authors (2-space indentation, single quotes, strict typing, “select ALL rules” linting are examples) but includes escape hatches and ***TODO*** markers to customize quickly. Started in Jan/2026, by ***Daniel Balparda***.

*Since version 0.1.0 it is PyPI package: <https://pypi.org/project/foobarnotreally/>*

***TODO:*** *change this header to match your project's conditions.*

## Table of contents

- [poetrycli - Python/Poetry/Typer/Rich CLI Template](#poetrycli---pythonpoetrytyperrich-cli-template)
  - [Table of contents](#table-of-contents)
  - [License](#license)
    - [*Third-party notices (TODO)*](#third-party-notices-todo)
    - [*Contributions and inbound licensing (TODO)*](#contributions-and-inbound-licensing-todo)
  - [*Installation (TODO)*](#installation-todo)
    - [*Supported platforms (TODO)*](#supported-platforms-todo)
    - [Known dependencies (Prerequisites)](#known-dependencies-prerequisites)
  - [*Context / Problem Space (TODO)*](#context--problem-space-todo)
    - [*What this tool is (TODO)*](#what-this-tool-is-todo)
    - [*What this tool is not (TODO)*](#what-this-tool-is-not-todo)
    - [*Key concepts and terminology* (TODO)](#key-concepts-and-terminology-todo)
    - [*Inputs and outputs (TODO)*](#inputs-and-outputs-todo)
      - [*Inputs (TODO)*](#inputs-todo)
      - [*Outputs (TODO)*](#outputs-todo)
  - [*Design assumptions / Disclaimers (TODO)*](#design-assumptions--disclaimers-todo)
    - [*Guarantees and stability (TODO)*](#guarantees-and-stability-todo)
    - [*Assumptions (TODO)*](#assumptions-todo)
    - [*Known limitations (TODO)*](#known-limitations-todo)
    - [*Deprecation policy (TODO)*](#deprecation-policy-todo)
    - [*Privacy / telemetry (TODO)*](#privacy--telemetry-todo)
  - [*CLI Interface (TODO)*](#cli-interface-todo)
    - [*Quick start (TODO)*](#quick-start-todo)
    - [*Common workflows (TODO)*](#common-workflows-todo)
      - [*Workflow 1 (TODO)*](#workflow-1-todo)
      - [*Workflow 2 (TODO)*](#workflow-2-todo)
    - [*Command structure (TODO)*](#command-structure-todo)
    - [Global flags](#global-flags)
    - [CLI Commands Documentation](#cli-commands-documentation)
    - [*Configuration (TODO)*](#configuration-todo)
      - [Config file locations](#config-file-locations)
      - [*Configuration schema (TODO)*](#configuration-schema-todo)
      - [*Validate configuration (TODO)*](#validate-configuration-todo)
      - [*Environment variables (TODO)*](#environment-variables-todo)
    - [*Input / output behavior (TODO)*](#input--output-behavior-todo)
      - [*`stdin` and piping (TODO)*](#stdin-and-piping-todo)
      - [*Output formats (TODO)*](#output-formats-todo)
      - [Color and formatting](#color-and-formatting)
      - [*Exit codes (TODO)*](#exit-codes-todo)
    - [*Logging and observability (TODO)*](#logging-and-observability-todo)
    - [*Safety features (TODO)*](#safety-features-todo)
  - [*Project Design (TODO)*](#project-design-todo)
    - [*Architecture overview (TODO)*](#architecture-overview-todo)
    - [*Modules / packages (TODO)*](#modules--packages-todo)
    - [*Data flow (TODO)*](#data-flow-todo)
    - [*Error handling philosophy (TODO)*](#error-handling-philosophy-todo)
    - [*Security model (TODO)*](#security-model-todo)
    - [*Performance characteristics (TODO)*](#performance-characteristics-todo)
  - [Development Instructions](#development-instructions)
    - [File structure](#file-structure)
    - [Development Setup](#development-setup)
      - [*Requirements (TODO)*](#requirements-todo)
      - [Install Python](#install-python)
      - [Install Poetry (recommended: `pipx`)](#install-poetry-recommended-pipx)
      - [Make sure `.venv` is local](#make-sure-venv-is-local)
      - [Get the repository](#get-the-repository)
      - [Create environment and install dependencies](#create-environment-and-install-dependencies)
      - [Optional: VSCode setup](#optional-vscode-setup)
    - [*Build (TODO)*](#build-todo)
    - [*Run locally (TODO)*](#run-locally-todo)
    - [Testing](#testing)
      - [Unit tests / Coverage](#unit-tests--coverage)
      - [Instrumenting your code](#instrumenting-your-code)
      - [Integration / e2e tests](#integration--e2e-tests)
      - [*Golden tests for CLI output (TODO)*](#golden-tests-for-cli-output-todo)
    - [Linting / formatting / static analysis](#linting--formatting--static-analysis)
      - [Type checking](#type-checking)
    - [*Documentation updates (TODO)*](#documentation-updates-todo)
    - [Versioning and releases](#versioning-and-releases)
      - [Versioning scheme](#versioning-scheme)
      - [Updating versions](#updating-versions)
        - [Bump project version (patch/minor/major)](#bump-project-version-patchminormajor)
        - [Update dependency versions](#update-dependency-versions)
        - [Exporting the `requirements.txt` file](#exporting-the-requirementstxt-file)
        - [CI and docs](#ci-and-docs)
        - [Git tag and commit](#git-tag-and-commit)
        - [Publish to PyPI](#publish-to-pypi)
    - [*Contributing (TODO)*](#contributing-todo)
  - [Security](#security)
    - [*Supply chain (TODO)*](#supply-chain-todo)
  - [*Reliability (TODO)*](#reliability-todo)
    - [*Operational guidance (TODO)*](#operational-guidance-todo)
    - [*Running in automation (TODO)*](#running-in-automation-todo)
    - [*Failure modes (TODO)*](#failure-modes-todo)
  - [*Troubleshooting (TODO)*](#troubleshooting-todo)
    - [*Enable debug output (TODO)*](#enable-debug-output-todo)
    - [*Common issues (TODO)*](#common-issues-todo)
    - [*Collect diagnostics (TODO)*](#collect-diagnostics-todo)
  - [*FAQ (TODO)*](#faq-todo)
    - [*FAQ Section I (TODO)*](#faq-section-i-todo)
      - [*Why does `<project>` need `<permission/dependency>`? (TODO)*](#why-does-project-need-permissiondependency-todo)
      - [*How do I migrate from version X to Y? (TODO)*](#how-do-i-migrate-from-version-x-to-y-todo)
      - [*How stable is the JSON output? (TODO)*](#how-stable-is-the-json-output-todo)
  - [*Glossary (TODO)*](#glossary-todo)
  - [Appendix **I**: Using the `poetrycli` template](#appendix-i-using-the-poetrycli-template)
    - [New Projects](#new-projects)
      - [Rename the package + CLI entrypoint](#rename-the-package--cli-entrypoint)
      - [Update app name used for config paths](#update-app-name-used-for-config-paths)
      - [Pick a Python version (skip if 3.12 is good)](#pick-a-python-version-skip-if-312-is-good)
      - [Customize CLI banner + top-level options](#customize-cli-banner--top-level-options)
      - [Optional: adjust style/lint strictness](#optional-adjust-stylelint-strictness)
    - [`poetrycli` Features explained](#poetrycli-features-explained)
      - [CLI design (Typer)](#cli-design-typer)
      - [Rich logging + Console singleton (`transcrypto`)](#rich-logging--console-singleton-transcrypto)
      - [Separation of CLI and business logic](#separation-of-cli-and-business-logic)
      - [Config management (`transcrypto.util.config`)](#config-management-transcryptoutilconfig)
      - [Strict linting + formatting with Ruff (pyproject.toml)](#strict-linting--formatting-with-ruff-pyprojecttoml)
      - [Typing checks (MyPy + Pyright)](#typing-checks-mypy--pyright)
      - [Tests + coverage (`pytest`)](#tests--coverage-pytest)
      - [Pre-commit checks](#pre-commit-checks)
      - [CI (GitHub Actions)](#ci-github-actions)
  - [Appendix **II**: Template Checklist: turning `poetrycli` into your new CLI project in 12 steps](#appendix-ii-template-checklist-turning-poetrycli-into-your-new-cli-project-in-12-steps)
    - [0: Prerequisites (one-time per machine)](#0-prerequisites-one-time-per-machine)
    - [1: Decide your identity](#1-decide-your-identity)
    - [2: Rename the Python package directory](#2-rename-the-python-package-directory)
    - [3: Update `pyproject.toml` (the big one)](#3-update-pyprojecttoml-the-big-one)
    - [3.1 Required metadata](#31-required-metadata)
      - [3.2: Poetry packaging + entrypoint wiring](#32-poetry-packaging--entrypoint-wiring)
      - [3.3: If you change Python version…](#33-if-you-change-python-version)
    - [4: Sync the runtime `__version__`](#4-sync-the-runtime-__version__)
    - [5: Update config app name](#5-update-config-app-name)
    - [6: Review lint policy (Ruff)](#6-review-lint-policy-ruff)
    - [7: Run the full validation suite (before first commit)](#7-run-the-full-validation-suite-before-first-commit)
    - [8: First release workflow (suggested)](#8-first-release-workflow-suggested)
    - [9:  Update README](#9--update-readme)
    - [10: Customize the CLI global flags](#10-customize-the-cli-global-flags)
    - [11: “Cleanup”](#11-cleanup)
    - [12: Done: Start building your project](#12-done-start-building-your-project)

## License

Copyright 2025 Daniel Balparda <balparda@github.com>

Licensed under the ***Apache License, Version 2.0*** (the "License"); you may not use this file except in compliance with the License. You may obtain a [copy of the License here](http://www.apache.org/licenses/LICENSE-2.0).

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

### *Third-party notices (TODO)*

*This project includes or depends on third-party software. See:*

- *NOTICE \<link\> (if applicable)*
- *Dependency license list: \<link or section\>*

### *Contributions and inbound licensing (TODO)*

- *Contributions are accepted under: \<same as project license | CLA | DCO\>*
- *Policy: \<link to CONTRIBUTING.md\>*

## *Installation (TODO)*

*To use in your project just do:*

```sh
pip3 install <your_pkg>
```

*and then `from <your_pkg> import <your_library>` (or other parts of the library) for using it.*

### *Supported platforms (TODO)*

- *OS: \<Linux | macOS | Windows\>*
- *Architectures: \<x86_64 | arm64\>*
- *Minimum versions: \<e.g., macOS 12+, Ubuntu 20.04+, Windows 11\>*

### Known dependencies (Prerequisites)

- **[python 3.12](https://python.org/)** - [documentation](https://docs.python.org/3.12/)
- **[rich 14.2+](https://pypi.org/project/rich/)** - Render rich text, tables, progress bars, syntax highlighting, markdown and more to the terminal - [documentation](https://rich.readthedocs.io/en/latest/)
- **[typer 0.21+](https://pypi.org/project/typer/)** - CLI parser - [documentation](https://typer.tiangolo.com/)
- **[transcrypto 2.1+](https://pypi.org/project/transcrypto/)** - CLI modules, logging, humanization, crypto, random, hash, serialization, config management, etc. - [documentation](https://github.com/balparda/transcrypto)
- **[poetrycli](https://github.com/balparda/poetrycli)** - CLI app templates and utils
- ***TODO:*** *add your main dependencies here too*

## *Context / Problem Space (TODO)*

### *What this tool is (TODO)*

*\<Describe the CLI in one paragraph. Emphasize outcomes and workflows.\>*

### *What this tool is not (TODO)*

- *Not intended for:*
- *Not a replacement for:*

### *Key concepts and terminology* (TODO)

- *A*
- *B*

### *Inputs and outputs (TODO)*

#### *Inputs (TODO)*

- *stdin: \<supported | not supported\>*
- *Files: \<paths, globs, formats\>*
- *Network/API: \<endpoints, services\>*
- *Environment variables/config:*

#### *Outputs (TODO)*

- *stdout: \<human output / structured output\>*
- *stderr: \<errors/logging\>*
- *Files/artifacts:*

## *Design assumptions / Disclaimers (TODO)*

### *Guarantees and stability (TODO)*

- *CLI flags/commands stability: \<stable | may change\>*
- *JSON output stability: \<stable schema | best-effort\>*
- *Backward compatibility:*

### *Assumptions (TODO)*

- *Environment: \<filesystem, permissions, network access\>*
- *Locale/encoding: \<UTF-8 expected?\>*
- *Time/timezone:*

### *Known limitations (TODO)*

- *Scale limits: \<e.g., tested up to 10k files\>*
- *Platform limitations: \<e.g., Windows path edge cases\>*
- *Edge cases: \<symlinks, long paths, etc.\>*

### *Deprecation policy (TODO)*

- *Deprecations are announced via:*
- *Timeline: \<e.g., 2 minor versions\>*
- *Migration guidance:*

### *Privacy / telemetry (TODO)*

- *Telemetry: \<none | optional | on by default\>*
- *What is collected:*
- *How to disable: \<env var | config flag\>*

## *CLI Interface (TODO)*

### *Quick start (TODO)*

*Minimal example.*

```sh
<project> <command> <arg>
```

### *Common workflows (TODO)*

#### *Workflow 1 (TODO)*

```sh
<project> <cmd> --flag value <input>
```

#### *Workflow 2 (TODO)*

```sh
<project> <cmd> <input> --output <file>
```

### *Command structure (TODO)*

General shape:

```sh
<project> [global flags] <command> [command flags] [args]
```

### Global flags

| Flag | Description | Default |
| --- | --- | --- |
| `-h`, `--help` | Show help | \<off\> |
| `--version` | Show version and exit | \<off\> |
| `-v`, `-vv`, `-vvv`, `--verbose` | Verbosity (nothing=*ERROR*, `-v`=*WARNING*, `-vv`=*INFO*, `-vvv`=*DEBUG*) | *ERROR* |
| `--color`/`--no-color` | Force enable/disable colored output (respects NO_COLOR env var if not provided) | `--color` |

### CLI Commands Documentation

This software auto-generates docs for CLI apps:

- [**`mycli`** documentation](mycli.md)

### *Configuration (TODO)*

#### Config file locations

This template uses `transcrypto.util.config` for configuration management. Config files are stored in OS-native locations:

- On MacOS: `/Users/[user]/Library/Application Support/[app_name]{/[version]}`
- On Windows: `C:\\Users\\[user]\\AppData\\Local{\\[app_author]}\\[app_name]{\\[version]}`
- On Linux: `/home/[user]/.config/[app_name]{/[version]}`
- On Android: `/data/data/com.myApp/shared_prefs/[app_name]{/[version]}`

***TODO: add specific config files info***

#### *Configuration schema (TODO)*

```yaml
# ~/.config/<project>/config.yaml
profile: default
timeout_ms: 30000
retries: 3
output:
  format: human # or json
  color: auto   # auto|always|never
```

#### *Validate configuration (TODO)*

```sh
<project> config validate
<project> config show --effective
```

#### *Environment variables (TODO)*

| Variable | Description | Default | Notes |
| --- | --- | --- | --- |
| `<PROJECT>_CONFIG` | Config file path | \<auto\> | |
| `<PROJECT>_LOG_LEVEL` | Log level | info | debug |
| `<PROJECT>_NO_COLOR` | Disable color | \<unset\> | obeys `NO_COLOR` too |

### *Input / output behavior (TODO)*

#### *`stdin` and piping (TODO)*

```sh
cat input.txt | <project> <command> --from-stdin
```

#### *Output formats (TODO)*

- *Human-readable (default)*
- *JSON (`--json`) for automation and scripting*

#### Color and formatting

Rich can provide color output in logging and in CLI output. App:

- Respects `NO_COLOR` environment variable
- Has `--no-color` / `--color` flag: if given will override the `NO_COLOR` environment variable
- If there is no environment variable and no flag is given, default to having color

To control color see [Rich's markup conventions](https://rich.readthedocs.io/en/latest/markup.html). In summary, the basic 16 colors are:

- `black`, `red`, `green`, `yellow`, `blue`, `magenta`, `cyan`, `white`
- Bright variants: `bright_black` (gray), `bright_red`, `bright_green`, `bright_yellow`, `bright_blue`, `bright_magenta`, `bright_cyan`, `bright_white`

Extended named colors (256-color palette) are as above, plus many more, including these useful ones:

- `grey0` through `grey100` (grayscale)
- `dark_red`, `light_red`, `dark_green`, `light_green`, `dark_blue`, `light_blue`, `dark_cyan`, `light_cyan`, `dark_magenta`, `light_magenta`
- `orange1`, `orange3`, `orange4`, `purple`, `purple4`, `gold1`, `gold3`

Styles you can combine with colors are: `bold`, `dim`, `italic`, `underline`, `blink`, `reverse`, `strike`, `overline`. Common usage patterns:

- `[red]text[/]` - red text
- `[bold red]text[/]` - bold red text
- `[bold]text[/]` - just bold
- `[#ff0000]text[/]` - hex color (RGB)
- `[rgb(255,0,0)]text[/]` - RGB notation
- `[on blue]text[/]` - blue **background**
- `[red on white]text[/]` - red text on white **background**

#### *Exit codes (TODO)*

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Generic failure |
| 2 | CLI usage error |
| 3 | Runtime dependency failure (network/filesystem) |
| 4 | Partial success (some items failed) |

*Keep this stable if users will script against it.*

### *Logging and observability (TODO)*

- *Log levels: error|warn|info|debug|trace*
- *Structured logs: \<supported? --log-format=json\>*
- *Debug bundle: \<project\> debug report (if available)*

### *Safety features (TODO)*

- *Dry run: `--dry-run` (no side effects)*
- *Non-interactive: `--yes` / `--no-input`*
- *Force: `--force` (document exactly what it bypasses)*

## *Project Design (TODO)*

### *Architecture overview (TODO)*

*\<High-level description of components and how they interact.\>*

*Example:*

- *CLI parser → configuration loader → core engine → output renderer*
- *Optional: plugins/adapters for external systems*

### *Modules / packages (TODO)*

| Component | Responsibility |
| --- | --- |
| cmd/ | CLI entrypoints and subcommands |
| internal/core/ | Core business logic |
| internal/io/ | Filesystem/network adapters |
| internal/output/ | Output formatting (human/JSON) |

### *Data flow (TODO)*

1. *Parse args + load config*
1. *Validate inputs*
1. *Execute core operation(s)*
1. *Collect results and render output*
1. *Return exit code*

### *Error handling philosophy (TODO)*

- *Clear actionable messages for user errors*
- *Structured errors for --json*
- *Avoid leaking secrets in errors/logs*

### *Security model (TODO)*

- *Principle of least privilege*
- *Secret handling: never log secrets; redact by default*
- *TLS verification: on by default; disabling requires explicit opt-in*

### *Performance characteristics (TODO)*

- *Intended scale:*
- *Complexity notes:*
- *Benchmarks:*

## Development Instructions

### File structure

```txt
.
├── CHANGELOG.md                  ⟸ latest changes/releases
├── LICENSE
├── Makefile
├── mycli.md                      ⟸ this is auto-generated CLI doc (by `make docs` or `make ci`)
├── poetry.lock                   ⟸ this is maintained by Poetry, do not manually edit
├── pyproject.toml                ⟸ most important configurations live here
├── README.md                     ⟸ this documentation
├── SECURITY.md                   ⟸ security policy
├── requirements.txt
├── .editorconfig
├── .gitignore
├── .pre-commit-config.yaml       ⟸ pre-submit configs
├── .github/
│   ├── copilot-instructions.md   ⟸ GitHub Copilot project-specific instructions
│   ├── dependabot.yaml           ⟸ Github dependency update pipeline
│   └── workflows/
│       ├── ci.yaml               ⟸ Github CI pipeline
│       └── codeql.yaml           ⟸ Github security scans and code quality pipeline
├── .vscode/
│   ├── extensions.json
│   └── settings.json             ⟸ VSCode configs
├── scripts/
│   └── template.py               ⟸ Use template & directory for executable standalone scripts
├── src/
│   └── <your_pkg>/               ⟸ change this directory's name (originally mycli)
│       ├── __init__.py
│       ├── __main__.py
│       ├── mycli.py              ⟸ Main CLI app entry point (Main())
│       ├── py.typed
│       ├── cli/
│       │   ├── __init__.py
│       │   └── randomcommand.py  ⟸ CLI commands implementation, to keep `mycli.py` clean
│       ├── core/
│       │   ├── __init__.py
│       │   └── example.py        ⟸ Business logic goes in this directory
│       └── utils/
│           ├── __init__.py
│           └── template.py       ⟸ Use template for starting regular modules
├── tests/                        ⟸ Unit-Testing goes in this directory
│   ├── mycli_test.py
│   └── ...                       ⟸ Usually, a similar structure to `src/mycli/...`
└── tests_integration/
    └── test_installed_cli.py     ⟸ Integration testing goes in this directory
```

What each area is for:

- `src/<your_pkg>/cli.py`: **Typer app** definition, top-level callback (**Main**), and all **commands/subcommands**.
- `src/<your_pkg>/core/example.py`: **“Business logic”** layer. CLI commands call into here. This is the main testable logic layer.
- `src/<your_pkg>/utils/template.py`: A template module showing a recommended docstring structure for **new modules**.
- `tests/test_cli.py`: Comprehensive CLI **tests** using Typer’s CliRunner, pytest.mark.parametrize, and unittest.mock.patch.
- `scripts/template.py`: A template for **“directly executable scripts”** (includes a shebang).

Specifically note and use the templates.

- **`src/<your_pkg>/utils/template.py`** is a suggested “module docstring skeleton” (purpose, API, inputs, errors, security, etc.). Copy it when creating new modules.
- **`scripts/template.py`** is a suggested “executable script skeleton” (with shebang) that imports and calls into the package. Scripts should remain thin.

Make sure you are familiar with the [`poetrycli` Features explained](#poetrycli-features-explained) for this project so you understand the philosophy behind developing for the structure here.

### Development Setup

#### *Requirements (TODO)*

#### Install Python

Here is a suggested recipe to install an arbitrary Python version on **Linux**:

```sh
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install git python3 python3-dev python3-venv build-essential software-properties-common

sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.12  # or python3.13 or python3.14 - TODO: pick a version
```

and on **Mac**:

```sh
brew update
brew upgrade
brew cleanup -s

brew install git python@3.12  # or python3.13 or python3.14 - TODO: pick a version
```

#### Install Poetry (recommended: `pipx`)

[Poetry reference.](https://python-poetry.org/docs/cli/)

Install `pipx` (if you don’t have it):

```sh
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

If you previously had **Poetry** installed, but ***not*** through `pipx` make sure to remove it first: `brew uninstall poetry` (mac) / `sudo apt-get remove python3-poetry` (linux). You should install Poetry with `pipx` and configure poetry to create `.venv/` locally. This keeps Poetry isolated from project virtual environments and python for the environments is isolated from python for Poetry. Do:

```sh
pipx install poetry
poetry --version
```

If you will use [PyPI](https://pypi.org/) to publish:

```sh
poetry config pypi-token.pypi <TOKEN>  # add your personal PyPI project token, if any
```

#### Make sure `.venv` is local

This template expects a project-local virtual environment at `./.venv` (VSCode settings assume it, for example).

```sh
poetry config virtualenvs.in-project true
```

#### Get the repository

```sh
git clone https://github.com/balparda/poetrycli.git poetrycli  # TODO: change to your project's repo
cd poetrycli
```

#### Create environment and install dependencies

From the repository root:

```sh
poetry env use python3.12  # creates the .venv with the correct Python version - TODO: pick correct Python version
poetry sync                # sync env to project's poetry.lock file
poetry env info            # no-op: just to check that environment looks good
poetry check               # no-op: make sure all pyproject.toml fields are being used correctly

poetry run mycli --help    # simple test if everything loaded OK
make ci                    # should pass OK on clean repo
```

To activate and use the environment do:

```sh
poetry env activate        # (optional) will print activation command for environment, but you can just use:
source .venv/bin/activate  # because .venv SHOULD BE LOCAL
...
pytest -vvv  # for example, or other commands you want to execute in-environment
...
deactivate  # to close environment
```

#### Optional: VSCode setup

This repo ships a `.vscode/settings.json` configured to:

- use `./.venv/bin/python`
- run `pytest`
- use **Ruff** as formatter
- disable deprecated pylint/flake8 integrations
- configure Google-style docstrings via **autoDocstring**
- use **Code Spell Checker**

Recommended VSCode extensions:

- Python (`ms-python.python`)
- Python Environments (`ms-python.vscode-python-envs`)
- Python Debugger (`ms-python.debugpy`)
- Pylance (`ms-python.vscode-pylance`)
- Mypy Type Checker (`ms-python.mypy-type-checker`)
- Ruff (`charliermarsh.ruff`)
- autoDocstring – Python Docstring Generator (`njpwerner.autodocstring`)
- Code Spell Checker (`streetsidesoftware.code-spell-checker`)
- markdownlint (`davidanson.vscode-markdownlint`)
- Markdown All in One (`yzhang.markdown-all-in-one`) - helps maintain this `README.md` table of contents
- Markdown Preview Enhanced (`shd101wyy.markdown-preview-enhanced`, optional)
- GitHub Copilot (`github.copilot`) - AI assistant; reads `.github/copilot-instructions.md` for project-specific coding conventions (indentation, naming, workflow)

### *Build (TODO)*

```sh
<build command>
```

### *Run locally (TODO)*

```sh
<project> --help
<run-from-source command>
```

### Testing

#### Unit tests / Coverage

```sh
make test               # plain test run, no integration tests
make integration        # run the integration tests
poetry run pytest -vvv  # verbose test run, includes integration tests

make cov  # coverage run, equivalent to: poetry run pytest --cov=src --cov-report=term-missing
```

A test can be marked with a "tag" by just adding a decorator:

```py
@pytest.mark.slow
def test_foo_method() -> None:
  """Test."""
  ...
```

These tags, like `slow` above are defined in `pyproject.toml`, in section `[tool.pytest.ini_options.markers]`, and you can define your own there. The ones already defined are:

| Tag | Meaning |
| --- | --- |
| `slow` | test is slow (> 1s) |
| `flaky` | AVOID! - test is known to be flaky |
| `stochastic` | test is capable of failing (even if very unlikely) |

You can use them to filter tests, for example:

```sh
poetry run pytest -vvv -m slow  # run only the slow tests
```

You can find the slowest tests by running (example suggestions):

```sh
poetry run pytest -vvv -q --durations=20
poetry run pytest -vvv -q --durations=20 -m "not slow"  # find unknown slow methods
poetry run pytest -vvv -q --durations=20 -m slow        # check methods marked `slow` are in fact slow
```

You can search for flaky tests by running `make flakes`, which runs all tests 100 times. Or you can do more, like in the example:

```sh
make flakes  # equivalent to: poetry run pytest --flake-finder --flake-runs=100 -q tests
poetry run pytest --flake-finder --flake-runs=10000 -m "not slow"
```

#### Instrumenting your code

You can instrument your code to find bottlenecks:

```sh
$ source .venv/bin/activate
$ which mycli
/path/to/.venv/bin/mycli  # <== place this in the command below:
$ pyinstrument -r html -o output1.html -- /path/to/.venv/bin/mycli <your-cli-command> <your-cli-flags>
$ deactivate
```

This will save a file `output1.html` to the project directory with the timings for all method calls. Make sure to **cleanup** these html files later.

#### Integration / e2e tests

Integration tests validate packaging and the installed console script by:

- building a wheel from the repository
- installing that wheel into a fresh temporary virtualenv
- running the installed console script(s) to verify behavior (for example, `--version` and basic commands)

The canonical integration test is [tests_integration/test_installed_cli.py](tests_integration/test_installed_cli.py). It uses helpers from `transcrypto.utils.config` to simplify the workflow:

- `EnsureAndInstallWheel(repo_root, tmp_path, expected_version, app_names)` — builds the wheel and installs it into a temporary venv, returning the venv python and `bin` directory.
- `EnsureConsoleScriptsPrintExpectedVersion(vpy, bin_dir, expected_version, app_names)` — verifies the console scripts exist and that `--version` prints the expected version.
- `CallGetConfigDirFromVEnv(vpy, app_name)` — calls the installed CLI inside the venv to find its data/config directory (used for cleanup/isolation).

Tests in this suite are marked with `pytest.mark.integration`.

Run the integration tests with:

```sh
# Run only integration-marked tests (recommended)
poetry run pytest -m integration -q

# Or run the full integration target (equivalent)
make integration
```

Notes:

- These tests are slower and require `poetry`/venv support on the host system.
- Keep the `_APP_NAME` / `_APP_NAMES` constants in the test aligned with your package and console-script names.
- Use `--no-color` in assertions to avoid ANSI escape sequences when checking output.

#### *Golden tests for CLI output (TODO)*

- *Human output:*
- *JSON output:*

### Linting / formatting / static analysis

```sh
make lint  # equivalent to: poetry run ruff check .
make fmt   # equivalent to: poetry run ruff format .
```

To check formatting without rewriting:

```sh
poetry run ruff format --check .
```

#### Type checking

```sh
make type  # equivalent to: poetry run mypy src tests tests_integration
```

(Pyright is primarily for editor-time; MyPy is what CI enforces.)

### *Documentation updates (TODO)*

- *How docs are built: \<mkdocs/docusaurus/sphinx/etc.\>*
- *CLI reference generation:*

### Versioning and releases

Make sure you are familiar with the [`poetrycli` Features explained](#poetrycli-features-explained) for this project so you understand the philosophy behind developing for the structure here.

#### Versioning scheme

This project follows a pragmatic versioning approach:

- **Patch**: bug fixes / docs / small improvements.
- **Minor**: new template features or non-breaking developer workflow changes.
- **Major**: breaking template changes (e.g., required file/command renames).

See: [CHANGELOG.md](CHANGELOG.md)

#### Updating versions

##### Bump project version (patch/minor/major)

Poetry can bump versions:

```sh
# bump the version!
poetry version minor  # updates 1.6 to 1.7, for example
# or:
poetry version patch  # updates 1.6 to 1.6.1
# or:
poetry version <version-number>
# (also updates `pyproject.toml` and `poetry.lock`)
```

This updates `[project].version` in `pyproject.toml`. **Remember to also update `src/<your_pkg>/__init__.py` to match (this repo gets/prints `__version__` from there)!**

##### Update dependency versions

The project has a [**dependabot**](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/dependabot-quickstart-guide) config file in `.github/dependabot.yaml` that weekly (defaulting to Tuesdays) scans both Github actions and the project dependencies and creates PRs to update them.

To update `poetry.lock` file to more current versions do `poetry update`, it will ignore the current lock, update, and rewrite the `poetry.lock` file. If you have cache problems `poetry cache clear PyPI --all` will clean it.

To add a new dependency you should do:

```sh
poetry add "pkg>=1.2.3"  # regenerates lock, updates env (adds dep to prod code)
poetry add -G dev "pkg>=1.2.3"  # adds dep to dev code ("group" dev)
# also remember: "pkg@^1.2.3" = latest 1.* ; "pkg@~1.2.3" = latest 1.2.* ; "pkg@1.2.3" exact
```

Keep tool versions aligned. Remember to check your diffs before submitting (especially `poetry.lock`) to avoid surprises!

##### Exporting the `requirements.txt` file

This template does not generate `requirements.txt` automatically (Poetry uses `poetry.lock`). If you need a `requirements.txt` for Docker/legacy tooling, use Poetry’s export plugin (`poetry-plugin-export`) by simply running:

```sh
make req  # or: poetry export --format requirements.txt --without-hashes --output requirements.txt
```

##### CI and docs

Make sure to run `make docs` or even better `make ci`. Both will update the CLI markdown docs and `requirements.txt` automatically.

##### Git tag and commit

Publish to GIT, including a TAG:

```sh
git commit -a -m "release version 0.1.0"
git tag 0.1.0
git push
git push --tags
```

##### Publish to PyPI

If you already have your PyPI token registered with Poetry (see [Install Poetry](#install-poetry-recommended-pipx)) then just:

```sh
poetry build
poetry publish
```

Remember to update [CHANGELOG.md](CHANGELOG.md).

### *Contributing (TODO)*

- *See `CONTRIBUTING.md*`
- *Code of conduct: `CODE_OF_CONDUCT.md`*

## Security

Please refer to the security policy in [SECURITY.md](SECURITY.md) for supported versions and how to report vulnerabilities.

The project has a [**codeql**](https://codeql.github.com/docs/) config file in `.github/workflows/codeql.yaml` that weekly (defaulting to Fridays) scans the project for code quality and security issues. It will also run on all commits. Github security issues will be opened in the project if anything is found.

### *Supply chain (TODO)*

- *Dependency pinning:*
- *Signed releases: \<GPG/cosign\>*
- *SBOM: \<available? where?\>*

## *Reliability (TODO)*

### *Operational guidance (TODO)*

- *Recommended timeouts:*
- *Retry behavior:*
- *Idempotency:*

### *Running in automation (TODO)*

- *CI usage examples*
- *Cron usage examples*
- *Non-interactive flags (`--yes`, `--json`, `--quiet`)*

### *Failure modes (TODO)*

- *Network failures:*
- *Partial failures: \<exit code + output behavior\>*
- *Rate limiting:*

## *Troubleshooting (TODO)*

### *Enable debug output (TODO)*

```sh
<project> --verbose
<project> --log-level debug <command>
```

### *Common issues (TODO)*

- *Problem:*
*Cause:*
*Fix:*

- *Problem:*
*Fix:*

### *Collect diagnostics (TODO)*

```sh
<project> debug report --output diagnostics.zip
```

## *FAQ (TODO)*

### *FAQ Section I (TODO)*

#### *Why does `<project>` need `<permission/dependency>`? (TODO)*

*\<Answer\>*

#### *How do I migrate from version X to Y? (TODO)*

*\<Answer + link to migration guide\>*

#### *How stable is the JSON output? (TODO)*

*\<Answer + schema contract\>*

## *Glossary (TODO)*

- A
- B

## Appendix **I**: Using the `poetrycli` template

### New Projects

If you are starting a new CLI app based on [`poetrycli`](https://github.com/balparda/poetrycli), then these are the steps to follow. Know that if you just used the `poetrycli` template to start a new repository then your files in this repo include many `# TODO:` markers to guide you on where to change the files.

**(Note there is also an [Appendix **II**: Template Checklist](#appendix-ii-template-checklist-turning-poetrycli-into-your-new-cli-project-in-12-steps))**

The suggested instructions to start with is:

#### Rename the package + CLI entrypoint

1. Rename the package directory: `src/mycli/` → `src/<your_pkg>/`

1. Update the script entrypoint in `pyproject.toml`:

```toml
[tool.poetry.scripts]
mycli = "mycli.cli:app" → <yourcli> = "<your_pkg>.cli:app"
```

1. Update Poetry packaging (change `mycli` to your package name):

```toml
[tool.poetry]
packages = [{ include = "<your_pkg>", from = "src" }]
```

1. Update the project metadata:

```toml
[project]
name = "<your_pkg>" → your PyPI/project name
also change version, description, authors, classifiers

[project.urls]
change GitHub URLs and others
```

1. Update `src/<your_pkg>/__init__.py`: keep `__version__ = "..."` in sync with `[project].version`.

#### Update app name used for config paths

The template uses `transcrypto.util.config` for configuration management. To set your app name, update it wherever you initialize configuration in your CLI:

```py
from transcrypto.util import config as cfg

# Initialize config with your app name
config = cfg.Config(app_name='<your_pkg>', config_name='<config_file_name>')
```

This ensures config files are stored in OS-specific directories. Also edit `Makefile` replacing occurrences of `mycli`.

#### Pick a Python version (skip if 3.12 is good)

This template currently targets **Python 3.12** (or **Python 3.13** or **Python 3.14**). It may possibly work with more versions, but these ones the authors have tested. If you want a different Python version, update the “Python version cluster” in multiple places, *at least* update all of these:

- `pyproject.toml`:
  - [project.classifiers] (e.g., "Programming Language :: Python :: 3.12")
  - [project.requires-python] (e.g., ">=3.12")
  - [tool.poetry.dependencies].python (e.g., "^3.12")
  - [tool.ruff].target-version (e.g., "py312")
  - [tool.mypy].python_version (e.g., "3.12")
  - [tool.pyright].pythonVersion (e.g., "3.12")
- `.github/workflows/ci.yaml`: matrix `python-version`
- `README.md` (this file): Python version references in install instructions

After changing versions, re-create your `.venv` (if you have already created it):

```sh
rm -rf .venv
make  # equivalent to: poetry install
```

#### Customize CLI banner + top-level options

In `src/<your_pkg>/cli.py`, `Main()` prints a banner and logs an example warning:

- Replace banner text (`“<your_pkg>”`, email, etc.)
- Remove example options you don’t want (`--foo`, `--bar`) or rename them into real app options

#### Optional: adjust style/lint strictness

[Ruff rule reference](https://docs.astral.sh/ruff/rules/). This template currently uses:

```toml
[tool.ruff.lint]
select = ["ALL"]
ignore = [...a few specific ones...]
```

If that’s too strict for your team, you can:

- Keep `ALL` and expand the `ignore = [...]` list, or
- Remove `ALL` and select only the groups you want that come commented out by default.

### `poetrycli` Features explained

This documents how to use [`poetrycli`](https://github.com/balparda/poetrycli)-derived projects. Some things here are a result of how this project is organized and meant to be used. Others may be good ideas regardless.

Before continuing it makes sense to make sure you are familiar with the [Development Instructions](#development-instructions) and have gone over the [Development Setup](#development-setup) and understand the [File structure](#file-structure) of the project.

#### CLI design (Typer)

The CLI is defined as a **Typer** application object:

```py
app = typer.Typer(add_completion=True, no_args_is_help=True)
```

A single callback works as the global “constructor”:

```py
@app.callback(invoke_without_command=True)
```

supports out-of-the-box:

- `--version` flag (prints version and exits)
- `-v/--verbose` (verbosity counter)
- example options `--foo` and `--bar`

Verbosity is an integer counter:

- no `-v`: verbosity = 0 → `ERROR` level logging
- `-v`: verbosity = 1 → `WARNING` level logging
- `-vv`: verbosity = 2 → `INFO` level logging
- `-vvv`: verbosity >= 3 → `DEBUG` level logging

The callback calls:

```py
console = cli_logging.InitLogging(verbose)
```

That configures logging and installs a shared **Rich** console singleton. Commands included out-of-the-box:

- `poetry run <yourcli> config-path` → prints the config file path
- `poetry run <yourcli> hello [name]` → prints `Hello, <name>!`

Subcommand **example** group included:

- `poetry run <yourcli> random num --min 0 --max 100`
- `poetry run <yourcli> random str --length 16 [--alphabet ...]`

This is implemented via:

```py
_random_app = typer.Typer(no_args_is_help=True)
app.add_typer(_random_app, name='random', help='Random utilities.')
```

#### Rich logging + Console singleton (`transcrypto`)

Logging and console singleton functionality is provided by the **transcrypto** library (`transcrypto.utils.logging`). `Console()` returns the global singleton if initialized, otherwise returns a fallback `rich.console.Console()`. This allows any command do:

```py
from transcrypto.utils import logging as cli_logging

console = cli_logging.Console()
console.print(...)
```

without worrying whether logging was initialized, which should be done only once:

```py
InitLogging(verbosity, include_process=False, soft_wrap=False)
```

this:

- creates a **Rich** `Console(soft_wrap=...)`
- configures Python logging with `RichHandler`
- sets logging level based on verbosity
- sets `force=True` in `logging.basicConfig(...)` to override prior config
- normalizes logging for “common providers” (uvicorn/gunicorn/etc.) to propagate into your handler
- logs a startup info line: Logging initialized at level ...

*Testing note:* For tests that rely on fresh logging init, call `ResetConsole()` in an `autouse` fixture (there is an example in `tests/test_cli.py`). This prevents cross-test leakage of the singleton.

#### Separation of CLI and business logic

Commands call into `src/<your_pkg>/core/example.py`, which should contain your business logic. Why this pattern is useful:

- CLI remains thin and testable
- Business logic can be tested independently (and reused elsewhere)
- Mocking business logic is cleaner

#### Config management (`transcrypto.util.config`)

This template uses `transcrypto.util.config` for cross-platform configuration management. Basic usage:

```py
from transcrypto.util import config as app_config

# Initialize config with your app name
config = app_config.Config('mycli', 'myconfig.bin')

config_dir = config.dir  # Path object to config directory
config_path = config.path  # Path object to config file ('myconfig.bin')

data = config.DeSerialize()  # loads default config object as a python object
config.Serialize({'key': 'new_value'})  # saves python object to default config file
```

The `Serialize`/`DeSerialize` methods are powerful `transcrypto` primitives that allow for, for example, strong encryption of your configs.

#### Strict linting + formatting with Ruff (pyproject.toml)

This template uses Ruff for both: `ruff check` (lint) and `ruff format` (format). Key formatting opinions:

```toml
indent-width = 2
quote-style = "single"
docstring-code-format = true
```

Lint configuration by default selects `ALL` rules, then ignores specific rules that conflict with this template’s choices. Notable ignores:

- `N802`: allow PascalCase for function/method names
- `E111`, `E114`: allow 2-space indentation
- formatter-conflict ignores: `D203`, `D213`, `COM812`
- `TC002`: allow “third-party import only used for typing” patterns
- a few practical exceptions for CLI ergonomics and TODO policy

If you want a calmer baseline, remove `"ALL"` and explicitly select rule groups.

#### Typing checks (MyPy + Pyright)

This repo supports strict typing in three ways:

- **MyPy**: configured via `[tool.mypy]` in `pyproject.toml` (`strict = true`, plus many explicit strict flags)
- **Pyright/Pylance**: configured via `[tool.pyright]` in `pyproject.toml` (`typeCheckingMode = "strict"`)
- **typeguard**: configured in `[tool.pytest.ini_options.typeguard-*]` in `pyproject.toml`

VSCode uses Pylance by default, so you get IDE-time feedback and CI-time enforcement. `typeguard` will be active during tests by default. You can suppress type checking in specific tests by invoking `@typeguard.suppress_type_checks` decorator or context:

```py
import typeguard

@typeguard.suppress_type_checks
def test_crazy_types() -> None:
  # whole method is exempt from typeguard

def test_less_crazy_types_test() -> None:
  # this part of test is type-checked
  with typeguard.suppress_type_checks():
    # this part is not type checked
```

#### Tests + coverage (`pytest`)

Tests run with `pytest`, and CI runs coverage:

```sh
make cov  # equivalent to: poetry run pytest --cov=src --cov-report=term-missing
```

Coverage configuration in `pyproject.toml` omits:

- `*/__init__.py`
- `*/__main__.py`
- `*/template.py`

Rationale: these files should remain “thin” and are usually not meaningful coverage targets.

#### Pre-commit checks

File `.pre-commit-config.yaml` defines pre-submit hooks:

```sh
poetry run pre-commit install
```

Run on all files:

```sh
make precommit  # equivalent to: poetry run pre-commit run --all-files
```

#### CI (GitHub Actions)

File `.github/workflows/ci.yaml` runs on pushes and PRs:

- `poetry install`
- `ruff check .`
- `ruff format --check .`
- `mypy src tests tests_integration`
- `pytest --cov=src --cov-report=term-missing`

CI is the “source of truth” that the template remains clean.

## Appendix **II**: Template Checklist: turning `poetrycli` into your new CLI project in 12 steps

This checklist is designed to be **mechanical**: do every step, run the commands, and you’ll end up with a renamed, clean, working project.

### 0: Prerequisites (one-time per machine)

- Install **Python 3.12** (or your chosen target version).
- Install Poetry via `pipx`:

```sh
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install poetry
```

- Configure Poetry to put the virtualenv in-project:

```sh
poetry config virtualenvs.in-project true
```

### 1: Decide your identity

Choose:

- **project name** (PyPI name): e.g. `coolcli`
- **package name** (import name): e.g. `coolcli` (usually same as project name)
- **CLI command** name: e.g. `cool`
- **app config name**: e.g. `coolcli` (used for config directories)

### 2: Rename the Python package directory

1. Rename the package folder: `src/mycli/` → `src/<your_pkg>/`
1. Search/replace imports:

   - `from mycli ...` → `from <your_pkg> ...`
   - `import mycli ...` → `import <your_pkg> ...`

1. Update tests that import the CLI app (e.g. `tests/test_cli.py`).

### 3: Update `pyproject.toml` (the big one)

Open `pyproject.toml` and update all the `# TODO:` markers.

### 3.1 Required metadata

Under `[project]`:

- `name = "mycli"` → your project name
- `version = "0.1.0"` → your initial version
- `description = ...`
- `authors = [...]`
- `license = ...`
- `classifiers` (especially the Python version classifier)
- `requires-python = ">=3.12"` (or your chosen version)
- `license-files = ["LICENSE"]` (keep unless you change licensing docs)

Under `[project.urls]`:

- Homepage/Repository/Issues/Changelog → update to your repo URLs

#### 3.2: Poetry packaging + entrypoint wiring

- Under `[tool.poetry]`: `packages = [{ include = "mycli", from = "src" }]` → update `include` to your package name
- Under `[tool.poetry.scripts]`: `mycli = "mycli.cli:app"` → update both sides:
  - CLI command name (left)
  - import path (right) to match your renamed package
- Do the exact same under `[project.scripts]`
- In `.github/workflows/ci.yaml` update `mycli` name in `typeguard-packages`

#### 3.3: If you change Python version…

There are **at least six** places to update (the file literally warns you). Update all of:

- `[project.classifiers]` → `Programming Language :: Python :: 3.xx`
- `[project.requires-python]`
- `[tool.poetry.dependencies] python = ...`
- `[tool.ruff] target-version = "py3xx"`
- `[tool.mypy] python_version = "3.xx"`
- `[tool.pyright] pythonVersion = "3.xx"`

Also update:

- `.github/workflows/ci.yaml` python matrix version.
- README references

### 4: Sync the runtime `__version__`

The CLI prints `__version__` from your package. Update:

- `src/<your_pkg>/__init__.py` → `__version__ = "<same as pyproject.toml>"`

Update tests that assert version output (there is a version test).

### 5: Update config app name

The template uses `transcrypto.util.config` for configuration. Update the `app_name` parameter wherever you initialize config in your CLI code:

```py
from transcrypto.util import config as cfg

config = cfg.Config('mycli', 'config.bin')  # ← change 'mycli' to your app name
```

This affects where the OS-native config directory lives (e.g., `~/.config/<app_name>/` on Linux).

Also go into `Makefile` and replace occurrences of `mycli`. Same thing with the integration tests, go into `tests_integration/test_installed_cli.py` and change the app and CLI name there.

### 6: Review lint policy (Ruff)

This template uses `select = ["ALL"]` and then ignores a curated list. Decide:

- Keep `ALL` (recommended if you like strictness), or
- Replace `ALL` with a smaller `select` list.

If you want to keep *PascalCase* methods:

- Ensure `N802` remains ignored (that’s the “function name should be lowercase” complaint).

### 7: Run the full validation suite (before first commit)

From repo root:

```bash
make     # equivalent to: poetry install
make ci  # runs complete CI pipeline
```

Expected:

- Pytest: green
- Integration: green
- Ruff: no diffs after `ruff format .`
- Ruff lint: clean
- MyPy: clean
- Coverage: acceptable (note: init/template files are omitted by design)  ￼

### 8: First release workflow (suggested)

1. Ensure version is correct: confirm in `pyproject.toml` + `__init__.py`
1. Run the full validation suite ([Step 7](#7-run-the-full-validation-suite-before-first-commit))
1. Commit, tag, and publish per your release process

### 9:  Update README

- Delete this "Appendix II" from the docs
- You probably want to at least partially keep the rest of the documentation
- Look for TODOs and *ITALICS* for places to edit
- Not all topics and sections are relevant for every project: pick the ones you want, and maybe delete the rest
- rename “mycli” references, usage examples, repo links
- `CHANGELOG.md` (reset it to your new project)
- `SECURITY.md` (make sure contact details are up to date)
- `LICENSE` file and [README header](#license) if your project changes license/ownership

### 10: Customize the CLI global flags

In `src/<your_pkg>/cli.py`, update:

- the `MyCLIConfig` structure
- global options in `Main()` (you probably want to leave `--version`, `--verbose` and `--color`)
- `help=` and `epilog=` for your commands and options

### 11: “Cleanup”

Once your project is real:

- Remove or repurpose the example commands (Hello, random, etc.)
- Remove `scripts/template.py` if you don’t use direct executable scripts
- Remove `src/<pkg>/utils/template.py` once everyone knows the pattern
- Tighten or relax Ruff ignores based on your team’s preferences

### 12: Done: Start building your project

*Congratulations! You should have a working project.* Next steps suggestions:

- Edit this `README.md` with information specific to your project.
- Start building your CLI logic, replacing the toy one provided here.
- Add unit tests for core logic and CLI wiring (use Typer's `CliRunner`).
- Add and maintain integration tests that validate packaging and the installed console script.

---

*Thanks!* - Daniel Balparda
