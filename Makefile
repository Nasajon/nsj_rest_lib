.PHONY: tests

include .env

ENV_VARS = $(shell cat .env)

env_setup:
	$(foreach v,$(ENV_VARS),$(eval export $(v)))

install_to_pkg:
	pip install build==1.2.2.post1
	pip install twine==6.1.0

build_pkg:
	python3 -m build

upload_pkg:
	python3 -m twine upload --skip-existing dist/*

publish_pkg: build_pkg upload_pkg

run: env_setup
	flask --app=src/nsj_rest_lib/wsgi.py run

tests: env_setup
	pytest -s tests/api/casos_de_teste

tests2: env_setup
	pytest -s tests/api/casos_de_teste/clientes/post