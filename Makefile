.PHONY: test check fixtures
test:
	.venv/bin/python -m pytest -q
check:
	.venv/bin/pip check
	.venv/bin/python -m compileall -q app scripts tests
	bash -n install.sh scripts/*.sh
fixtures:
	.venv/bin/python scripts/generate-fixtures.py tests/fixtures/generated
