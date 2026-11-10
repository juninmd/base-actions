.PHONY: lint

# Mesmos gates do job `lint` do CI. Requer actionlint e shellcheck no PATH
# (e `pip install pyyaml zizmor`): sem shellcheck o linter so avisa localmente.
lint:
	actionlint
	CI=1 python .github/scripts/lint-actions.py
	shellcheck scripts/*.sh
	zizmor --offline --min-severity medium .
	python .github/scripts/test-comments-scan.py
