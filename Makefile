ENV ?= dev
REGION = ap-south-1
SERVICES = voice-service conversation-orchestrator scheme-retrieval-service eligibility-engine user-profile-service scheme-management-service

.PHONY: install test lint build deploy-all clean

install:
	@for svc in $(SERVICES); do \
		echo "Installing $$svc..."; \
		pip install -r services/$$svc/requirements.txt -r services/$$svc/requirements-dev.txt; \
	done

test:
	@for svc in $(SERVICES); do \
		echo "Testing $$svc..."; \
		cd services/$$svc && pytest tests/ -v --cov=src --cov-fail-under=80; cd ../..; \
	done

lint:
	@for svc in $(SERVICES); do \
		flake8 services/$$svc/src/; \
		black --check services/$$svc/src/; \
	done

build:
	@mkdir -p artifacts
	@for svc in $(SERVICES); do \
		echo "Building $$svc..."; \
		cd services/$$svc && pip install -r requirements.txt -t dist/ -q && cp -r src/* dist/ && \
		cd dist && zip -r ../../../artifacts/$$svc.zip . -q && cd ../../..; \
	done
	@echo "Build complete. Artifacts in ./artifacts/"

deploy-all: build
	@for svc in $(SERVICES); do \
		FUNCTION=sahayak-$(ENV)-$$svc; \
		echo "Deploying $$FUNCTION..."; \
		aws lambda update-function-code \
			--function-name $$FUNCTION \
			--zip-file fileb://artifacts/$$svc.zip \
			--region $(REGION) --output text; \
		aws lambda wait function-updated --function-name $$FUNCTION --region $(REGION); \
	done

clean:
	@rm -rf artifacts/
	@find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete
