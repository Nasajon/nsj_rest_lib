install_to_pkg:
	pip install build
	pip install twine

build_pkg:
	python -m build

upload_pkg:
	python -m twine upload --skip-existing dist/*

tests:
	pytest -s tests/api/casos_de_teste