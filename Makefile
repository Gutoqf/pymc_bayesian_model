.PHONY: init check_lint test

init:
	pip install -r requirements.txt

check_lint:
	pip install -r requirements.txt
	pip install -r lint-requirements.txt
	flake8 .
	isort --check-only .
	black --diff --check --fast .

test:
	pip install -r test-requirements.txt
	pytest tests