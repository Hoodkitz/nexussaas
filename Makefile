.PHONY: up down migrate sandbox-image test lint api worker backup install-services

PY ?= .venv/bin/python

up:            ## start Postgres + Redis
	docker compose up -d db redis

down:
	docker compose down

migrate:
	$(PY) -m alembic upgrade head

sandbox-image:
	docker build -t nexussaas-sandbox:latest infra/sandbox

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check apps packages tests migrations

api:
	$(PY) -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000

worker:
	$(PY) -m apps.worker.main

backup:
	scripts/backup.sh

install-services:
	mkdir -p ~/.config/systemd/user
	cp infra/systemd/*.service ~/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable --now nexussaas-api nexussaas-worker
