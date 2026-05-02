# Copilot Instructions

This is a python/poetry-based project template.

## Running Code and Tests

- All non-`make` commands should be run from the Poetry environment: `poetry run <command>`
- To run an app: `poetry run <app_command> <flags> <args>`
- To run tests on a file: `poetry run pytest tests/<file>_test.py`

## Code Standards

### Required Before Each Commit

- Run `make test` to ensure all tests pass
- Run `make ci` runs everything, to ensure integration tests and linters pass, also to generate auto-generated code
- When adding new functionality, make sure you update the `README.md` file both in how to use the new functionality but also remembering this is a template project, meant to be copied and modified by users so be clear on what is template code and what is example code, and how users should modify it for their own use
- Remember to update `CHANGELOG.md` too

### Styling

- Zero lint errors or warnings
- Try to always keep line length under 100 characters
- All files must have a license header (e.g., `# SPDX-License-Identifier: Apache-2.0` for Python files, `<!-- SPDX-License-Identifier: Apache-2.0 -->` for Markdown files, etc)

- Use Python conventions, but note that:
  - Use 2 spaces for indentation
  - Always prefer single quotes (`'`) but use double quotes in docstrings (`"""`)
  - Google-style docstrings with complete type annotations in the `Args` and `Returns` sections
  - Methods and Classes must be named in CamelCase; test methods can be snake_case but must start with `test_`, but I prefer test methods to be in CamelCase as well as `testSomething`
  - Start private Classes, Methods, and fields with an underscore (`_`). Only make public what is strictly necessary, the rest keep private
  - Always use `from __future__ import annotations`
  - MyPy strict + Pyright strict + typeguard everywhere. Always add complete type annotations. Avoid creating typeguard exceptions in tests as much as possible.
  - Testfiles are `<module>_test.py`, NOT `test_<module>.py` and tests mirror source structure
  - Project selects `"ALL"` Ruff rules and adds just a few exceptions
  - Never import except at the top, not even for tests, not even for type checking: ALL imports at the top always (only acceptable exception is CLI modules imports to register commands)

### CLI Architecture

- CLI is a **Typer** app: `app = typer.Typer(...)` in the main app module
- Global callback (`@app.callback`) handles `--version`, `--verbose`, `--color` and creates a shared config object stored in `ctx.obj`
- Every command receives `ctx: click.Context` and reads config via `config = ctx.obj`
- Every command is decorated with `@clibase.CLIErrorGuard` (from `transcrypto.cli.clibase`)
- Subcommand groups use a separate `typer.Typer()` added via `app.add_typer(...)`
- CLI modules are imported at the bottom of the main app file to register commands

### `transcrypto`

We try to use `transcrypto` utilities and helpers as much as possible:

- `from transcrypto.utils import logging as cli_logging` — Rich console singleton, `InitLogging()`, `Console()`, `ResetConsole()`
  - After this initialization, use `cli_logging.Console().print(...)` for all console output and plain `import logging; logging.info(...)` for all logging output
- `from transcrypto.utils import config as app_config` — config management, `InitConfig()`, `ResetConfig()`
- `from transcrypto.cli import clibase` — `CLIErrorGuard`, `CLIConfig`, `GenerateTyperHelpMarkdown()`

- Try to use `transcrypto` when possible, including for:
  - Base (`transcrypto.utils.base`): lots of conversions bytes/int/hex/str/etc
  - Human-friendly outputs: `transcrypto.utils.human`
  - Saving/loading configs, including encrypted: `transcrypto.utils.config`
  - Random: `transcrypto.utils.saferandom`
  - Simple statistical results: `transcrypto.utils.stats`
  - Timing: `transcrypto.utils.timer`
  - Encryption: `transcrypto.core.key` and `transcrypto.core.aes` are good starting points

## Testing Patterns

- Test files mirror source: `src/<pkg>/cli/foo.py` → `tests/cli/foo_test.py`
- Shared test helpers (e.g., `CallCLI()`, `PrintedValue()`) live in `tests/<app>_test.py` and are imported by sub-tests
- Use `@pytest.fixture(autouse=True)` to reset singletons (`cli_logging.ResetConsole()`, `app_config.ResetConfig()`) before each test
- CLI tests use `typer.testing.CliRunner().invoke(app, args)` for real CLI wiring
- Use `@pytest.mark.parametrize` heavily for data-driven tests
- Use `unittest.mock.patch` to mock `transcrypto.utils.logging.rich_console.Console` and assert on `console.print(...)` calls
- Mark tests with `@pytest.mark.slow`, `@pytest.mark.stochastic`, `@pytest.mark.integration` as appropriate
- Integration tests (`tests_integration/`) build a wheel, install into a temp venv, and run the installed CLI

## Repository Structure

- `CHANGELOG.md`: latest changes/releases
- `Makefile`: commands for testing, linting, generating code, etc
- `<app>.md`: this are auto-generated CLI docs (by `make docs` or `make ci`)
- `pyproject.toml`: most important configurations live here
- `README.md`: main documentation
- `requirements.txt`: auto-generated file (by `make req` or `make ci`)
- `.github/`: Github configs and pipelines
- `.vscode/`: VSCode configs
- `scripts/`: Standalone scripts
- `src/<your_pkg>/`: Main source code
  - `src/<your_pkg>/__init__.py`: Version lives here (e.g., `__version__ = "0.1.0"`) and in `pyproject.toml` both
  - `src/<your_pkg>/<app>.py`: A CLI app entry point
  - `src/<your_pkg>/cli/`: CLI-related code
  - `src/<your_pkg>/core/`: Core logic and domain models
  - `src/<your_pkg>/utils/`: Utility functions and helpers
- `tests/`: Test files and test utilities
- `tests_integration/`: Integration test files
