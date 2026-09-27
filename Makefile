.PHONY: run serve install test lint format help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies into .venv
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

run: ## Run the bot (long polling)
	python3 -m bot

serve: ## Run only the health/status HTTP server
	python3 -m bot.serve

test: ## Run the test suite
	pytest -q

lint: ## Lint and format-check
	ruff check .
	ruff format --check .

format: ## Auto-format the code
	ruff format .
	ruff check --fix .
