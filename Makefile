# Sahayak AI Makefile
# Commands for development, testing, and deployment

.PHONY: help install dev test clean docker-build docker-run deploy-local

# Show help message
help:
	@echo "Sahayak AI - Voice-first, multilingual government scheme assistant"
	@echo ""
	@echo "Usage:"
	@echo "  make install          Install dependencies"
	@echo "  make dev              Run development server"
	@echo "  make test             Run all tests"
	@echo "  make test-unit        Run unit tests"
	@echo "  make test-integration Run integration tests"
	@echo "  make clean            Clean temporary files"
	@echo "  make docker-build     Build Docker image"
	@echo "  make docker-run       Run application in Docker"
	@echo "  make deploy-local     Deploy to localstack for testing"

# Install dependencies
install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .

# Run development server
dev:
	uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Run all tests
test:
	python -m pytest tests/ -v

# Run unit tests
test-unit:
	python -m pytest tests/ -v -k "test_" --cov=services --cov-report=html

# Run integration tests
test-integration:
	python -m pytest tests/ -v -m integration

# Clean temporary files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache/
	rm -rf .coverage/
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/

# Build Docker image
docker-build:
	docker build -t sahayak-ai:latest .

# Run application in Docker
docker-run:
	docker run -p 8000:8000 sahayak-ai:latest

# Deploy to localstack for testing
deploy-local:
	@echo "Deploying to LocalStack for testing..."
	# Add commands to deploy to localstack here
	# This might include creating DynamoDB tables, S3 buckets, etc.
	@echo "Deployment to LocalStack completed"

# Run code formatting
format:
	black .

# Run linting
lint:
	flake8 .
	mypy .

# Run security scan
security:
	bandit -r . -x ./.venv,.git,__pycache__

# Run all checks
checks: lint security test

# Create a new migration
migration:
	@echo "Creating database migration..."
	# This would be implemented based on the specific database migration tool used

# Seed the database with initial data
seed:
	python scripts/seed_schemes.py

# Run smoke tests
smoke-test:
	python scripts/smoke_test.py

# Generate API documentation
docs:
	python -m pydoc -w .