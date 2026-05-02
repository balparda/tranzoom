<!-- SPDX-FileCopyrightText: Copyright 2026 Daniel Balparda <balparda@github.com> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Changelog

All notable changes to this project will be documented in this file.

- [Changelog](#changelog)
  - [V.V.V - YYYY-MM-DD - Placeholder](#vvv---yyyy-mm-dd---placeholder)
  - [0.1.0 - 2026-01-17](#010---2026-01-17)

This project follows a pragmatic versioning approach:

- **Patch**: bug fixes / docs / small improvements.
- **Minor**: new template features or non-breaking developer workflow changes.
- **Major**: breaking template changes (e.g., required file/command renames).

***TODO***: *Template note: when you create a new project from this template, you should* ***reset*** *the changelog to reflect your new project’s history.*

## V.V.V - YYYY-MM-DD - Placeholder

- Added
  - Placeholder for future changes.

- Changed
  - Placeholder for future changes.

- Fixed
  - Placeholder for future changes.

## 0.1.0 - 2026-01-17

Initial public template release.

- Added
  - **Poetry + Python 3.12** base project (`pyproject.toml`) with local `.venv` workflow.
  - **Typer** CLI with:
    - Global constructor callback (`Main`) and `--version` option.
    - Example commands: `hello`, `config-path`.
    - Example subcommand group: `random num`, `random str`.
  - **Rich** logging integration with:
    - `InitLogging(verbosity)` and global `Console()` singleton access pattern.
  - **Cross-platform config path** helper using `platformdirs` (`resources/config.py`).
  - **Ruff** configured as:
    - formatter (2-space indentation, single quotes)
    - linter with `select = ["ALL"]` plus template-focused ignores (including allowing PascalCase for methods).
  - **Strict typing** with MyPy (`strict = true`) and Pyright (`typeCheckingMode = "strict"`).
  - **Pytest** suite with didactic examples, parametrize + patch, and CLI runner usage.
  - **pre-commit** hooks for Ruff + MyPy (pinned versions).
  - **GitHub Actions CI** running: lint, format check, typing, tests + coverage.

- Changed
  - N/A

- Fixed
  - N/A
