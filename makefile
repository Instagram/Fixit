
.venv:
	python -m venv --clear .venv

.PHONY: venv
venv: .venv
	.venv/bin/python -m pip install -U pip
	.venv/bin/python -m pip install -r requirements-dev.txt
	.venv/bin/python -m pip install -r requirements.txt
	.venv/bin/python -m pip install -e .
	@echo "Run \`source .venv/bin/activate\` to activate venv"

.PHONY: format
format:
	python -m ufmt format fixit

.PHONY: test
test:
	python -m fixit.tests

.PHONY: lint
lint:
	python -m flake8 fixit
	python -m ufmt check fixit

.PHONY: html
html: docs/*
	sphinx-build -a -b html docs html

.PHONY: distclean
distclean:
	rm -rf .venv
