.PHONY: lint

# Mesmos gates do job `lint` do CI. Requer actionlint e shellcheck no PATH
# (e `pip install pyyaml`): sem shellcheck o linter so avisa localmente.
lint:
	actionlint
	CI=1 python .github/scripts/lint-actions.py
