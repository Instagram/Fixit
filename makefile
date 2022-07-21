
.venv:
	python -m venv --clear .venv

venv: .venv
	.venv/bin/python -m pip install -U pip
	.venv/bin/python -m pip install -r requirements-dev.txt
	.venv/bin/python -m pip install -r requirements.txt
	@echo "Run \`source .venv/bin/activate\` to activate venv"

format:
	python -m ufmt format fixit

test:
	python -m fixit.tests

lint:
	python -m ufmt check fixit

distclean:
	rm -rf .venv
