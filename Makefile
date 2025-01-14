.PHONY: tests

include .env

ENV_VARS = $(shell cat .env)

env_setup:
	$(foreach v,$(ENV_VARS),$(eval export $(v)))

install_to_pkg:
	pip install build
	pip install twine

build_pkg:
	python -m build

upload_pkg:
	python -m twine upload --skip-existing dist/*

tests: env_setup
	pytest -s tests/api/casos_de_teste