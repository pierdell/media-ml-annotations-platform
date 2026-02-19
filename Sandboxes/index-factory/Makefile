.PHONY: up down build logs test seed clean

# Start all services
up:
	docker compose up -d --build

# Stop all services
down:
	docker compose down

# Build without starting
build:
	docker compose build

# View logs
logs:
	docker compose logs -f

# View API logs
logs-api:
	docker compose logs -f api

# View worker logs
logs-worker:
	docker compose logs -f worker

# Run tests
test:
	python -m unittest tests/test_structure.py -v

# Seed mock data (requires running services)
seed:
	python scripts/seed_data.py

# Reset everything (volumes included)
clean:
	docker compose down -v --remove-orphans

# Open RabbitMQ management UI
rabbitmq-ui:
	@echo "Opening http://localhost:15672 (user: indexfactory / pass: indexfactory_secret)"
	@xdg-open http://localhost:15672 2>/dev/null || open http://localhost:15672 2>/dev/null || true

# Shell into API container
shell-api:
	docker compose exec api bash

# Shell into worker container
shell-worker:
	docker compose exec worker bash

# Run database migrations
migrate:
	docker compose exec api alembic upgrade head

# Create a new migration
migration:
	@read -p "Migration message: " msg && \
	docker compose exec api alembic revision --autogenerate -m "$$msg"
