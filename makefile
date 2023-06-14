
.venv:
	hatch env prune
	hatch env create
	ln -sf "$(hatch env find all)" .venv

.PHONY: venv
venv: .venv
	@echo "Run \`hatch shell\` to create a new shell in the venv or \`source `hatch env find`/bin/activate\` to activate it in the current shell"

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
