.PHONY: dev setup sync score recs dryrun test lint clean

# Development
dev:
	docker-compose up --build

setup:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

# Data operations
sync:
	curl -X POST "http://localhost:8000/sync/full_sync" -u admin:change-me

score:
	curl -X POST "http://localhost:8000/score/icp?level=keyword&limit=1000" -u admin:change-me
	curl -X POST "http://localhost:8000/score/icp?level=term&limit=1000" -u admin:change-me

recs:
	curl -X POST "http://localhost:8000/recommendations/generate?types=neg,pause,budget&force_refresh=true" -u admin:change-me

dryrun:
	curl -X GET "http://localhost:8000/recommendations/?limit=5" -u admin:change-me | \
		python -c "import sys, json; recs = json.load(sys.stdin)['recommendations']; [print(r['id']) for r in recs]" | \
		head -3 | \
		xargs -I {} curl -X POST "http://localhost:8000/apply/dry_run_all" \
		-H "Content-Type: application/json" \
		-d '["{}", ]' \
		-u admin:change-me

# Testing
test:
	python -m pytest tests/ -v

test-integration:
	python -m pytest tests/test_integration.py -v

# Code quality
lint:
	black .
	isort .
	flake8 .

typecheck:
	mypy .

# Database
db-reset:
	docker-compose down -v
	docker-compose up -d postgres
	sleep 5
	docker-compose up --build

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# API testing
test-api:
	@echo "Testing health endpoint..."
	@curl -s http://localhost:8000/healthz | jq '.'
	@echo "\nTesting Google Ads status..."
	@curl -s http://localhost:8000/auth/google_ads/status -u admin:change-me | jq '.'

# Help
help:
	@echo "Available commands:"
	@echo "  dev         - Start development environment"
	@echo "  setup       - Set up Python virtual environment"
	@echo "  sync        - Sync data from Google Ads"
	@echo "  score       - Run ICP scoring"
	@echo "  recs        - Generate recommendations"
	@echo "  dryrun      - Dry-run top recommendations"
	@echo "  test        - Run unit tests"
	@echo "  lint        - Run code formatting and linting"
	@echo "  db-reset    - Reset database"
	@echo "  test-api    - Test API endpoints"
	@echo "  clean       - Clean up containers and images"
