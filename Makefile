SHELL := /bin/bash
LAB ?= week01
PYTHON ?= .venv/bin/python

.PHONY: help venv validate config build start stop status reset test integration helper manager deploy rollback offline clean

help:
	@printf '%s\n' \
	  'make venv        Install development dependencies' \
	  'make validate    Validate manifests and Compose files' \
	  'make build       Build the selected lab images' \
	  'make start       Start the selected lab' \
	  'make stop        Stop the selected lab' \
	  'make status      Show lab status' \
	  'make reset       Reset the selected lab (keeps evidence)' \
	  'make test        Run all tests' \
	  'make integration Run integration tests only' \
	  'make helper      Run the privileged helper on a development socket' \
	  'make manager     Run the Lab Manager on 127.0.0.1:8080' \
	  'make deploy      Deploy the current version (DEST=/opt/iotlab)' \
	  'make rollback    Roll back to the previous release' \
	  'make offline     Create an offline bundle in dist/' \
	  'make clean       Remove local Python caches'

venv:
	python3 -m venv .venv
	.venv/bin/pip install -r tests/requirements-dev.txt

validate:
	scripts/verify.sh

config:
	docker compose -f labs/$(LAB)/docker-compose.yml config

build:
	scripts/lab-build.sh $(LAB)

start:
	scripts/lab-start.sh $(LAB)

stop:
	scripts/lab-stop.sh $(LAB)

status:
	scripts/lab-status.sh $(LAB)

reset:
	scripts/lab-reset.sh $(LAB) --yes

test:
	$(PYTHON) -m pytest tests

integration:
	$(PYTHON) -m pytest -m integration tests

helper:
	PYTHONPATH=. $(PYTHON) -m backend.helper.server --root . \
	  --socket /tmp/iotlab-helper.sock --allowed-uid $$(id -u)

manager:
	IOTLAB_HELPER_SOCKET=/tmp/iotlab-helper.sock IOTLAB_ENABLE_ACTIONS=1 \
	  $(PYTHON) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080

deploy:
	scripts/deploy.sh --dest $${DEST:-/opt/iotlab}

rollback:
	scripts/rollback.sh --dest $${DEST:-/opt/iotlab}

offline:
	scripts/export-offline.sh

clean:
	rm -rf __pycache__ .pytest_cache backend/app/__pycache__ tools/__pycache__ tests/__pycache__
