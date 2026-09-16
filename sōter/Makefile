.PHONY: up down logs test lint migrate
up:
	docker compose up -d --build
down:
	docker compose down
logs:
	docker compose logs -f api worker
test:
	pytest -q
lint:
	ruff check .
migrate:
	docker compose exec api alembic upgrade head
