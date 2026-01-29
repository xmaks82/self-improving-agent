.PHONY: build run stop logs shell clean help

# Default target
help:
	@echo "Self-Improving Agent - Commands:"
	@echo ""
	@echo "  make build    - Build Docker image"
	@echo "  make run      - Run agent (interactive)"
	@echo "  make stop     - Stop agent"
	@echo "  make logs     - View logs"
	@echo "  make shell    - Open shell in container"
	@echo "  make clean    - Remove containers and images"
	@echo ""

build:
	docker compose build

run:
	docker compose run --rm agent

stop:
	docker compose down

logs:
	docker compose logs -f

shell:
	docker compose run --rm agent /bin/bash

clean:
	docker compose down --rmi all --volumes
