# SPDX-FileCopyrightText: Copyright 2026 <balparda@github.com> & <BellaKeri@github.com>
# SPDX-License-Identifier: Apache-2.0

.PHONY: install fmt lint type test integration cov flakes precommit docs req ci cython clean-cython

install:
	poetry install

fmt:
	poetry run ruff format .

lint:
	poetry run ruff check .

type:
	poetry run mypy src tests tests_integration

test:
	poetry run pytest -q tests

integration:
	poetry run pytest -q tests_integration

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
	poetry export --format requirements.txt --without-hashes --output requirements.txt

ci: cov integration precommit docs req
	@echo "CI checks passed! Generated docs & requirements.txt."

cython:
	@echo "Building Cython extension"
	poetry run python build_ext.py build_ext --inplace
	@echo "Done. fractalfast extension built alongside src/tranzoom/core/fractalfast.py"

clean-cython:
	@echo "Removing Cython build artifacts"
	rm -rf build/ src/tranzoom/core/fractalfast.c src/tranzoom/core/fractalfast*.so src/tranzoom/core/fractalfast*.pyd
