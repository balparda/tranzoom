# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0

.PHONY: install init fmt lint type test integration cov flakes precommit docs req clean-cython timages demo build ci

install:
	poetry install

init:
	@echo "Initializing Poetry environment with in-project virtualenv and Python 3.14"
	poetry config virtualenvs.in-project true
	poetry env use python3.14
	poetry sync

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

timages:
	scripts/make_test_images.sh

demo:
	scripts/make_demo_images.sh

build: clean-cython
	@echo "Building source and wheel distributions with Poetry"
	poetry build --clean -vv

ci: timages build cov integration precommit docs req
	@echo "Success: Built. CI checks passed! Lint (precommit). Generated docs & requirements.txt."
