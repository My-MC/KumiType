PYTHON ?= uv run --locked python
BUILD_DIR ?= build
DIST_DIR ?= dist
JOBS ?= auto
HARFBUZZ ?= hb-shape

.PHONY: install test lint docker fetch fonts audit validate package preview verify
install:
	uv python install
	uv sync --locked --extra dev
test:
	$(PYTHON) -m pytest
lint:
	$(PYTHON) -m ruff check src tests scripts
docker:
	docker build -t kumitype-builder:local .
fetch:
	$(PYTHON) -m kumitype.cli fetch
fonts:
	$(PYTHON) -m kumitype.cli build-all --jobs $(JOBS) --output-dir "$(BUILD_DIR)"
audit:
	$(PYTHON) -m kumitype.cli audit --build-dir "$(BUILD_DIR)"
validate:
	$(PYTHON) -m kumitype.cli validate --all --build-dir "$(BUILD_DIR)" --harfbuzz "$(HARFBUZZ)" --require-harfbuzz
verify: audit
	$(MAKE) validate
package:
	$(PYTHON) -m kumitype.cli package --all --build-dir "$(BUILD_DIR)" --output-dir "$(DIST_DIR)"
preview:
	$(PYTHON) scripts/generate-preview.py --build-dir "$(BUILD_DIR)"
