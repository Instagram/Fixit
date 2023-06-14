
.PHONY: venv
venv:
	hatch env remove all
	hatch env create all
	ln -sf "$$(hatch env find all)" .venv
	@echo "Run \`source .venv/bin/activate\` to activate virtualenv"

.PHONY: format
format:
	hatch run lint:fix

.PHONY: test
test:
	hatch run test
	hatch run typecheck

.PHONY: lint
lint:
	hatch run lint:check

.PHONY: html
html: docs/*
	hatch run docs:build

.PHONY: distclean
distclean:
	hatch env prune
	rm -f .venv
