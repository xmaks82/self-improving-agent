.PHONY: build run stop logs shell clean update help version

# Default target
help:
	@echo "Self-Improving Agent - Commands:"
	@echo ""
	@echo "  make run      - Run agent (interactive)"
	@echo "  make update   - Update to latest version"
	@echo "  make build    - Build Docker image"
	@echo "  make stop     - Stop agent"
	@echo "  make logs     - View logs"
	@echo "  make shell    - Open shell in container"
	@echo "  make clean    - Remove containers and images"
	@echo "  make version  - Show current version"
	@echo ""

version:
	@grep 'version = ' pyproject.toml | head -1 | cut -d'"' -f2

update:
	@echo "Updating Self-Improving Agent..."
	@echo ""
	@echo "Current version:"
	@grep 'version = ' pyproject.toml | head -1
	@echo ""
	git fetch origin
	git pull origin main
	@echo ""
	@echo "New version:"
	@grep 'version = ' pyproject.toml | head -1
	@echo ""
	@echo "Rebuilding Docker image..."
	docker compose build
	@echo ""
	@echo "Update complete! Run 'make run' to start."

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
