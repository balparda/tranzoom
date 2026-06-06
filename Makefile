# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0

.PHONY: install init fmt lint type test integration cov flakes cython clean-cython precommit docs req build ci

install:
	poetry install

init:
	poetry config virtualenvs.in-project true
	poetry env use python3.12
	poetry sync
	poetry run python build_ext.py build_ext --inplace || echo "Cython build skipped (compiler/libs missing)"
	poetry run tranz --help

fmt:
	poetry run ruff format .

lint:
	poetry run ruff check .

type:
	poetry run mypy src tests tests_integration

test:
	poetry run pytest -vvvv -q tests

integration:
	poetry run pytest -vvvv -q tests_integration

cov:
	poetry run pytest --typeguard-packages=tranzoom --cov=src --cov-report=term-missing -q tests

flakes:
	poetry run pytest --flake-finder --flake-runs=100 -q tests

cython:
	@echo "Building Cython extensions"
	poetry run scripts/build_extensions.py
	@echo "Done: fractal* extensions built"

clean-cython:
	@echo "Removing Cython build artifacts: c/so/pyd/dylib files and build/ directory"
	rm -rf build/ src/tranzoom/core/*.c src/tranzoom/core/*.so src/tranzoom/core/*.pyd src/tranzoom/core/*.dylib

precommit:
	poetry run pre-commit run --all-files

docs:
	@echo "Generating tranz.md"
	poetry run tranz markdown > tranz.md

req:
	poetry export --format requirements.txt --without-hashes --output requirements.txt

build:
	poetry build --clean -vv

ci: clean-cython cython cov integration precommit docs req build
	@echo "CI checks passed! Generated docs & requirements.txt."
