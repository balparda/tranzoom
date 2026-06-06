# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0

.PHONY: install init fmt lint type test integration cov flakes precommit docs req clean-cython build ci

install:
	poetry install

init:
	@echo "Initializing Poetry environment with in-project virtualenv and Python 3.12"
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

precommit:
	poetry run pre-commit run --all-files

docs:
	@echo "Generating tranz.md"
	poetry run tranz markdown > tranz.md

req:
	@echo "Generating requirements.txt from Poetry dependencies"
	poetry export --format requirements.txt --without-hashes --output requirements.txt

clean-cython:
	@echo "Removing Cython build artifacts: c/so/pyd/dylib files and build/ directory"
	rm -rf build/ src/tranzoom/core/*.c src/tranzoom/core/*.so src/tranzoom/core/*.pyd src/tranzoom/core/*.dylib

build: clean-cython
	@echo "Building source and wheel distributions with Poetry"
	poetry build --clean -vv

ci: build cov integration precommit docs req build
	@echo "Success: Built. CI checks passed! Lint. Generated docs & requirements.txt."
