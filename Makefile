# Makefile for Anki Telegram Bot Docker operations

.PHONY: help build up down logs shell clean restart dev prod pull-model

# Default target
help:
	@echo "Anki Telegram Bot - Docker Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build        Build all Docker images"
	@echo "  up           Start all services"
	@echo "  down         Stop all services"
	@echo "  logs         View logs (all services)"
	@echo "  logs-bot     View bot logs only"
	@echo "  shell        Open shell in bot container"
	@echo "  clean        Remove all containers and volumes"
	@echo "  restart      Restart all services"
	@echo "  dev          Start in development mode"
	@echo "  prod         Start in production mode"
	@echo "  pull-model   Pull Ollama model"

# Build all images
build:
	@echo "Building Docker images..."
	docker-compose build

# Start services
up:
	@echo "Starting services..."
	docker-compose up -d
	@echo ""
	@echo "Services started! Check logs with: make logs"
	@echo "Bot authentication code can be found in logs if not set in .env"

# Stop services
down:
	@echo "Stopping services..."
	docker-compose down

# View logs
logs:
	docker-compose logs -f

logs-bot:
	docker-compose logs -f bot

logs-ollama:
	docker-compose logs -f ollama

logs-anki:
	docker-compose logs -f anki

# Open shell in bot container
shell:
	docker-compose exec bot /bin/bash

# Clean everything
clean:
	@echo "Stopping and removing all containers, volumes..."
	docker-compose down -v
	@echo "Cleanup complete!"

# Restart services
restart:
	@echo "Restarting services..."
	docker-compose restart

# Development mode
dev:
	@echo "Starting in development mode..."
	docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Production mode
prod:
	@echo "Starting in production mode..."
	docker-compose up -d

# Pull Ollama model
pull-model:
	@echo "Pulling Gemma2:9b model..."
	docker-compose run --rm ollama-puller

# Check service health
health:
	@echo "Checking service health..."
	@docker-compose ps
	@echo ""
	@echo "Ollama status:"
	@curl -s http://localhost:11434/api/tags | jq -r '.models[].name' 2>/dev/null || echo "Ollama not responding"
	@echo ""
	@echo "Anki status:"
	@curl -s http://localhost:8765 || echo "Anki not responding"