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

publish_pkg: build_pkg upload_pkg

run: env_setup
	flask --app=src/nsj_rest_lib/wsgi.py run

tests: env_setup
	pytest -s tests/api/casos_de_teste